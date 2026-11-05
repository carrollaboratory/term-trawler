#!/bin/env python
import logging
from argparse import ArgumentParser  # , FileType
from importlib.metadata import version
from pathlib import Path

from car_utils import setup_logging

from extraction_loop import extract
from extractors import ExtractorBase

logger = logging.getLogger(__name__)


def exec():
    parser = ArgumentParser(
        prog="term-trawler",
        description="""Trawling the depths of the internet for terminology catches of the day.""",
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
        "-c",
        "--config",
        default="config.yaml",
        required=False,
        help="Configuration file specifying vocabularies to load and warehouse for loading.",
    )
    parser.add_argument(
        "-ch",
        "--chunk",
        default=ExtractorBase.chunk_size,
        required=False,
        help="The number of rows processed at a time",
    )
    parser.add_argument(
        "-r",
        "--report",
        default=None,
        required=False,
        type=Path,
        help="The term count report is written to the file specified",
    )
    parser.add_argument(
        "-f",
        "--format",
        default="table",
        type=str.lower,
        choices=["table", "tsv", "csv"],
        required=False,
        help="The format of the term count report (table, tsv, csv).",
    )
    parser.add_argument(
        "-v",
        "--vocab",
        default=None,
        required=False,
        help="Comma-separated prefixes or vocabulary_ids to extract",
    )

    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        parser.error(f"{config_path} file not found.")
    # Initialize the logger with whatever the user requested
    setup_logging(level=args.log_level)
    logger.info(f"You have chosen to use: {args}")
    extract(
        config_path,
        chunk_size=args.chunk,
        report_path=args.report,
        extract_vocab=args.vocab,
        format=args.format,
    )


if __name__ == "__main__":
    exec()
