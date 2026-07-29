import json
import logging
from collections.abc import Generator
from pathlib import Path
from typing import Any

import yaml

import extractors
from extractors import ExtractorBase

logger = logging.getLogger(__name__)


EXTRACTORS = {
    getattr(obj, "extractor_name"): obj  # OMOP: obj are your dictionary entries
    for name in extractors.__all__  # iterate over each of your __all__ strings
    if (obj := getattr(extractors, name))  # Unpack the class object from the module
    and issubclass(
        obj, extractors.ExtractorBase
    )  # Confirm that it is a child class of the ExtractorBase
    and obj is not extractors.ExtractorBase  # Avoid capturing the parent class itself.
}

PREFIXES = {
    "SNOMED": "snomedct",
    "NCIT": "NCIT",
    "EDAM": "edam"
}
def format_code(row: dict[str, str | None], config: dict):
    """Takes the concept_code in the zip files and formats it to the [prefix]:[code] format
    for the output.

    Replaces "_" with ":" in the codes.
    If ":" is not present in the concept_code, it first defers to the prefix in the config file,
    then the dictionary above to build the code format.

    Arguments:
        row: Row in zip file.
        config_prefix: The "prefix" in the config file.

    Returns:
        Returns the formatted concept_id
    """
    concept_id = row["concept_code"]
    if not concept_id:
        raise ValueError("No concept_code in row.")
    vocabulary_id = row.get("vocabulary_id") or config.get("prefix", "")
    vocabulary_id = vocabulary_id.upper() if vocabulary_id else ""
    prefix = PREFIXES.get(vocabulary_id)
    if concept_id:
        if config.get("source_type", "").upper() == "OMOP" and "_" in concept_id:
            return concept_id.replace("_", ":")
        if "_" in concept_id and prefix:
            embedded_prefix, _, remainder = concept_id.partition("_")
            if embedded_prefix.upper() == prefix.upper():
                return f"{prefix}:{remainder}"
        if ":" not in concept_id:
            prefix = config.get("prefix", "") or PREFIXES.get(vocabulary_id.upper(), "")
            if not prefix:
                raise ValueError(f"Prefix not found for {vocabulary_id}")
            return f"{prefix}:{concept_id}"
    return concept_id

def found_code(concept_code: str):
    """Takes the concept_code and extracts only the code portion after the delimiter,
    or only returns the code if no delimiter is present.

    Arguments:
        concept_code: The formatted concept code in [prefix]:[code] format

    Returns:
        The code after the delimeter in the concept_code.
    """
    if ":" in concept_code:
        return concept_code.split(":")[1]
    return concept_code

def concept_rows(row: dict[str, str | None], config: dict, version=None):
    """Takes zip file and writes the data into TermOntology format.

    Arguments:
        row: Row in zip file.
        config_prefix: The "prefix" in the config file.
    """
    formatted_code = format_code(row, config)
    vocabulary_id = row.get("vocabulary_id", config.get("prefix", ""))
    concept = {
        "ontology_id": vocabulary_id,
        "concept_id": formatted_code,
        "concept_code": found_code(formatted_code)
    }

    if config.get("source_type", "").upper() == "OMOP" and vocabulary_id and vocabulary_id.upper() == "NCIT":
        concept["definition"] = row["concept_name"]
    else:
        concept["display"] = row.get("concept_name")

    if row.get("invalid_reason"):
        concept["version"] = row.get("valid_end_date")
    else:
        concept["version"] = version

    return concept

def vocab_rows(row: dict[str, str | None], config: dict):
    """Takes zip file and writes the data into TermOntology format.

    Arguments:
        row: Row in zip file.
        config: The config dictionary for a vocabulary.
    """
    columns = {
        "vocabulary_uri": "ontology_uri",
        "fhir_system": "fhir_system",
        "prefix": "prefix",
        "description": "description",
    }

    vocabulary = {
        "ontology_id": row.get("vocabulary_id") or config.get("prefix", ""),
        "name": row["vocabulary_name"] or config.get("vocabulary_name", "")
    }

    for source, dest in columns.items():
        if source in config:
            vocabulary[dest] = config[source]

    if config.get("archive_filename"):
        vocabulary["source"] = f"{config.get('source_type')} - {Path(config['archive_filename']).name}"

    return vocabulary


def write_concept(data: Generator[list[dict[str, Any]]], output_path: str, config: dict, version=None):
    """Takes unzipped data file and writes it to a JSON file in TermConcept format.

    Arguments:
        data: Unzipped data file.
        output_path: The path to write the JSON file.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as o:
        for chunk in data:
            for row in chunk:
                o.writelines(json.dumps(concept_rows(row, config, version)) + "\n")

def write_vocab(data: Generator[list[dict[str, Any]]], output_path: str, config: dict):
    """Takes unzipped data file and writes it to a JSON file in TermOntology format.

    Arguments:
        data: Unzipped data file.
        output_path: The path to write the JSON file.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as o:
        for chunk in data:
            for row in chunk:
                o.writelines(json.dumps(vocab_rows(row, config)) + "\n")

def extract(config_path: Path, chunk_size: int):
    """Iterates over the 'vocabularies' property in the config file and runs
    the appropriate extractor script based on source_type.
    Creates a collection of archive filenames and only runs the extractor
    on unique filenames to avoid duplicates.

    Arguments:
        config_path: The specified config file to iterate.
    """
    with open(config_path) as c:
        config = yaml.safe_load(c)

        ExtractorBase.chunk_size = int(chunk_size)
    extracted_files = {}
    dirs_to_cleanup = []

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

        version = extractor.get_version(vocabulary_id)

        write_concept(
            extractor.extract_data(vocabulary_id=vocabulary_id, data_type="CONCEPT"),
            f"output/{vocabulary_id}_concept.jsonl",
            config=vocab,
            version=version,
        )
        write_vocab(
            extractor.extract_data(vocabulary_id=vocabulary_id, data_type="VOCABULARY"),
            f"output/{vocabulary_id}_vocabulary.jsonl",
            config=vocab,
        )
    for extractor in dirs_to_cleanup:
        extractor.__exit__(None, None, None)
