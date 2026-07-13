from collections.abc import Generator
from typing import Any, Dict

from extractors import ExtractorBase


class OwlExtractor(ExtractorBase):
    extractor_name = "OWL"

    def __enter__(self):
        return self
        # Entry point for the context manager

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False
        # What happens when context manager is done

    def extract_data(
        self, vocabulary_id: str, data_type: Any
    ) -> Generator[Dict[str, Any], None, None]:
        print(
            f"I am the OWL extractor for {self.config['vocabulary_name']}! Hoot hoot!"
        )
        yield from ()
        # for word in "this is silly".split():
        #     yield {"dict": "something"}
