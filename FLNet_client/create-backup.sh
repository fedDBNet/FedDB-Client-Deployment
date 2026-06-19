#!/usr/bin/env bash
set -euo pipefail

# 1. Get the absolute path of the directory this script (and docker-compose.yml) is in
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"

# Safety check
if [ ! -f "$COMPOSE_FILE" ]; then
  echo "Error: docker-compose.yml not found at $COMPOSE_FILE" >&2
  exit 1
fi

# Set folder name pattern to 'backup_YYYY-MM-DD_HH-MM-SS'
BACKUP_DIR="$SCRIPT_DIR/backups/backup_$(date +%Y-%m-%d_%H-%M-%S)"
DUMP_DIR="$BACKUP_DIR/db_dumps"

mkdir -p "$DUMP_DIR"

echo "Creating fully portable backup in $BACKUP_DIR"

# 2. Copy all current project contents directly into the backup folder root
# Excludes the 'backups' folder to prevent copying old backups into the new one
rsync -a --exclude='backups/' "$SCRIPT_DIR/" "$BACKUP_DIR/"

# 3. Run database dumps into the designated 'db_dumps' subdirectory
# Ensure the database containers are running before executing the dumps
if ! docker compose -f "$COMPOSE_FILE" ps --services --filter "status=running" | grep -qE 'local-learning-api-db|orch-api-db|keycloak-postgres'; then
  echo "Error: One or more database containers are not running. Please start them before running this backup script." >&2
  exit 1
fi

docker compose -f "$COMPOSE_FILE" exec -T local-learning-api-db \
  pg_dump -U user -d local-learning-management \
  > "$DUMP_DIR/local-learning-api-db.sql"

docker compose -f "$COMPOSE_FILE" exec -T orch-api-db \
  pg_dump -U user -d local-learning-management \
  > "$DUMP_DIR/orch-api-db.sql"

docker compose -f "$COMPOSE_FILE" exec -T keycloak-postgres \
  pg_dump -U keycloak -d keycloak \
  > "$DUMP_DIR/keycloak-db.sql"

# 4. Write out the completely independent restore-backup.sh script
echo "Generating self-contained restore script..."
cat << 'EOF' > "$BACKUP_DIR/restore-backup.sh"
#!/usr/bin/env bash
set -euo pipefail

# Since this script runs from the backup root, the current directory IS the project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.yml"
DUMP_DIR="$PROJECT_ROOT/db_dumps"

echo "--> Running portable restore inside: $PROJECT_ROOT"

# Safety check
if [ ! -f "$COMPOSE_FILE" ]; then
  echo "Error: docker-compose.yml not found at $COMPOSE_FILE" >&2
  exit 1
fi

# Verify SQL dumps exist in the designated subdirectory
for file in \
  "$DUMP_DIR/local-learning-api-db.sql" \
  "$DUMP_DIR/orch-api-db.sql" \
  "$DUMP_DIR/keycloak-db.sql"; do
  if [ ! -f "$file" ]; then
    echo "Error: Missing database backup file: $file" >&2
    exit 1
  fi
done

# Stop services, start DBs, and import SQL data using local compose file
echo "--> Stopping services that use the databases..."
docker compose -f "$COMPOSE_FILE" stop local-learning-api orch-api keycloak instance-manager-frontend controller

echo "--> Starting database containers..."
docker compose -f "$COMPOSE_FILE" up -d local-learning-api-db orch-api-db keycloak-postgres

echo "Waiting for databases to initialize..."
sleep 3

echo "--> Restoring local learning database..."
docker compose -f "$COMPOSE_FILE" exec -T local-learning-api-db \
  psql -q -U user -d local-learning-management \
  < "$DUMP_DIR/local-learning-api-db.sql"

echo "--> Restoring orchestration database..."
docker compose -f "$COMPOSE_FILE" exec -T orch-api-db \
  psql -q -U user -d local-learning-management \
  < "$DUMP_DIR/orch-api-db.sql"

echo "--> Restoring Keycloak database..."
docker compose -f "$COMPOSE_FILE" exec -T keycloak-postgres \
  psql -q -U keycloak -d keycloak \
  < "$DUMP_DIR/keycloak-db.sql"

printf "\nSUCCESS: Full restore completed contextually inside: %s\n" "$PROJECT_ROOT"
EOF

# 5. Make the restore script executable
chmod +x "$BACKUP_DIR/restore-backup.sh"

printf "Backup completed: %s\n" "$BACKUP_DIR"
