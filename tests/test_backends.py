"""End-to-end trawler and shrimp-basket runs against the file-based backends.

The LinkML loader patches the common access model's tables in place (names and
schema) once per process, so each run happens in a subprocess to keep the
backends from bleeding into each other or into the other tests.
"""

import csv
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from sqlalchemy import create_engine, text

from extraction_loop import get_backend, get_schema_name

FIXTURES = Path(__file__).parent / "fixtures"
BIN = Path(sys.executable).parent
PREFIX = "TRAWLTEST"


@pytest.mark.parametrize(
    "url,backend",
    [
        ("postgresql+psycopg2://u:p@localhost:5432/db", "postgresql"),
        ("postgresql:///?service=trawler", "postgresql"),
        ("duckdb:///terms.duckdb", "duckdb"),
        ("sqlite:///terms.db", "sqlite"),
    ],
)
def test_get_backend(url, backend):
    assert get_backend(url) == backend


def test_get_backend_unsupported():
    with pytest.raises(ValueError, match="Unsupported database"):
        get_backend("mysql://u:p@localhost/db")


def test_get_schema_name():
    custom = {"warehouse": {"schema": "terms"}}
    assert get_schema_name({}, "postgresql") == "dev_include_access"
    assert get_schema_name(custom, "duckdb") == "terms"
    assert get_schema_name(custom, "sqlite") is None


def run(cmd: str, *args, db_url: str):
    # DATABASE_URL wins over the config's db_uri, so pin it in case it's set in .env
    env = {**os.environ, "DATABASE_URL": db_url}
    result = subprocess.run(
        [str(BIN / cmd), *map(str, args)], env=env, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.mark.parametrize("backend,schema", [("sqlite", None), ("duckdb", "trawl")])
def test_trawl_and_shrimp(tmp_path, backend, schema):
    db_url = f"{backend}:///{tmp_path / f'terms.{backend}'}"
    config = {
        "warehouse": {"db_uri": db_url, "schema": "trawl"},
        "vocabularies": [
            {
                "vocabulary_id": PREFIX,
                "vocabulary_name": "Trawler Test",
                "description": "Test vocabulary",
                "prefix": PREFIX,
                "fhir_system": "http://example.org/fhir/CodeSystem/trawler-test",
                "vocabulary_uri": "http://example.org/trawler-test#[code]",
                "source_filename": str(FIXTURES / "fhir-codesystem.json"),
                "source_type": "FHIR",
            }
        ],
    }
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.safe_dump(config))

    # Twice, to make sure the upserts and table creation are rerunnable
    for _ in range(2):
        run("trawler", "-c", config_file, db_url=db_url)

    qualify = f"{schema}." if schema else ""
    engine = create_engine(db_url)
    with engine.connect() as conn:
        concepts = conn.execute(
            text(f"SELECT concept_curie, display FROM {qualify}concept ORDER BY 1")
        ).all()
        deprecated = conn.execute(
            text(f"SELECT concept_curie, deprecation_type FROM {qualify}deprecatedconcept")
        ).all()
        vocab = conn.execute(
            text(f"SELECT vocabulary_prefix, version FROM {qualify}vocabulary")
        ).all()
    engine.dispose()

    assert [c for c, _ in concepts] == [
        f"{PREFIX}:{code}" for code in ("harpoon", "net", "shrimp", "trawl")
    ]
    assert deprecated == [(f"{PREFIX}:harpoon", "D")]
    assert vocab == [(PREFIX, "0.1.0")]

    outdir = tmp_path / "basket"
    run(
        "shrimp-basket",
        "-c", config_file,
        "--curie", f"{PREFIX}:net,{PREFIX}:shrimp,{PREFIX}:lobster",
        "--outdir", outdir,
        db_url=db_url,
    )

    assert {r["concept_curie"] for r in read_csv(outdir / "concepts.csv")} == {
        f"{PREFIX}:net",
        f"{PREFIX}:shrimp",
    }
    assert [r["vocabulary_prefix"] for r in read_csv(outdir / "vocabulary.csv")] == [
        PREFIX
    ]
    assert read_csv(outdir / "unmatched_curies.csv") == [
        {
            "curie": f"{PREFIX}:lobster",
            "prefix": "",
            "harmonized_curie": f"{PREFIX}:lobster",
        }
    ]
