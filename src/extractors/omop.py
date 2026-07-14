import csv
import tempfile
import zipfile
from collections.abc import Generator
from typing import Any, Dict

from extractors import ExtractorBase


class OmopExtractor(ExtractorBase):
    extractor_name = "OMOP"

    def __init__(self, config: dict):
        super().__init__(config)
        self.filename = config["archive_filename"]

    def __enter__(self):
        self.temp_obj = tempfile.TemporaryDirectory()
        self.temp_dir = self.temp_obj.name
        try:
            with zipfile.ZipFile(self.filename) as zf:
                zf.extractall(self.temp_dir)
                print(
                    f"Zip file extracted to {self.temp_dir}."
                )
                return self
        except zipfile.BadZipfile:
            print(f"OMOP {self.filename} could not be extracted.")
            return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        print("Cleaning up resource now!")
        self.temp_obj.cleanup()
        return False

    def extract_data(
        self, vocabulary_id: str, data_type: str
    ) -> Generator[Dict[str, Any], None, None]:
        upper_vocab = vocabulary_id.upper()
        file_path = f"{self.temp_dir}/{data_type}.csv"
        with open(file_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                if row.get("vocabulary_id", "").upper() == upper_vocab:
                    yield row
