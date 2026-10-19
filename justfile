set dotenv-load := true
config := "dev.yaml"
chunk_size := "5000"


extract report="":
    uv run trawler -c {{config}} -ch {{chunk_size}} {{ if report != "" { "--report " + quote(report) } else { "" } }}

db:
    sudo -u postgres psql -d term_trawler

clear:
    PGPASSWORD="$PGPASSWORD" psql -h localhost -U postgres -d term_trawler -c "TRUNCATE dev_include_access.concept, dev_include_access.vocabulary, dev_include_access.deprecatedconcept CASCADE;"

drop:
    psql -c "DROP SCHEMA IF EXISTS dev_include_access CASCADE;"

schema:
    psql -c "CREATE SCHEMA IF NOT EXISTS dev_include_access;"
