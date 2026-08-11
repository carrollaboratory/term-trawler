import io
import logging
from datetime import datetime, timezone
from pathlib import Path

import yaml
from car_utils import LinkMLModelLoader
from sqlalchemy import case, text, update
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import true

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


def deprecated(row: dict[str, str | None]):
    invalid = row.get("invalid_reason")
    return invalid is not None and invalid.upper() == "D"


def concept_rows(row: dict[str, str | None], config: dict, replacement=None):
    """Takes zip file and writes the data into TermOntology format.

    Arguments:
        row: Row in zip file.
        config_prefix: The "prefix" in the config file.
    """
    formatted_code = format_code(row, config)
    vocabulary_id = row.get("vocabulary_id", config.get("prefix", ""))
    concept = {
        "concept_curie": formatted_code,
        "vocabulary_id": vocabulary_id,
        "concept_code": found_code(formatted_code),
        "deprecated": deprecated(row),
        "dbt_updated_at": datetime.now(timezone.utc),
        "dbt_valid_from": row.get("valid_start_date") or datetime.now(timezone.utc),
    }

    if (
        config.get("source_type", "").upper() == "OMOP"
        and vocabulary_id
        and vocabulary_id.upper() == "NCIT"
    ):
        concept["definition"] = row["concept_name"]
    else:
        concept["display"] = row.get("concept_name")

    if config.get("source_type", "").upper() == "OMOP":
        concept["omop_concept_id"] = row.get("concept_id")

    return concept


def vocab_rows(row: dict[str, str | None], config: dict):
    """Takes zip file and writes the data into TermOntology format.

    Arguments:
        row: Row in zip file.
        config: The config dictionary for a vocabulary.
    """
    columns = {
        "vocabulary_uri": "vocabulary_uri",
        "fhir_system": "fhir_system",
        "prefix": "prefix",
        "description": "description",
    }

    vocabulary = {
        "vocabulary_id": row.get("vocabulary_id") or config.get("prefix", ""),
        "name": row["vocabulary_name"] or config.get("vocabulary_name", ""),
        "version": row["vocabulary_version"],
    }

    for source, dest in columns.items():
        if source in config:
            vocabulary[dest] = config[source]

    if config.get("archive_filename"):
        vocabulary["source"] = (
            f"{config.get('source_type')} - {Path(config['archive_filename']).name}"
        )
    else:
        vocabulary["source"] = (
            f"{config.get('source_type')} - {Path(config['owl_file'])}"
        )
    return vocabulary


loader = LinkMLModelLoader(
    database_url="postgresql://postgres:temp_password@localhost:5432/term_trawler",
    model_import_path="md_terminology_trove.md_terminology_trove",  # the name you found in the wheel
    table_prefix="term_{}",  # note the `{}` -- see Gotchas below
    schema_name="dev_include_access",
).load()


Concept = loader.get_model("Concept")
Vocabulary = loader.get_model("Vocabulary")


def load_concept(data, config: dict, replacement=None):
    with loader.create_session() as session:
        for chunk in data:
            concepts = [
                Concept(**concept_rows(row, config, replacement)) for row in chunk
            ]
            session.add_all(concepts)
            session.commit()


def load_vocab(data, config: dict):
    with loader.create_session() as session:
        for chunk in data:
            vocabs = [Vocabulary(**vocab_rows(row, config)) for row in chunk]
            session.add_all(vocabs)
            session.commit()


def create_omop_fallback(db_engine):
    with db_engine.begin() as connection:
        # Create the OMOP fallback vocabulary
        connection.execute(
            text("""
                INSERT INTO dev_include_access.term_vocabulary (
                    vocabulary_id,
                    name,
                    vocabulary_uri,
                    fhir_system,
                    prefix,
                    description,
                    version,
                    source
                )
                VALUES (
                    'OMOP',
                    'OMOP Metadata Fallback',
                    'https://ohdsi.org',
                    'http://hl7.org/fhir/uv/omop/ImplementationGuide/hl7.fhir.uv.omop',
                    'OMOP',
                    'OMOP Metadata Fallback',
                    NULL,
                    NULL
                )
                ON CONFLICT (vocabulary_id) DO NOTHING
            """)
        )

        # Create the fallback concept
        connection.execute(
            text("""
                INSERT INTO dev_include_access.term_concept (
                    concept_curie,
                    vocabulary_id,
                    concept_code,
                    omop_concept_id,
                    display,
                    deprecated,
                    replaced_by,
                    dbt_updated_at,
                    dbt_valid_from
                )
                VALUES (
                    'OMOP:0',
                    'OMOP',
                    '0',
                    0,
                    'No matching concept',
                    FALSE,
                    NULL,
                    NOW(),
                    NOW()
                )
                ON CONFLICT (concept_curie) DO NOTHING
            """)
        )


def update_replacements(replacement, db_engine):
    print(
        f"Updating {len(replacement):,} replacements...",
        flush=True,
    )

    if not replacement:
        return

    with db_engine.begin() as connection:
        connection.execute(
            text("""
                CREATE TEMP TABLE replacement_updates (
                    omop_concept_id INTEGER,
                    replacement TEXT
                ) ON COMMIT DROP
            """)
        )

        raw_connection = connection.connection.dbapi_connection

        data = io.StringIO()

        for omop_concept_id, replacement_curie in replacement.items():
            data.write(f"{int(omop_concept_id)}\t{replacement_curie}\n")

        data.seek(0)

        with raw_connection.cursor() as cursor:
            cursor.copy_from(
                data,
                "replacement_updates",
                columns=("omop_concept_id", "replacement"),
            )

        result = connection.execute(
            text("""
                UPDATE dev_include_access.term_concept AS c
                SET replaced_by = CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM dev_include_access.term_concept AS target
                        WHERE target.concept_curie = r.replacement
                    )
                    THEN r.replacement
                    ELSE 'OMOP:0'
                END
                FROM replacement_updates AS r
                WHERE c.omop_concept_id = r.omop_concept_id
            """)
        )

        print(
            f"Updated {result.rowcount:,} concepts.",
            flush=True,
        )


def extract(config_path: Path, chunk_size: int):
    """Iterates over the 'vocabularies' property in the config file and runs
    the appropriate extractor script based on source_type.
    Creates a collection of archive filenames and only runs the extractor
    on unique filenames to avoid duplicates.

    Arguments:
        config_path: The specified config file to iterate.
    """
    db_engine = get_engine(config_path)
    loader.module.Base.metadata.create_all(db_engine)

    create_omop_fallback(db_engine)
    with open(config_path) as c:
        config = yaml.safe_load(c)

        ExtractorBase.chunk_size = int(chunk_size)

    extracted_files = {}
    dirs_to_cleanup = []
    all_replacements = {}

    for vocab in config["vocabularies"]:
        source_type = vocab["source_type"]
        extractor_type = EXTRACTORS.get(source_type.upper())
        if extractor_type is None:
            logger.warning(f"{source_type} is not a valid source type.")
            continue

        vocabulary_id = vocab.get("vocabulary_id") or vocab.get("prefix")
        filename = vocab.get("archive_filename")

        if filename is not None and filename in extracted_files:
            extractor = extractor_type(vocab)
            extractor.temp_dir = extracted_files[filename]
        else:
            extractor = extractor_type(vocab)
            extractor.__enter__()
            dirs_to_cleanup.append(extractor)
            if filename is not None:
                extracted_files[filename] = extractor.temp_dir

        print(f"Starting vocabulary: {vocabulary_id}", flush=True)

        replacement = extractor.get_replacement(vocab)
        if replacement:
            all_replacements.update(replacement)
        print(
            f"Built {len(replacement)} replacement mappings for {vocabulary_id}",
            flush=True,
        )
        load_vocab(
            extractor.extract_data(vocabulary_id=vocabulary_id, data_type="VOCABULARY"),
            config=vocab,
        )

        print("Starting concept load...", flush=True)

        load_concept(
            extractor.extract_data(vocabulary_id=vocabulary_id, data_type="CONCEPT"),
            config=vocab,
        )
        print("Concept load finished.", flush=True)

        print(f"Number of replacements: {len(replacement)}", flush=True)

        print("Replacement update finished.", flush=True)
    for extractor in dirs_to_cleanup:
        extractor.__exit__(None, None, None)
    update_replacements(all_replacements, db_engine)
