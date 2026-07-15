import logging
from pathlib import Path

import yaml

import extractors
import json

EXTRACTORS = {
    getattr(obj, "extractor_name"): obj  # OMOP: obj are your dictionary entries
    for name in extractors.__all__  # iterate over each of your __all__ strings
    if (obj := getattr(extractors, name))  # Unpack the class object from the module
    and issubclass(
        obj, extractors.ExtractorBase
    )  # Confirm that it is a child class of the ExtractorBase
    and obj is not extractors.ExtractorBase  # Avoid capturing the parent class itself.
}

def format_code(row):
    concept_code = row["concept_code"]
    if "_" in concept_code:
        return concept_code.replace("_", ":")
    if row["vocabulary_id"].upper() == 'SNOMED':
        concept_code = f"snomedct:{concept_code}"
    if row["vocabulary_id"].upper() == "NCIt".upper():
        concept_code = f"NCIT:{concept_code}"
    return concept_code

def concept_rows(row):
    concept = {
        "ontology_id": row["vocabulary_id"],
        "concept_code": format_code(row),
    }

    if row["vocabulary_id"] == "NCIt":
        concept["definition"] = row["concept_name"]
    else:
        concept["display"] =row["concept_name"]
    return concept


def write_concept(data: list, output_path: str):
    """Takes unzipped data file and writes it to a JSON file in TermConcept format.

    Arguments:
        data: Unzipped data file.
        output_path: The path to write the JSON file.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as o:
        for chunk in data:
            for row in chunk:
                o.write(json.dumps(concept_rows(row)) + "\n")

def write_vocab(data, output_path):
    """Takes unzipped data file and writes it to a JSON file in TermOntology format.

    Arguments:
        data: Unzipped data file.
        output_path: The path to write the JSON file.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as o:
        for chunk in data:
            for row in chunk:
                o.write(json.dumps(concept_rows(row)) + "\n")

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

        concept_data = list(
            extractor.extract_data(vocabulary_id=vocabulary_id, data_type="CONCEPT", chunk_size=100)
        )
        vocabulary_data = list(
            extractor.extract_data(vocabulary_id=vocabulary_id, data_type="VOCABULARY", chunk_size=100)
        )
        write_concept(concept_data, f"output/{vocabulary_id}_concept.jsonl")

        logging.info(
            f"{vocabulary_id}: {sum(len(chunk) for chunk in concept_data)} concepts, {sum(len(chunk) for chunk in vocabulary_data)} vocabulary rows"
        )

    for extractor in dirs_to_cleanup:
        extractor.__exit__(None, None, None)
