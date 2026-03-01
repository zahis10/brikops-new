#!/bin/bash
set -euo pipefail

DB_NAME="${DB_NAME:-contractor_ops}"
BACKUP_DIR="${BACKUP_DIR:-/home/runner/workspace/.data/backups}"
MONGO_PORT="${MONGO_PORT:-27017}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

usage() {
    echo "Usage: $0 {backup|restore|list|verify} [backup_name]"
    echo ""
    echo "Commands:"
    echo "  backup              Create a new backup"
    echo "  restore <name>      Restore from a backup (dry-run by default, add --confirm to execute)"
    echo "  list                List available backups"
    echo "  verify <name>       Verify backup integrity"
    exit 1
}

do_backup() {
    local backup_path="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}"
    mkdir -p "$backup_path"

    echo "[BACKUP] Starting backup of ${DB_NAME} to ${backup_path}"
    mongodump --host 127.0.0.1 --port "$MONGO_PORT" --db "$DB_NAME" --out "$backup_path" 2>&1

    local uploads_src="/home/runner/workspace/backend/uploads"
    if [ -d "$uploads_src" ]; then
        echo "[BACKUP] Backing up uploads directory..."
        cp -r "$uploads_src" "${backup_path}/uploads_snapshot"
        local file_count=$(find "${backup_path}/uploads_snapshot" -type f | wc -l)
        echo "[BACKUP] Backed up ${file_count} attachment files"
    fi

    echo "[BACKUP] Backup complete: ${backup_path}"
    echo "[BACKUP] Collections:"
    ls -la "${backup_path}/${DB_NAME}/" 2>/dev/null | grep -E "\.bson$" | awk '{print "  " $NF " (" $5 " bytes)"}'
}

do_restore() {
    local backup_name="${1:-}"
    local confirm="${2:-}"

    if [ -z "$backup_name" ]; then
        echo "[RESTORE] Error: Please specify a backup name. Use '$0 list' to see available backups."
        exit 1
    fi

    local backup_path="${BACKUP_DIR}/${backup_name}"
    if [ ! -d "$backup_path" ]; then
        echo "[RESTORE] Error: Backup not found at ${backup_path}"
        exit 1
    fi

    if [ "$confirm" != "--confirm" ]; then
        echo "[RESTORE] DRY RUN - Would restore from: ${backup_path}"
        echo "[RESTORE] Collections to restore:"
        ls "${backup_path}/${DB_NAME}/" 2>/dev/null | grep -E "\.bson$" | sed 's/.bson$//' | while read col; do
            echo "  - ${col}"
        done
        if [ -d "${backup_path}/uploads_snapshot" ]; then
            local file_count=$(find "${backup_path}/uploads_snapshot" -type f | wc -l)
            echo "[RESTORE] Uploads snapshot: ${file_count} files"
        fi
        echo ""
        echo "[RESTORE] To execute restore, run: $0 restore ${backup_name} --confirm"
        return 0
    fi

    echo "[RESTORE] LIVE RESTORE from: ${backup_path}"
    mongorestore --host 127.0.0.1 --port "$MONGO_PORT" --db "$DB_NAME" --drop "${backup_path}/${DB_NAME}/" 2>&1
    echo "[RESTORE] Database restore complete"

    if [ -d "${backup_path}/uploads_snapshot" ]; then
        echo "[RESTORE] Restoring uploads..."
        cp -r "${backup_path}/uploads_snapshot/"* /home/runner/workspace/backend/uploads/ 2>/dev/null || true
        echo "[RESTORE] Uploads restored"
    fi
}

do_list() {
    echo "[LIST] Available backups in ${BACKUP_DIR}:"
    if [ ! -d "$BACKUP_DIR" ]; then
        echo "  (no backups directory)"
        return
    fi
    ls -1d "${BACKUP_DIR}/${DB_NAME}_"* 2>/dev/null | while read dir; do
        local name=$(basename "$dir")
        local size=$(du -sh "$dir" 2>/dev/null | awk '{print $1}')
        echo "  ${name} (${size})"
    done
}

do_verify() {
    local backup_name="${1:-}"
    if [ -z "$backup_name" ]; then
        echo "[VERIFY] Error: Please specify a backup name."
        exit 1
    fi
    local backup_path="${BACKUP_DIR}/${backup_name}"
    if [ ! -d "$backup_path" ]; then
        echo "[VERIFY] Error: Backup not found at ${backup_path}"
        exit 1
    fi

    echo "[VERIFY] Checking backup: ${backup_name}"
    local bson_count=$(find "${backup_path}/${DB_NAME}" -name "*.bson" 2>/dev/null | wc -l)
    local meta_count=$(find "${backup_path}/${DB_NAME}" -name "*.metadata.json" 2>/dev/null | wc -l)
    echo "  BSON files: ${bson_count}"
    echo "  Metadata files: ${meta_count}"

    local all_ok=true
    for bson_file in "${backup_path}/${DB_NAME}/"*.bson; do
        local size=$(stat -c%s "$bson_file" 2>/dev/null || echo "0")
        local name=$(basename "$bson_file")
        if [ "$size" -gt 0 ]; then
            echo "  ${name}: ${size} bytes [OK]"
        else
            echo "  ${name}: EMPTY [WARN]"
        fi
    done

    if [ -d "${backup_path}/uploads_snapshot" ]; then
        local ucount=$(find "${backup_path}/uploads_snapshot" -type f | wc -l)
        echo "  Uploads snapshot: ${ucount} files [OK]"
    fi
    echo "[VERIFY] Integrity check complete"
}

case "${1:-}" in
    backup)  do_backup ;;
    restore) do_restore "${2:-}" "${3:-}" ;;
    list)    do_list ;;
    verify)  do_verify "${2:-}" ;;
    *)       usage ;;
esac
