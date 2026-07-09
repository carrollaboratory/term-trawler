import tempfile
import zipfile
from typing import Any

from extractors import ExtractorBase


class OmopExtractor(ExtractorBase):
    extractor_name = "OMOP"

    def __init__(self, config: dict):
        super().__init__(config)
        self.vocabulary_id = config["vocabulary_id"]
        self.filename = config["archive_filename"]
        self.temp_dir = tempfile.mkdtemp()

    def extract_data(self, data_type: Any):
        print(f"I am the OMOP extractor for {self.config['vocabulary_id']}")
        with zipfile.ZipFile(self.filename) as zf:
            for item in zf.namelist():
                zf.extract(item, path=self.temp_dir)
                yield item
