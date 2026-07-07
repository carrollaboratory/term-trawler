#!/bin/env python
import logging
import sys
from argparse import ArgumentParser  # , FileType
from pathlib import Path

from ttrawler import init_logging
from extraction_loop import extract

def exec(args: list[str] | None = None):
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
        help="Configuration file specifying vocabularies to gather and warehouse for loading."
    )

    args = parser.parse_args(args)

    config_path = Path(args.config)
    if not config_path.exists():
        parser.error(f"{config_path} file not found.")
    # Initialize the logger with whatever the user requested
    init_logging(args.log_level)
    logging.info(f"You have chosen to use: {args}")

    extract(config_path)


if __name__ == "__main__":
    exec()
