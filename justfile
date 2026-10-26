set dotenv-load := true
config := "dev.yaml"
chunk_size := "5000"

extract vocab="" report="" format="":
    uv run trawler -c {{config}} -ch {{chunk_size}} {{ if vocab != "" { "--vocab " + quote(vocab) } else { "" } }} {{ if report != "" { "--report " + quote(report) } else { "" } }} {{ if format != "" { "--format " + quote(format) } else { "" } }}

db:
    sudo -u postgres psql -d term_trawler

clear:
    PGPASSWORD="$PGPASSWORD" psql -h localhost -U postgres -d term_trawler -c "TRUNCATE dev_include_access.concept, dev_include_access.vocabulary, dev_include_access.deprecatedconcept CASCADE;"

drop:
    psql -c "DROP SCHEMA IF EXISTS dev_include_access CASCADE;"

schema:
    psql -c "CREATE SCHEMA IF NOT EXISTS dev_include_access;"
