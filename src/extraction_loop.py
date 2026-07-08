import yaml
from extractors.omop import OmopExtractor
from extractors.owl import OwlExtractor
import logging
from pathlib import Path


EXTRACTORS = {
    "OMOP": OmopExtractor,
    "OWL": OwlExtractor
}

def extract(config_path: Path):
    """Iterates over the 'vocabularies' property in the config file and runs
    the appropriate extractor script based on source_type.

    Arguments:
        config_path: The specified config file to iterate.
    """
    with open(config_path) as c:
        config = yaml.safe_load(c)

    for vocab in config["vocabularies"]:
        source_type = vocab["source_type"]
        extractor_type = EXTRACTORS.get(source_type.upper())
        if extractor_type is None:
            logging.warning(f"{source_type} is not a valid source type.")
            continue

        extractor = extractor_type(vocab)
        extractor.extract_data(data_type=None)
