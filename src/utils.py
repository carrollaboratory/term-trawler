import os

from sqlalchemy.engine import URL, make_url

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
        if concept_id.startswith(("http://", "https://")):
            local_id = concept_id.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
            config_prefix = config.get("prefix", "")

            if config_prefix and local_id.upper().startswith(
                f"{config_prefix.upper()}_"
            ):
                local_id = local_id[len(config_prefix) + 1 :]

            return f"{config_prefix}:{local_id}"
        if config.get("source_type", "").upper() == "OMOP" and "_" in concept_id:
            return concept_id.replace("_", ":")
        effective_prefix = prefix or config.get("prefix", "")
        if "_" in concept_id and prefix:
            embedded_prefix, _, remainder = concept_id.partition("_")
            if embedded_prefix.upper() == prefix.upper():
                return f"{effective_prefix}:{remainder}"
        if ":" not in concept_id:
            prefix = PREFIXES.get(vocabulary_id) or config.get("prefix", "")
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
        return concept_code.split(":", 1)[1]
    return concept_code


def build_db_url(config: dict | None = None):
    if url := os.environ.get("DATABASE_URL"):
        return url
    warehouse = (config or {}).get("warehouse") or {}
    if uri := warehouse.get("db_uri"):
        return os.path.expandvars(uri)
    if service := warehouse.get("service"):
        return f"postgresql:///?service={service}"
    if service := os.environ.get("PGSERVICE"):
        return f"postgresql:///?service={service}"
    missing = [v for v in ("PGUSER", "PGPASSWORD", "PGDATABASE") if v not in os.environ]
    if missing:
        raise RuntimeError(
            "No database connection info found. Set DATABASE_URL, provide "
            f"warehouse.db_uri in the config, or set: {', '.join(missing)}"
        )
    return URL.create(
        "postgresql",
        username=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
        host=os.environ.get("PGHOST", "localhost"),
        port=int(os.environ.get("PGPORT", "5432")),
        database=os.environ["PGDATABASE"],
    ).render_as_string(hide_password=False)
