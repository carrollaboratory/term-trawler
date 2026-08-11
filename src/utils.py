PREFIXES = {"SNOMED": "snomedct", "NCIT": "NCIT", "EDAM": "edam"}


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
