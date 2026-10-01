set dotenv-load := true
config := "dev.yaml"
chunk_size := "5000"

extract: clear
    uv run trawler -c {{config}} -ch {{chunk_size}}

extract-only:
    uv run trawler -c {{config}} -ch {{chunk_size}}

db:
    sudo -u postgres psql -d term_trawler

clear:
    PGPASSWORD="$PGPASSWORD" psql -h localhost -U postgres -d term_trawler -c "TRUNCATE dev_include_access.term_concept, dev_include_access.term_vocabulary CASCADE;"

drop:
    psql -c "DROP SCHEMA IF EXISTS dev_include_access CASCADE;"

schema:
    psql -c "CREATE SCHEMA IF NOT EXISTS dev_include_access;"
