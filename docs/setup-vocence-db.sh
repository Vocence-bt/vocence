#!/usr/bin/env bash
# Create PostgreSQL user and database for Vocence
# Run with: sudo -u postgres ./setup-vocence-db.sh
# Or: sudo -u postgres bash setup-vocence-db.sh

set -e

USER_NAME="vocence"
DB_NAME="vocence"
USER_PASSWORD="vocence"

psql -v ON_ERROR_STOP=1 <<EOF
CREATE USER ${USER_NAME} WITH PASSWORD '${USER_PASSWORD}';
CREATE DATABASE ${DB_NAME} OWNER ${USER_NAME};
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${USER_NAME};
\c ${DB_NAME}
GRANT ALL ON SCHEMA public TO ${USER_NAME};
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ${USER_NAME};
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ${USER_NAME};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${USER_NAME};
EOF

echo "Done. User '${USER_NAME}', database '${DB_NAME}' created. Password: ${USER_PASSWORD}"
echo "Connect with: psql -h localhost -U ${USER_NAME} -d ${DB_NAME}"
echo "Or: postgresql://${USER_NAME}:${USER_PASSWORD}@localhost:5432/${DB_NAME}"
