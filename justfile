set dotenv-load := true
container := "term_trawler"
config := "dev.yaml"
chunk_size := "5000"

# Install dependencies in pyproject.toml and create the PostgreSQL db.
# Must have POSTGRES variables set in .env file.
setup:
    just init
    just db-setup

# Run the extract sript
extract vocab="" report="" format="":
    uv run trawler -c {{config}} -ch {{chunk_size}} {{ if vocab != "" { "--vocab " + quote(vocab) } else { "" } }} {{ if report != "" { "--report " + quote(report) } else { "" } }} {{ if format != "" { "--format " + quote(format) } else { "" } }}

init:
    uv sync

# Create the postgreSQL database with Docker. Must have POSTGRES variables set in .env file.
# If Docker container already exists, it starts it.
db-setup:
    if docker container inspect {{container}} >/dev/null 2>&1; then \
        just db-start; \
    else \
        just db-up; \
        just db-wait; \
        just db-schema; \
    fi

# Create the postgreSQL database with Docker. Must have POSTGRES variables set in .env file.
db-up:
    docker run --name {{container}} \
        -e POSTGRES_USER="$PGUSER" \
        -e POSTGRES_PASSWORD="$PGPASSWORD" \
        -e POSTGRES_DB="$PGDATABASE" \
        -p "${PGPORT:-5432}:5432" \
        -v term-trawler-pgdata:/var/lib/postgresql/data \
        -d postgres:16

# Start the Docker container
db-start:
    docker start {{container}}

db-wait:
    until docker exec {{container}} pg_isready -U "$PGUSER" -d "$PGDATABASE"; do sleep 1; done

# Create schema for PostgreSQL db.
db-schema:
    psql -c "CREATE SCHEMA IF NOT EXISTS dev_include_access;"

# Stop the docker container
db-stop:
    docker stop {{container}}

# Access the db
db:
    sudo -u postgres psql -d term_trawler



# ========THE FOLLOWING COMMANDS ARE ONLY FOR USE IN DEVELOPMENT===========

clear:
    PGPASSWORD="$PGPASSWORD" psql -h localhost -U postgres -d term_trawler -c "TRUNCATE dev_include_access.concept, dev_include_access.vocabulary, dev_include_access.deprecatedconcept CASCADE;"

drop:
    psql -c "DROP SCHEMA IF EXISTS dev_include_access CASCADE;"
