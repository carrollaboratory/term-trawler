import logging
from argparse import ArgumentParser  # , FileType
from importlib.metadata import version
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
import sys

from car_utils import setup_logging

logger = logging.getLogger(__name__)


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
        "-c",
        "--config",
        default="config.yaml",
        required=False,
        help="Configuration file specifying vocabularies to load and warehouse for loading.",
    )

    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        parser.error(f"{config_path} file not found.")
    # Initialize the logger with whatever the user requested
    setup_logging(level=args.log_level)

    if args.curie_file is None and args.curie is None:
        print("You must provide either --curie-file or --curie to continue")
        sys.exit(1)

    logger.info(f"You have chosen to use: {args}")


if __name__ == "__main__":
    exec()
