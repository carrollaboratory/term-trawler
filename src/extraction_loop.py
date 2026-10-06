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
from sqlalchemy import text

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
    if row.get("invalid_reason") in ("U", "D") and replacement:
        dep_concept["replacement_curie"] = replacement.get(row.get("concept_id"))
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
        "name": row["vocabulary_name"] or config.get("vocabulary_name", ""),
        "version": row["vocabulary_version"],
    }

    for source, dest in columns.items():
        if source in config:
            vocabulary[dest] = config[source]

    if config.get("archive_filename"):
        vocabulary["vocabulary_source"] = (
            f"{config.get('source_type')} - {Path(config['archive_filename']).name}"
        )
    else:
        vocabulary["vocabulary_source"] = (
            f"{config.get('source_type')} - {Path(config['owl_file'])}"
        )
    return vocabulary


loader = LinkMLModelLoader(
    database_url=f"postgresql://{os.environ['PGUSER']}:{os.environ['PGPASSWORD']}"
    f"@{os.environ['PGHOST']}:{os.environ['PGPORT']}/{os.environ['PGDATABASE']}",
    model_import_path="common_access_model.datamodel.common_access_model_sqla",  # the name you found in the wheel
    table_prefix="term_{}",  # note the `{}` -- see Gotchas below
    schema_name="dev_include_access",
).load()
assert loader.module is not None, "LinkML model failed to load"
Base = loader.module.Base


def load_concept(data, config: dict, replacement=None):
    """Loads both Concept and DeprecatedConcept tables"""

    with loader.create_session() as session:
        for chunk in data:
            concepts = []
            deprecated_concepts = []
            for row in chunk:
                concepts.append(Concept(**concept_rows(row, config)))
                if row.get("invalid_reason"):
                    deprecated_concepts.append(
                        DeprecatedConcept(
                            **deprecated_concept_rows(row, config, replacement)
                        )
                    )
            session.add_all(concepts)
            session.add_all(deprecated_concepts)
            session.commit()


def load_vocab(data, config: dict):
    with loader.create_session() as session:
        for chunk in data:
            vocabs = [Vocabulary(**vocab_rows(row, config)) for row in chunk]
            session.add_all(vocabs)
            session.commit()


def create_omop_fallback(db_engine):
    """Builds 'OMOP' vocabulary for updated codes to fall back to 'OMOP:0' if they do not have a replacement"""
    with db_engine.begin() as connection:
        # Create the OMOP fallback vocabulary
        connection.execute(
            text("""
                INSERT INTO dev_include_access.term_vocabulary (
                    vocabulary_id,
                    name,
                    vocabulary_uri,
                    fhir_system,
                    vocabulary_prefix,
                    description,
                    version,
                    vocabulary_source
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
                ON CONFLICT (vocabulary_prefix) DO NOTHING
            """)
        )

        # # Create the fallback deprecated concept
        # # The line below has been commented out because replacement_curie is no longer required in the new model,
        # common_access_model. We are keeping the code for the OMOP:0 fallback in case it is needed in the future
        # connection.execute(
        #     text("""
        #         INSERT INTO dev_include_access.term_deprecatedconcept (
        #             concept_curie,
        #             deprecation_type,
        #             replacement_curie
        #         )
        #         SELECT 'OMOP:0', NULL, NULL
        #         WHERE NOT EXISTS(SELECT 1 FROM dev_include_access.term_deprecatedconcept WHERE concept_curie = 'OMOP:0')
        #     """)
        # )


def apply_omop_fallback(db_engine):
    """Applies 'OMOP:0' fallback for replacement_curie for deprecated/updates codes with no replacements"""
    with db_engine.begin() as connection:
        connection.execute(
            text("""
                UPDATE dev_include_access.term_deprecatedconcept
                SET replacement_curie = 'OMOP:0'
                WHERE deprecation_type IS NOT NULL
                  AND replacement_curie IS NULL
                  AND concept_curie <> 'OMOP:0'
            """)
        )


def update_replacements_by_curie(pairs: dict[str, str], db_engine):
    if not pairs:
        return
    with db_engine.begin() as connection:
        connection.execute(
            text("""
                UPDATE dev_include_access.term_deprecatedconcept AS c
                SET replacement_curie = CASE
                    WHEN EXISTS (
                        SELECT 1 FROM dev_include_access.term_concept AS t
                        WHERE t.concept_curie = r.new_curie
                    ) THEN r.new_curie
                END
                FROM (
                    SELECT unnest(CAST(:olds AS text[])) AS old_curie,
                           unnest(CAST(:news AS text[])) AS new_curie
                ) AS r
                WHERE c.concept_curie = r.old_curie
            """),
            {"olds": list(pairs), "news": list(pairs.values())},
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
    Base.metadata.create_all(db_engine)

    create_omop_fallback(db_engine)
    with open(config_path) as c:
        config = yaml.safe_load(c)
        ExtractorBase.chunk_size = int(chunk_size)

    extracted_files = {}
    dirs_to_cleanup = []
    all_replacements = {}
    owl_replacements = {}

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
    update_replacements_by_curie(owl_replacements, db_engine)
    for extractor in dirs_to_cleanup:
        extractor.__exit__(None, None, None)

    # The line below has been commented out because replacement_curie is no longer required in the new model,
    # common_access_model. We are keeping the code for the OMOP:0 fallback in case it is needed in the future
    # apply_omop_fallback(db_engine)
