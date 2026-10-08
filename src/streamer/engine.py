import os

import yaml
from sqlalchemy import create_engine


def get_engine(config_path):
    with open(config_path) as c:
        config = yaml.safe_load(c)

    db_uri = os.path.expandvars(config["warehouse"]["db_uri"])
    missing = [
        v
        for v in ("PGUSER", "PGPASSWORD", "PGHOST", "PGPORT", "PGDATABASE")
        if v not in os.environ
    ]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")
    return create_engine(db_uri, future=True)
