import logging
import os
from pathlib import Path

import yaml
from car_utils import LinkMLModelLoader
from common_access_model.datamodel.common_access_model_sqla import (
    Concept,
    DeprecatedConcept,
    Vocabulary,
)
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert

import extractors
from extractors import ExtractorBase
from streamer.engine import get_engine
from utils import format_code, found_code

logger = logging.getLogger(__name__)

EXTRACTORS = {
    obj.extractor_name: obj  # OMOP: obj are your dictionary entries
    for name in extractors.__all__  # iterate over each of your __all__ strings
    if (obj := getattr(extractors, name))  # Unpack the class object from the module
    and issubclass(
        obj, extractors.ExtractorBase
    )  # Confirm that it is a child class of the ExtractorBase
    and obj is not extractors.ExtractorBase  # Avoid capturing the parent class itself.
}

REPORT_DIR = Path("count_reports")

loader = LinkMLModelLoader(
    database_url=f"postgresql://{os.environ['PGUSER']}:{os.environ['PGPASSWORD']}"
    f"@{os.environ['PGHOST']}:{os.environ['PGPORT']}/{os.environ['PGDATABASE']}",
    model_import_path="common_access_model.datamodel.common_access_model_sqla",  # the name you found in the wheel
    table_prefix="{}",  # note the `{}` -- see Gotchas below
    schema_name="dev_include_access",
).load()
assert loader.module is not None, "LinkML model failed to load"
Base = loader.module.Base


def select_vocabs(config: dict, extract_vocab: str | list[str] | None) -> list[dict]:
    vocabs = config["vocabularies"]
    if not extract_vocab:
        return vocabs
    if isinstance(extract_vocab, str):
        extract_vocab = [extract_vocab]
    wanted = {
        part.strip().upper()
        for item in extract_vocab
        for part in item.split(",")
        if part.strip()
    }

    def names(v: dict) -> set[str]:
        return {
            str(v.get("prefix") or "").upper(),
            str(v.get("vocabulary_id") or "").upper(),
        }

    selected = [v for v in vocabs if wanted & names(v)]
    matched = set().union(*(names(v) for v in selected)) if selected else set()
    missing = sorted(wanted - matched)
    if missing:
        logger.error(f"No vocabulary matching '{missing}' in config")
    return selected


def concept_rows(row: dict[str, str | None], config: dict):
    """Takes zip file and writes the data into TermOntology format.

    Arguments:
        row: Row in zip file.
        config_prefix: The "prefix" in the config file.
    """
    formatted_code = format_code(row, config)
    vocabulary_prefix = config.get("prefix", "")
    concept = {
        "concept_curie": formatted_code,
        "vocabulary_prefix": vocabulary_prefix,
        "concept_code": found_code(formatted_code),
    }

    if (
        config.get("source_type", "").upper() == "OMOP"
        and vocabulary_prefix
        and vocabulary_prefix.upper() == "NCIT"
    ):
        concept["definition"] = row["concept_name"]
    else:
        concept["display"] = row.get("concept_name")
        if row.get("definition"):
            concept["definition"] = row["definition"]

    if config.get("source_type", "").upper() == "OMOP":
        concept["concept_id"] = row.get("concept_id")

    return concept


def deprecated_concept_rows(row: dict[str, str | None], config: dict, replacement=None):
    """Builds a row for the DeprecatedConcept table.

    Arguments:
        row: Row in zip file.
        config: The config dictionary for a vocabulary.
        replacement: Dict mapping deprecated concept_id -> replacement concept_curie.
    """
    formatted_code = format_code(row, config)
    dep_concept = {
        "concept_curie": formatted_code,
        "deprecation_type": row.get("invalid_reason"),
    }

    if replacement:
        found_replacement = (
            replacement.get(row.get("concept_id"))
            if config["source_type"] == "OMOP"
            else replacement.get(formatted_code)
        )

        if found_replacement:
            dep_concept["replacement_curie"] = found_replacement
        # The code below is commented out because replacement_curie is not required in the new
        # model, but we are keeping the code in case it is needed in the future
        # else:
        #     dep_concept["replacement_curie"] = "OMOP:0"
    return dep_concept


def vocab_rows(row: dict[str, str | None], config: dict):
    """Takes zip file and writes the data into TermOntology format.

    Arguments:
        row: Row in zip file.
        config: The config dictionary for a vocabulary.
    """
    columns = {
        "vocabulary_uri": "vocabulary_uri",
        "fhir_system": "fhir_system",
        "prefix": "vocabulary_prefix",
        "description": "description",
    }

    vocabulary = {
        "vocabulary_id": row.get("vocabulary_id") or config.get("prefix", ""),
        "name": row.get("vocabulary_name") or config.get("vocabulary_name", ""),
        "version": row.get("vocabulary_version"),
    }

    for source, dest in columns.items():
        if source in config:
            vocabulary[dest] = config[source]

    if config.get("source_filename"):
        vocabulary["vocabulary_source"] = (
            f"{config.get('source_type')} - {Path(config['source_filename']).name}"
        )
    else:
        vocabulary["vocabulary_source"] = (
            f"{config.get('source_type')} - {Path(config['owl_file'])}"
        )
    return vocabulary


def omop_vocab_row():
    columns = {
        "vocabulary_uri": "https://ohdsi.org",
        "fhir_system": "http://hl7.org/fhir/uv/omop/ImplementationGuide/hl7.fhir.uv.omop",
        "vocabulary_prefix": "OMOP",
        "description": "OMOP Metadata Fallback",
        "vocabulary_id": "OMOP",
        "name": "OMOP Metadata Fallback",
        "version": "",
        "vocabulary_source": "",
    }

    return columns


def omop_concept_row():
    columns = {
        "concept_curie": "OMOP:0",
        "concept_id": 0,
        "display": "No matching concept",
        "vocabulary_prefix": "OMOP",
        "definition": "No matching concept",
        "concept_code": 0,
    }
    return columns


def upsert_concepts(session, rows: dict[str, dict]):
    table = Concept.__table__
    # Multi-row inserts need identical keys in every row, so fill gaps with None (e.g. display vs definition)
    keys = {k for r in rows.values() for k in r}
    values = [{k: r.get(k) for k in keys} for r in rows.values()]
    update_cols = [k for k in keys if k != "concept_curie"]
    # Builds INSERT with every row in the chunk
    stmt = insert(table).values(values)
    # Updates row if it already exists
    stmt = stmt.on_conflict_do_update(
        index_elements=["concept_curie"],
        # Sets row excluded due to pre-existence/conflict to the value of the new row
        set_={k: stmt.excluded[k] for k in update_cols},
        # Only update if the value in an existing row is different from a value in the new row
        where=or_(
            *[table.c[k].is_distinct_from(stmt.excluded[k]) for k in update_cols]
        ),
    )
    session.execute(stmt)


def load_concept(data, config: dict, replacement=None):
    """Loads both Concept and DeprecatedConcept tables."""
    with loader.create_session() as session:
        # Builds one dict per concept
        for chunk in data:
            concepts = {}
            deprecated = {}
            for row in chunk:
                c = concept_rows(row, config)
                concepts[c["concept_curie"]] = c
                # If "invalid_reason" in row, builds DeprecatedConcept dict
                if row.get("invalid_reason"):
                    d = deprecated_concept_rows(row, config, replacement)
                    deprecated[d["concept_curie"]] = d
            if concepts:
                upsert_concepts(session, concepts)
            # Loads existing deprecated rows, updates them, or adds new ones
            if deprecated:
                existing_dep = {
                    r.concept_curie: r
                    # scalars() returns the deprecated objects directly from the row
                    for r in session.scalars(
                        select(DeprecatedConcept).where(
                            DeprecatedConcept.concept_curie.in_(list(deprecated))
                        )
                    )
                }
                for k, d in deprecated.items():
                    if k in existing_dep:
                        # If a curie already exists in deprecated concepts, setattr copies the new values from d onto that row
                        for attr, value in d.items():
                            setattr(existing_dep[k], attr, value)
                    else:
                        session.add(DeprecatedConcept(**d))

            session.commit()


def load_vocab(data, config: dict):
    with loader.create_session() as session:
        for chunk in data:
            for row in chunk:
                session.merge(Vocabulary(**vocab_rows(row, config)))
            session.commit()


def create_omop_fallback():
    """Builds 'OMOP' vocabulary for updated codes to fall back to 'OMOP:0' if they do not have a replacement"""
    with loader.create_session() as session:
        session.merge(Vocabulary(**omop_vocab_row()))
        session.commit()

        # Create the fallback deprecated concept
    with loader.create_session() as session:
        session.merge(Concept(**omop_concept_row()))
        session.commit()


def count_concepts(session, vocab_ids: set[str] | None = None) -> dict[str, int]:
    """Returns {vocbulary_prefix: number of concepts} for the Concept table"""
    stmt = select(Concept.vocabulary_prefix, func.count()).group_by(
        Concept.vocabulary_prefix
    )
    if vocab_ids:
        stmt = stmt.where(Concept.vocabulary_prefix.in_(vocab_ids))
    return dict(session.execute(stmt).all())


def build_count_report(before: dict[str, int], after: dict[str, int]) -> list[dict]:
    """Build one row per ontology comparing concept counts before and after the load"""
    # Union of both, so ontologies that are new or deleted still get a row
    rows = []
    for prefix in sorted(set(before) | set(after)):
        prev = before.get(prefix, 0)
        curr = after.get(prefix, 0)
        if prefix not in before:
            note = "NEW"
        else:
            note = ""
        rows.append(
            {
                "prefix": prefix,
                "prev": prev,
                "current": curr,
                "change": curr - prev,
                "note": note,
            }
        )
    return rows


def format_count_report(rows: list[dict]) -> str:
    """Format the count report rows as an aligned table"""
    lines = [f"{'Prefix':<22}{'Prev':>14}{'Current':>14}{'Change':>12}  Note"]
    for r in rows:
        lines.append(
            f"{r['prefix']:<22}{r['prev']:>14,}{r['current']:>14,}"
            f"{r['change']:>+12,}  {r['note']}"
        )
    return "\n".join(lines)


def print_count_report(rows: list[dict]):
    """Print the report as an aligned table"""
    print(format_count_report(rows))


def write_count_report(rows: list[dict], output: Path) -> Path:
    """Write count report to a timestamped CSV"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(format_count_report(rows) + "\n")
    return output


def extract(
    config_path: Path,
    chunk_size: int,
    report_path: Path | None = None,
    extract_vocab: str | None = None,
):
    """Iterates over the 'vocabularies' property in the config file and runs
    the appropriate extractor script based on source_type.
    Creates a collection of filenames and only runs the extractor
    on unique filenames to avoid duplicates.

    Arguments:
        config_path: The specified config file to iterate.
    """
    db_engine = get_engine(config_path)
    Base.metadata.create_all(db_engine)

    with open(config_path) as c:
        config = yaml.safe_load(c)
    ExtractorBase.chunk_size = int(chunk_size)
    selected = select_vocabs(config, extract_vocab)
    report_ids = {v["prefix"] for v in selected if v.get("prefix")}
    with loader.create_session() as session:
        before = count_concepts(session, report_ids)
    # The line below is commented out because replacement_curie is not required in the new model,
    # so we do not need an OMOP fallback at this time. We are keeping the code in case it is needed in the future
    # create_omop_fallback()

    extracted_files = {}
    dirs_to_cleanup = []
    all_replacements = {}
    owl_replacements = {}
    for vocab in selected:
        source_type = vocab["source_type"]
        extractor_type = EXTRACTORS.get(source_type.upper())
        if extractor_type is None:
            logger.warning(f"{source_type} is not a valid source type.")
            continue

        vocabulary_id = vocab.get("vocabulary_id") or vocab.get("prefix")
        if not vocabulary_id:
            logger.warning(
                f"Skipping vocabulary entry with no vocabulary_id or prefix: {vocab}"
            )
            continue
        filename = vocab.get("source_filename")

        if filename is not None and filename in extracted_files:
            extractor = extractor_type(vocab)
            extractor.temp_dir = extracted_files[filename]
        else:
            extractor = extractor_type(vocab)
            extractor.__enter__()
            dirs_to_cleanup.append(extractor)
            if filename is not None and extractor.temp_dir is not None:
                extracted_files[filename] = extractor.temp_dir

        print(f"Starting vocabulary: {vocabulary_id}", flush=True)

        replacement = extractor.get_replacement(vocab)
        if replacement:
            all_replacements.update(replacement)

        load_vocab(
            extractor.extract_data(vocabulary_id=vocabulary_id, data_type="VOCABULARY"),
            config=vocab,
        )

        print("Starting concept load...", flush=True)

        load_concept(
            extractor.extract_data(vocabulary_id=vocabulary_id, data_type="CONCEPT"),
            config=vocab,
            replacement=replacement,
        )
        print("Concept load finished.", flush=True)
        if source_type.upper() == "OWL":
            for chunk in extractor.extract_data(
                vocabulary_id=vocabulary_id, data_type="DEPRECATED_CONCEPT"
            ):
                for row in chunk:
                    if row.get("replacement_curie"):
                        owl_replacements[row["concept_curie"]] = row[
                            "replacement_curie"
                        ]
    with loader.create_session() as session:
        after = count_concepts(session, report_ids)
    report = build_count_report(before, after)
    print_count_report(report)
    if report_path:
        write_count_report(report, report_path)
        logger.info(f"Wrote count report to {report_path}")
    for extractor in dirs_to_cleanup:
        extractor.__exit__(None, None, None)
