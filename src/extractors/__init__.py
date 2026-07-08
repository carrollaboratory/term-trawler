from abc import ABC, abstractmethod

class ExtractorBase(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def extract_data(self, data_type):
        pass

from .omop import OmopExtractor
from .owl import OwlExtractor

__all__ = ["ExtractorBase", "OmopExtractor", "OwlExtractor"]
