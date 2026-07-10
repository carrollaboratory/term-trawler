from abc import ABC, abstractmethod
from collections.abc import Generator
from typing import Any, Dict


class ExtractorBase(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def extract_data(self, data_type: Any) -> Generator[Dict[str, Any], None, None]:
        yield {"dict": "something"}

    @abstractmethod
    def __enter__(self):
        print("Opening resource...")
        return self

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        print("Cleaning up resource now!")
        # Return True if you want to suppress an exception, False otherwise
        return False


from .omop import OmopExtractor  # noqa: E402
from .owl import OwlExtractor  # noqa: E402

__all__ = ["ExtractorBase", "OmopExtractor", "OwlExtractor"]
