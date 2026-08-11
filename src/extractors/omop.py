import csv
import tempfile
import zipfile
from collections.abc import Generator
from typing import Any

from extractors import ExtractorBase
from utils import format_code


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
                print(f"Zip file extracted to {self.temp_dir}.")
                return self
        except zipfile.BadZipfile:
            print(f"OMOP {self.filename} could not be extracted.")
            return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        print("Cleaning up resource now!")
        self.temp_obj.cleanup()
        return False

    def get_version(self, vocabulary_id: str) -> str | None:
        for chunk in self.extract_data(
            vocabulary_id=vocabulary_id,
            data_type="VOCABULARY",
        ):
            for row in chunk:
                return row.get("vocabulary_version")
        return None

    def get_replacement(self, config) -> dict[str, str]:
        concept_rows = {}

        # Build concept_id -> CONCEPT row lookup
        for chunk in self.extract_data(
            vocabulary_id="",
            data_type="CONCEPT",
        ):
            for row in chunk:
                concept_id = row.get("concept_id")
                if concept_id:
                    concept_rows[concept_id] = row

        replacement = {}

        for chunk in self.extract_data(
            vocabulary_id="",
            data_type="CONCEPT_RELATIONSHIP",
        ):
            for row in chunk:
                if row.get("relationship_id") == "Concept replaced by":
                    old_id = row.get("concept_id_1")
                    new_id = row.get("concept_id_2")

                    if old_id and new_id:
                        replacement_row = concept_rows.get(new_id)

                        if replacement_row:
                            replacement_curie = format_code(
                                replacement_row,
                                config,
                            )
                            replacement[old_id] = replacement_curie or "OMOP:0"
        return replacement

    def extract_data(
        self, vocabulary_id: str, data_type: str
    ) -> Generator[list[dict[str, Any]], None, None]:
        chunk = []
        upper_vocab = vocabulary_id.upper() if vocabulary_id else None
        file_path = f"{self.temp_dir}/{data_type}.csv"
        with open(file_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                if (
                    upper_vocab is None
                    or row.get("vocabulary_id", "").upper() == upper_vocab
                ):
                    chunk.append(row)
                    if len(chunk) == ExtractorBase.chunk_size:
                        yield chunk
                        chunk = []
            if chunk:
                yield chunk
