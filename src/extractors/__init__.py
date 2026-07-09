from abc import ABC, abstractmethod
from typing import Any


class ExtractorBase(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def extract_data(self, data_type: Any):
        pass

from .omop import OmopExtractor  # noqa: E402
from .owl import OwlExtractor  # noqa: E402

__all__ = ["ExtractorBase", "OmopExtractor", "OwlExtractor"]
