#!/bin/env python
import logging
from argparse import ArgumentParser  # , FileType
from pathlib import Path
from extractors import ExtractorBase
from extraction_loop import extract
from ttrawler import init_logging


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
        "-c",
        "--config",
        default="dev.yaml",
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

    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        parser.error(f"{config_path} file not found.")
    # Initialize the logger with whatever the user requested
    init_logging(args.log_level)
    logging.info(f"You have chosen to use: {args}")

    extract(config_path, chunk_size=args.chunk)


if __name__ == "__main__":
    exec()
