FROM postgres:17

# Schema + synthetic seed run automatically (alphabetical order) on first start
# via the official image's /docker-entrypoint-initdb.d mechanism.
COPY 00_schema.sql /docker-entrypoint-initdb.d/00_schema.sql
COPY 01_seed_reference.sql /docker-entrypoint-initdb.d/01_seed_reference.sql
