import json
from collections.abc import Generator
from typing import Any

from extractors import ExtractorBase
from utils import format_code


class FhirExtractor(ExtractorBase):
    extractor_name = "FHIR"

    def __init__(self, config: dict):
        super().__init__(config)
        self.filename = config["archive_filename"]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def get_version(self, vocabulary_id: str) -> str | None:
        return None

    def get_replacement(self, config) -> dict[str, str]:
        return {}

    def extract_data(
        self, vocabulary_id: str, data_type: str
    ) -> Generator[list[dict[str, Any]], None, None]:
        with open(self.filename) as f:
            j = json.load(f)
        if data_type == "VOCABULARY":
            yield [
                {
                    "vocabulary_id": self.config.get("prefix", ""),
                    "vocabulary_name": self.config.get("vocabulary_name", ""),
                    "vocabulary_version": j.get("version", ""),
                }
            ]
        elif data_type == "CONCEPT":
            for c in j.get("concept", []):
                concept = {
                    "concept_curie": format_code(
                        {
                            "concept_code": c.get("code", ""),
                            "vocabulary_id": self.config.get("prefix", ""),
                        },
                        self.config,
                    ),
                    "concept_code": c.get("code", ""),
                    "concept_name": c.get("display", ""),
                    "vocabulary_prefix": self.config.get("prefix", ""),
                    "display": c.get("display", ""),
                    "definition": c.get("definition", ""),
                }
                for p in c.get("property", []):
                    if p.get("code") == "status" and p.get("valueCode") == "retired":
                        concept["invalid_reason"] = "D"
                        break
                yield [concept]
