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

def concept_rows(row):
    return {
        "ontology_id": row["vocabulary_id"],
        "concept_code": row["concept_code"],
        #TODO: Check the display, I think concept_name is the definition, which might be weird.
        "display": row["concept_name"],
        "definition": row["concept_name"]

    }

def write_concept(data, output_path):
    """Takes unzipped data file and writes it to a JSON file.

    Arguments:
        data: Unzipped data file.
        output_path: The path to write the JSON file.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as o:
        for row in data:
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
            extractor.extract_data(vocabulary_id=vocabulary_id, data_type="CONCEPT")
        )
        vocabulary_data = list(
            extractor.extract_data(vocabulary_id=vocabulary_id, data_type="VOCABULARY")
        )
        write_concept(concept_data, f"output/{vocabulary_id}_concept.jsonl")
        logging.info(
            f"{vocabulary_id}: {len(concept_data)} concepts, {len(vocabulary_data)} vocabulary rows"
        )

    for extractor in dirs_to_cleanup:
        extractor.__exit__(None, None, None)
