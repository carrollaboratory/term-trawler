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


def create_omop_fallback():
    """Builds 'OMOP' vocabulary for updated codes to fall back to 'OMOP:0' if they do not have a replacement"""
    with loader.create_session() as session:
        vocab = [Vocabulary(**omop_vocab_row())]
        session.add_all(vocab)
        session.commit()

        # Create the fallback deprecated concept
    with loader.create_session() as session:
        concept = [Concept(**omop_concept_row())]
        session.add_all(concept)
        session.commit()


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
    # The line below is commented out because replacement_curie is not required in the new model,
    # so we do not need an OMOP fallback at this time. We are keeping the code in case it is needed in the future
    # create_omop_fallback()
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
    for extractor in dirs_to_cleanup:
        extractor.__exit__(None, None, None)
