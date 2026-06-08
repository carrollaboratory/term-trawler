import logging
import sys

# Rich Logging if rich is installed
if sys.stderr.isatty():
    from rich.console import Console
    from rich.logging import RichHandler
    from rich.traceback import install


def init_logging(loglevel: str | None = None):
    # When we are in the terminal, let's use the rich logging
    if loglevel is None:
        loglevel = "WARN"
    DATEFMT = "%Y-%m-%dT%H:%M:%SZ"
    if sys.stderr.isatty():
        install(show_locals=True)

        handler = RichHandler(
            level=loglevel,
            console=Console(stderr=True),
            show_time=False,
            show_level=True,
            markup=True,
            rich_tracebacks=True,
        )
        FORMAT = "%(message)s"
    else:
        FORMAT = "%(asctime)s\t%(levelname)s\t%(message)s"
        handler = logging.StreamHandler()

    logging.basicConfig(
        level=loglevel, format=FORMAT, datefmt=DATEFMT, handlers=[handler]
    )
