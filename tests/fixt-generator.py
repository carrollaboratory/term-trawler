from csv import DictReader, DictWriter
from pathlib import Path

filename = Path("src/tests/fixtures/concepts.csv")

input = Path("src/tests/fixtures/curies_to_fix.csv")


with filename.open("r", encoding="utf-8") as f:
    reader = DictReader(f)

    test_rows = []
    for row in reader:
        test_rows.append(
            {
                "curie": row["concept_curie"],
                "prefix": "",
                "expected_curie": row["concept_curie"],
                "expected_display": row["display"],
                "vocabulary_prefix": row["vocabulary_prefix"],
            }
        )

    with input.open("w", newline="", encoding="utf-8") as outf:
        writer = DictWriter(
            outf,
            fieldnames=[
                "curie",
                "prefix",
                "expected_curie",
                "expected_display",
                "vocabulary_prefix",
            ],
        )
        writer.writeheader()
        writer.writerows(test_rows)
