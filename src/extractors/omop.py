from typing import Any

from extractors import ExtractorBase


class OmopExtractor(ExtractorBase):
    extractor_name = "OMOP"

    def extract_data(self, data_type: Any):
        print(f"I am the OMOP extractor for {self.config['vocabulary_id']}")
