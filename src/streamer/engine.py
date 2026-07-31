import yaml
from sqlalchemy import create_engine


def get_engine(config_path):
    with open(config_path) as c:
        config = yaml.safe_load(c)

    return create_engine(config["warehouse"]["db_uri"], future=True)
