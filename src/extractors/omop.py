from extractors import SourceConfig
import yaml

class OmopExtractor(SourceConfig):
    def extract_data(self, data_type):
        print(f"I am the OMOP extractor for {self.config['vocabulary_id']}")
