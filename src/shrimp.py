import contextlib
import io
import logging
import sys
from argparse import ArgumentParser  # , FileType
from csv import DictReader
from csv import writer as CsvWriter
from importlib.metadata import version
from itertools import batched
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from common_access_model.datamodel.common_access_model_sqla import Concept, Vocabulary
from dotenv import load_dotenv
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session
from yaml import safe_load

from extraction_loop import get_loader

load_dotenv()

from car_utils import setup_logging

# May be a URL or a local path (tests point this at a fixture)
synonym_source = "https://raw.githubusercontent.com/carrollaboratory/term-wyrm/refs/heads/main/src/term_wyrm/data/vocabulary_details.csv"
_config = None

logger = logging.getLogger(__name__)


def get_config(filename: Path | str | None = None) -> dict:
    global _config

    if _config is None:
        assert filename is not None, (
            "The first call to get_config must have the filename"
        )
        filename = Path(filename)
        if not filename.exists():
            logger.error(f"'{filename}' was not found.")
            sys.exit(1)
        with filename.open("r", encoding="utf-8") as infile:
            _config = safe_load(infile)
    return _config


_prefix_lookup = None


@contextlib.contextmanager
def db_session(config: dict):
    loader = get_loader(config)
    with loader.create_session() as session:
        yield session


def _read_text(source: str | Path) -> str:
    if urlparse(str(source)).scheme in ("http", "https"):
        with urlopen(str(source)) as response:
            return response.read().decode("utf-8")
    return Path(source).read_text(encoding="utf-8")


def get_prefix_lookup(source: str | Path | None = None) -> dict[str, str]:
    """Return lowercased synonym -> preferred prefix to allow cleaner transformation of Curies"""
    global _prefix_lookup

    if _prefix_lookup is None:
        _prefix_lookup = {}
        reader = DictReader(io.StringIO(_read_text(source or synonym_source)))

        for line in reader:
            prefix = line["prefix"]

            # Add the self reference to switching cleaner
            _prefix_lookup[prefix.lower()] = prefix

            for syn in line["synonym"].split(","):
                if syn.strip():
                    _prefix_lookup[syn.strip().lower()] = prefix
    return _prefix_lookup


_harmony_log = {}


def parse_curie_file(
    filename: str | Path | None,
    harmonize: bool = False,
    delimiter: str = ",",
    quotechar: str = '"',
) -> list[str]:
    "read curies from CSV file with header 'curie' and an optional 'prefix' column"

    curie_list = []
    if filename is not None:
        with Path(filename).open("r", encoding="utf-8") as infile:
            reader = DictReader(infile, delimiter=delimiter, quotechar=quotechar)

            for line in reader:
                curie = (line.get("curie") or "").strip()
                if not curie:
                    continue
                if harmonize:
                    curie = harmonize_curie(curie, line.get("prefix"))

                curie_list.append(curie)

    return curie_list


def harmonize_curie(curie: str, prefix: str | None = None) -> str:
    """Harmonize a term. If you know a column's type (by synonym is fine) this will return the Curie using the preferred prefix whether or not it is prefixed."""

    global _harmony_log
    pref_lookup = get_prefix_lookup()

    code = curie.strip()
    prefix = (prefix or "").strip() or None
    if ":" in code:
        embedded, code = code.split(":", 1)
        # An explicit prefix wins over whatever was embedded in the curie
        prefix = prefix or embedded
    if not prefix:
        raise ValueError(f"Unable to harmonize codes without a valid prefix: {curie!r}")
    try:
        new_prefix = pref_lookup[prefix.strip().lower()]
    except KeyError:
        raise ValueError(f"Unknown prefix {prefix!r} for curie {curie!r}") from None
    new_curie = f"{new_prefix}:{code.strip()}"

    # Log the transformation so we can output the transform as a CSV
    _harmony_log[new_curie] = [curie, prefix, new_curie]

    return new_curie


def find_concepts(
    session: Session, curies: list[str], batch_size: int = 1000
) -> tuple[dict[str, Concept], dict[str, Vocabulary]]:
    """Look up curies in the Concept table along with the Vocabularies they belong to.

    Returns (curie -> Concept, vocabulary_prefix -> Vocabulary). Curies that aren't in
    the database are simply absent from the first dict."""
    matched_concepts = {}  # curie -> Concept entry
    vocabulary_prefixes = set()

    for chunk in batched(sorted(set(curies)), batch_size):
        stmt = select(Concept).where(Concept.concept_curie.in_(chunk))
        for concept in session.scalars(stmt):
            matched_concepts[concept.concept_curie] = concept
            vocabulary_prefixes.add(concept.vocabulary_prefix)

    stmt = select(Vocabulary).where(
        Vocabulary.vocabulary_prefix.in_(sorted(vocabulary_prefixes))
    )
    vocabularies = {v.vocabulary_prefix: v for v in session.scalars(stmt)}

    return matched_concepts, vocabularies


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
        action="store_true",
        help="Rewrite curie prefixes (and synonyms) to the preferred prefix before lookup.",
    )
    parser.add_argument(
        "-c",
        "--config",
        default="config.yaml",
        required=False,
        help="Configuration file specifying vocabularies to load and warehouse for loading.",
    )
    parser.add_argument(
        "-o",
        "--outdir",
        required=True,
        help="Directory where output CSVs will be written such as 'output/study_id/'  ",
    )

    args = parser.parse_args()

    # Initialize the logger with whatever the user requested
    setup_logging(level=args.log_level)

    config = get_config(args.config)

    if args.curie_file is None and args.curie is None:
        print("You must provide either --curie-file or --curie to continue")
        sys.exit(1)

    logger.info(f"You have chosen to use: {args}")

    # For now, I'm going to assume we'll always harmonize the curies even if
    # the user is confident they are good
    curie_list = parse_curie_file(
        args.curie_file, harmonize=True
    )  # harmonize=args.harmonize_prefix)
    if args.curie is not None:
        for curie in args.curie.split(","):
            curie = curie.strip()
            if curie:
                curie_list.append(
                    harmonize_curie(curie) if args.harmonize_prefix else curie
                )

    with db_session(config) as session:
        concepts, vocabularies = find_concepts(session, curie_list)

    missing = sorted(set(curie_list) - set(concepts))
    if missing:
        logger.warning(f"{len(missing)} curie(s) not found in the database: {missing}")
    logger.info(
        f"Found {len(concepts)} concept(s) across {len(vocabularies)} vocabularies"
    )

    outputdir = Path(args.outdir)
    outputdir.mkdir(parents=True, exist_ok=True)
    missing_terms = set(curie_list) - set(list(concepts.keys()))
    if len(missing_terms) > 0:
        with (outputdir / "unmatched_curies.csv").open("wt", encoding="utf-8") as outf:
            writer = CsvWriter(outf, delimiter=",", quotechar='"')
            writer.writerow(["curie", "prefix", "harmonized_curie"])

            for term in missing_terms:
                # [curie, prefix, new_curie]
                writer.writerow(_harmony_log[term])

    # Harmony Mapping - [curie, prefix, new_curie]
    if len(_harmony_log) > 0:
        with (outputdir / "curie_harmonization.csv").open(
            "wt", encoding="utf-8"
        ) as outf:
            writer = CsvWriter(outf, delimiter=",", quotechar='"')
            writer.writerow(["curie", "prefix", "harmonized_curie"])

            for term in _harmony_log.values():
                # [curie, prefix, new_curie]
                writer.writerow(term)

    # Concepts
    mapper = inspect(Concept)
    model_headers = [column.key for column in mapper.column_attrs]
    with (outputdir / "concepts.csv").open("wt", encoding="utf-8") as outf:
        writer = CsvWriter(outf, delimiter=",", quotechar='"')
        writer.writerow(model_headers)

        for concept in concepts.values():
            writer.writerow([getattr(concept, col) for col in model_headers])

    # Vocabularies
    mapper = inspect(Vocabulary)
    model_headers = [column.key for column in mapper.column_attrs]
    with (outputdir / "vocabulary.csv").open("wt", encoding="utf-8") as outf:
        writer = CsvWriter(outf, delimiter=",", quotechar='"')
        writer.writerow(model_headers)

        for vocab in vocabularies.values():
            writer.writerow([getattr(vocab, col) for col in model_headers])


if __name__ == "__main__":
    exec()
