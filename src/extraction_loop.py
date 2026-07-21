from pathlib import Path
from collections.abc import Generator
from typing import Any, Dict
import extractors
import json
import yaml
import logging


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
    "NCIT": "NCIT"
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
    vocabulary_id = row["vocabulary_id"]
    vocabulary_id = vocabulary_id.upper() if vocabulary_id else ""
    if concept_id:
        if "_" in concept_id:
            return concept_id.replace("_", ":")
        prefix = PREFIXES.get(vocabulary_id)
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
    concept = {
        "ontology_id": row["vocabulary_id"],
        "concept_id": formatted_code,
        "concept_code": found_code(formatted_code)
    }

    if row["vocabulary_id"] == "NCIt":
        concept["definition"] = row["concept_name"]
    else:
        concept["display"] =row["concept_name"]

    if row["invalid_reason"]:
        concept["version"] = row["valid_end_date"]
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
        "ontology_id": row["vocabulary_id"],
        "name": row["vocabulary_name"],
    }

    for source, dest in columns.items():
        if source in config:
            vocabulary[dest] = config[source]

    if config.get("archive_filename"):
        vocabulary["source"] = f"{config.get('source_type')} - {config.get('archive_filename')}"

    return vocabulary


def write_concept(data: Generator[list[Dict[str, Any]]], output_path: str, config: dict, version=None):
    """Takes unzipped data file and writes it to a JSON file in TermConcept format.

    Arguments:
        data: Unzipped data file.
        output_path: The path to write the JSON file.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as o:
        for chunk in data:
            for row in chunk:
                o.write(json.dumps(concept_rows(row, config, version)) + "\n")

def write_vocab(data: Generator[list[Dict[str, Any]]], output_path: str, config: dict):
    """Takes unzipped data file and writes it to a JSON file in TermOntology format.

    Arguments:
        data: Unzipped data file.
        output_path: The path to write the JSON file.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as o:
        for chunk in data:
            for row in chunk:
                o.write(json.dumps(vocab_rows(row, config)) + "\n")

def extract(config_path: Path):
    """Iterates over the 'vocabularies' property in the config file and runs
    the appropriate extractor script based on source_type.
    Creates a collection of archive filenames and only runs the extractor
    on unique filenames to avoid duplicates.

    Arguments:
        config_path: The specified config file to iterate.
    """
    with open(config_path) as c:
        config = yaml.safe_load(c)

    extracted_files = {}
    dirs_to_cleanup = []

    for vocab in config["vocabularies"]:
        source_type = vocab["source_type"]
        extractor_type = EXTRACTORS.get(source_type.upper())
        if extractor_type is None:
            logging.warning(f"{source_type} is not a valid source type.")
            continue

        vocabulary_id = vocab.get("vocabulary_id")
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
            extractor.extract_data(vocabulary_id=vocabulary_id, data_type="CONCEPT", chunk_size=100),
            f"output/{vocabulary_id}_concept.jsonl",
            config=vocab,
            version=version,
        )
        write_vocab(
            extractor.extract_data(vocabulary_id=vocabulary_id, data_type="VOCABULARY", chunk_size=1),
            f"output/{vocabulary_id}_vocabulary.jsonl",
            config=vocab,
        )
    for extractor in dirs_to_cleanup:
        extractor.__exit__(None, None, None)
