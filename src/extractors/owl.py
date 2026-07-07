from extractors import SourceConfig

class OwlExtractor(SourceConfig):
    def extract_data(self, data_type):
        print("I am the OWL extractor! Hoot hoot!")
