import tempfile
import zipfile
from collections.abc import Generator
from typing import Any, Dict

from extractors import ExtractorBase


class OmopExtractor(ExtractorBase):
    extractor_name = "OMOP"

    def __init__(self, config: dict):
        super().__init__(config)
        self.vocabulary_id = config["vocabulary_id"]
        self.filename = config["archive_filename"]

    def __enter__(self):
        self.temp_obj = tempfile.TemporaryDirectory()
        self.temp_dir = self.temp_obj.name
        print(f"Created temporary {self.temp_dir} file.")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        print("Cleaning up resource now!")
        self.temp_obj.cleanup()
        # Return True if you want to suppress an exception, False otherwise
        return False

    def extract_data(self, data_type: Any) -> Generator[Dict[str, Any], None, None]:
        try:
            with zipfile.ZipFile(self.filename) as zf:
                for item in zf.namelist():
                    zf.extract(item, path=self.temp_dir)
                    yield item
            print(
                f"OMOP {self.config['vocabulary_id']} file extracted to {self.temp_dir}"
            )
        except zipfile.BadZipfile:
            print(f"OMOP {self.config['vocabulary_id']} could not be extracted.")
