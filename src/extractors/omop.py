from extractors import SourceConfig

class OmopExtractor(SourceConfig):
    def extract_data(self, data_type):
        print("I am the OMOP extractor!!")
