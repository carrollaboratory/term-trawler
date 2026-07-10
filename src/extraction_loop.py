import logging
from pathlib import Path

import yaml

import extractors

EXTRACTORS = {
    getattr(obj, "extractor_name"): obj  # OMOP: obj are your dictionary entries
    for name in extractors.__all__  # iterate over each of your __all__ strings
    if (obj := getattr(extractors, name))  # Unpack the class object from the module
    and issubclass(
        obj, extractors.ExtractorBase
    )  # Confirm that it is a child class of the ExtractorBase
    and obj is not extractors.ExtractorBase  # Avoid capturing the parent class itself.
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
        with extractor_type(vocab) as extractor:
            list(extractor.extract_data(data_type=None))
