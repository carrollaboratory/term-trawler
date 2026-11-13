import contextlib
import logging
import sys
from argparse import ArgumentParser  # , FileType
from csv import DictReader
from importlib.metadata import version
from pathlib import Path

from dotenv import load_dotenv
from yaml import safe_load

from extraction_loop import get_loader
from sqlalchemy import select
from sqlalchemy.orm import Session
from itertools import batched
load_dotenv()

from car_utils import open_archive_buffer, setup_logging

synonym_source = Path("https://raw.githubusercontent.com/carrollaboratory/term-wyrm/refs/heads/main/src/term_wyrm/data/vocabulary_details.csv")
_config = None

logger = logging.getLogger(__name__)


def get_config(filename: Path | None = None) -> dict[str, str]:
    global _config

    if _config is None:
        assert filename is not None, (
            "The first call to get_config must have the filename"
        )
        if not filename.exists:
            logger.error(f"'{filename}' was not found.")
            sys.exit(1)
        _config = safe_load(str(filename))
    return _config


_prefix_lookup = None


@contextlib.contextmanager
def db_session(config: dict[str, str], chunk_size: int):
    loader = get_loader(config)
    # Stolen from Yelena's code. I don't think I need them
    # db_engine = get_engine(config)
    # I doubt I'll need this
    # ExtractorBase.chunk_size = chunk_size
    # Base.metadata.create_all(db_engine)
    yield loader.create_session()


def get_prefix_lookup() -> dict[str, str]:
    """Return synonym -> prefix to allow cleaner transformation of Curies"""
    global _prefix_lookup

    if _prefix_lookup is None:
        _prefix_lookup = {}

        with synonym_source.open('r', encoding='utf-8') as infile:
            reader = DictReader(infile, delimiter=",", quotechar='"')

            for line in reader:
                prefix = line["prefix"]

                # Add the self reference to switching cleaner
                _prefix_lookup[prefix] = prefix

                for syn in line["synonym"].split(","):
                    _prefix_lookup[syn] = prefix
    return _prefix_lookup


_harmony_log = {}


def parse_curie_file(
    filename: str | None,
    harmonize: bool = False,
    delimiter: str = ",",
    quotechar: str = '"',
) -> list[str]:
    "read curies from CSV file with header 'curie' and an optional 'prefix' column"

    curie_list = []
    if filename is not None:
        with Path(filename).open('r', encoding='utf-8') as infile:
            reader = DictReader(infile, delimiter=delimiter, quotechar=quotechar)

            for line in reader:
                curie = line.get("curie")
                if not curie:
                    continue
                if harmonize:
                    curie = harmonize_curie(curie, line.get("prefix"))

                curie_list.append(curie)

    return curie_list


def harmonize_curie(curie: str, prefix: str | None = None) -> str:
    """Harmonize a term. If you know a column's type (by synonym is fine) this will return the Curie using the preferred prefix whether or not it is prefixed."""

    pref_lookup = get_prefix_lookup()

    code = curie
    if ":" in code:
        parts = code.split(":")
        if prefix is None:
            prefix, code = parts[0], ":".join(parts[1:])
        else:
            code = ":".join(parts[1:])
    assert prefix, f"Unable to harmonize codes without a valid prefix: {curie}"
    new_prefix = pref_lookup[prefix]
    new_curie = f"{new_prefix}:{code}"

    # Log the transformation so we can output the transform as a CSV
    _harmony_log[curie] = [curie, prefix, new_curie]

    return new_curie


def exec():
    parser = ArgumentParser(
        prog="shrimp-net",
        description="""Sifting through the net for a smaller catch.""",
    )
    parser.add_argument(
        "-log",
        "--log-level",
        choices=["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level tolerated (default is INFO)",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {version('term-trawler')}"
    )
    parser.add_argument(
        "--curie-file", type=str, help="File containing Curies separated by newline"
    )
    parser.add_argument(
        "--curie",
        required=False,
        type=str,
        help="Comma separated list of Curies if you don't need an entire file's worth.",
    )
    parser.add_argument(
        "--harmonize-prefix",
    )
    parser.add_argument(
        "-c",
        "--config",
        default="config.yaml",
        required=False,
        help="Configuration file specifying vocabularies to load and warehouse for loading.",
    )

    args = parser.parse_args()

    # Initialize the logger with whatever the user requested
    setup_logging(level=args.log_level)

    config = get_config(args.config)

    if args.curie_file is None and args.curie is None:
        print("You must provide either --curie-file or --curie to continue")
        sys.exit(1)

    curie_list = parse_curie_file(args.curie_file)
    if args.curie is not None:
        for curie in args.curie.split(","):
            curie_list.append(harmonize_curie(curie))

    logger.info(f"You have chosen to use: {args}")


def find_concepts(curies:list[str], config:dict[str, str], batch_size:int = 1000):
    vocabularies = []
    concepts = []

    unique_curies = list(set(curies))
    matched_concepts = {} # curie -> Concept entry
    vocabularies = {} # vocabulary_prefix -> Vocabulary entry

    dbloader = get_loader(config)
    Vocabulary = dbloader.get_model("Vocabulary")
    Concept = dbloader.get_model("Concept")

    vocabulary_prefixes = set()

    with dbloader.create_session() as sess:
        for chunk in batched(unique_curies, batch_size):
            stmt = sess.query(Concept).where(Concept.concept_curie.in(curies))
            for concept in sess.scalars(stmt):
                matched_concepts[concept.concept_curie] = concept
                vocabulary_prefixes.add(concept.vocabulary_prefix)

        vocabulary_prefixes = list(vocabulary_prefixes)
        # Now let's get the vocabularies
        stmt = sess.query(Vocabulary).where(Vocabulary.vocabulary_prefix.in(vocabulary_prefixes))
        vocabularies = {v.vocabulary_prefix: v for v in sess.scalars(stmt)}





if __name__ == "__main__":
    exec()
