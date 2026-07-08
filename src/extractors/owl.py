from extractors import ExtractorBase
from typing import Any

class OwlExtractor(ExtractorBase):
    extractor_name = "OWL"
    def extract_data(self, data_type: Any):
        print(f"I am the OWL extractor for {self.config['vocabulary_name']}! Hoot hoot!")
