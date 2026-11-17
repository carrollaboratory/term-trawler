"""Tests for shrimp-basket: curie harmonization and concept lookup.

Nothing here touches the network or Postgres: the prefix synonyms come from a
fixture copy of term-wyrm's vocabulary_details.csv, and the concept lookup runs
against an in-memory SQLite database built from the common access model.
"""

from csv import DictReader
from pathlib import Path

import pytest
from common_access_model.datamodel.common_access_model_sqla import (
    Base,
    Concept,
    Vocabulary,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import shrimp

FIXTURES = Path(__file__).parent / "fixtures"

# Synonyms that term-wyrm doesn't (yet) know about
UNKNOWN_SYNONYMS: set[str] = set()


def read_csv(name: str) -> list[dict[str, str]]:
    with (FIXTURES / name).open(encoding="utf-8") as f:
        return list(DictReader(f))


CURIES_TO_FIX = read_csv("curies_to_fix.csv")


def _case_id(row):
    return f"{row['curie']!r}/{row['prefix']!r}"


@pytest.fixture(autouse=True)
def local_synonyms(monkeypatch):
    """Point the prefix lookup at the fixture file and reset its cache."""
    monkeypatch.setattr(shrimp, "synonym_source", FIXTURES / "vocabulary_synonyms.csv")
    monkeypatch.setattr(shrimp, "_prefix_lookup", None)
    monkeypatch.setattr(shrimp, "_harmony_log", {})


def _harmonize_params():
    for row in CURIES_TO_FIX:
        embedded = row["curie"].strip().split(":", 1)[0]
        marks = []
        if embedded in UNKNOWN_SYNONYMS:
            marks.append(
                pytest.mark.xfail(
                    raises=ValueError,
                    strict=True,
                    reason=f"{embedded} isn't a synonym in term-wyrm",
                )
            )
        yield pytest.param(row, marks=marks, id=_case_id(row))


@pytest.mark.parametrize("row", list(_harmonize_params()))
def test_harmonize_curie(row):
    assert (
        shrimp.harmonize_curie(row["curie"], row["prefix"] or None)
        == row["expected_curie"]
    )


def test_harmonize_empty_prefix_column_is_ignored():
    # DictReader hands back "" for an empty prefix column
    assert shrimp.harmonize_curie("HPO:0001171", "") == "HP:0001171"


def test_harmonize_requires_a_prefix():
    with pytest.raises(ValueError, match="without a valid prefix"):
        shrimp.harmonize_curie("0000001")


def test_harmonize_unknown_prefix():
    with pytest.raises(ValueError, match="Unknown prefix"):
        shrimp.harmonize_curie("NOTREAL:123")


def test_harmonize_logs_transformations():
    shrimp.harmonize_curie("hpo:0002018")
    assert shrimp._harmony_log["hpo:0002018"] == ["hpo:0002018", "hpo", "HP:0002018"]


def test_parse_curie_file_raw():
    curies = shrimp.parse_curie_file(FIXTURES / "curie_list.csv")
    assert len(curies) == len(CURIES_TO_FIX)
    # Whitespace is trimmed even without harmonization
    assert "HP:0001067" in curies
    assert "HP:0001169" in curies


def test_parse_curie_file_harmonized(tmp_path):
    # Drop the rows we know can't be harmonized yet
    rows = [
        r
        for r in CURIES_TO_FIX
        if r["curie"].split(":", 1)[0].strip() not in UNKNOWN_SYNONYMS
    ]
    curie_file = tmp_path / "curies.csv"
    curie_file.write_text(
        "curie,prefix\n" + "".join(f'"{r["curie"]}",{r["prefix"]}\n' for r in rows)
    )
    assert shrimp.parse_curie_file(curie_file, harmonize=True) == [
        r["expected_curie"] for r in rows
    ]


def test_parse_curie_file_none():
    assert shrimp.parse_curie_file(None) == []


@pytest.fixture
def session():
    """In-memory SQLite db loaded with the fixture vocabularies and concepts."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as sess:
        sess.add_all(
            Vocabulary(**{k: v or None for k, v in row.items()})
            for row in read_csv("vocabularies.csv")
        )
        for row in read_csv("concepts.csv"):
            row = {k: v or None for k, v in row.items()}
            if row["concept_id"] is not None:
                row["concept_id"] = int(row["concept_id"])
            sess.add(Concept(**row))
        sess.commit()
        yield sess
    engine.dispose()


@pytest.mark.parametrize("batch_size", [1000, 7])
def test_find_concepts(session, batch_size):
    expected = {r["expected_curie"]: r for r in CURIES_TO_FIX}

    concepts, vocabularies = shrimp.find_concepts(
        session, list(expected), batch_size=batch_size
    )

    assert set(concepts) == set(expected)
    for curie, concept in concepts.items():
        assert concept.display == expected[curie]["expected_display"]
        assert concept.vocabulary_prefix == expected[curie]["vocabulary_prefix"]
    assert set(vocabularies) == {"HP", "MONDO", "snomedct"}


def test_find_concepts_missing_and_duplicates(session):
    concepts, vocabularies = shrimp.find_concepts(
        session, ["HP:0000001", "HP:0000001", "HP:9999999"]
    )
    assert list(concepts) == ["HP:0000001"]
    assert list(vocabularies) == ["HP"]


def test_find_concepts_empty(session):
    assert shrimp.find_concepts(session, []) == ({}, {})
