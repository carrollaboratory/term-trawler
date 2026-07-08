from extractors import ExtractorBase
import yaml

class OmopExtractor(ExtractorBase):
    def extract_data(self, data_type):
        print(f"I am the OMOP extractor for {self.config['vocabulary_id']}")
