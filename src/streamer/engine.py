import yaml
from sqlalchemy import create_engine

from utils import build_db_url


def get_engine(config_path):
    with open(config_path) as c:
        config = yaml.safe_load(c)
    return create_engine(build_db_url(config))
