# Persistence and Backup

**Version:** 1.0
**Date:** 2026-11-20
**Status:** DOCUMENTED — no automated backup implemented yet

---

## 1. Storage Inventory

| Store | File / Directory | Technology | Survives Restart |
|---|---|---|---|
| Workflow state | `data/workflows.db` | SQLite 3 WAL | YES |
| Manufacturing plans | `data/plans.db` | SQLite 3 WAL | YES |
| Report history | `data/report_history.db` | SQLite 3 WAL | YES |
| CAD artifact files | `data/artifacts/<sha256>/` | Filesystem | YES |

Data directory location is controlled by the `MACHININGPRO_DATA_DIR` environment
variable. Default: `data/` (relative to the backend working directory).

---

## 2. Backup Status

```
BACKUP_SUPPORTED=MANUAL_ONLY
BACKUP_METHOD=file_copy_sqlite_wal
RESTORE_SUPPORTED=MANUAL_ONLY
RESTORE_METHOD=file_copy_restore
```

No automated backup system is implemented. All databases are single SQLite files
that can be copied safely while the application is running in WAL mode, as long
as the `-wal` and `-shm` sidecar files are copied together with the main `.db` file.

---

## 3. Manual Backup Procedure

### 3.1 Stop-and-Copy (safest)

```sh
# Stop the backend
pkill -f uvicorn

# Copy everything
cp -r data/ data_backup_$(date +%Y%m%d_%H%M%S)/

# Restart
uvicorn backend.api.app:app --host 0.0.0.0 --port 8000
```

### 3.2 Online Copy (WAL mode allows this)

SQLite WAL mode allows readers and one writer to run concurrently. A file copy
while the application is running is safe if you copy all three files for each
database in one shot:

```sh
BACKUP_DIR="data_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
for db in data/workflows.db data/plans.db data/report_history.db; do
    base=$(basename "$db")
    cp "$db" "$BACKUP_DIR/$base"
    cp "${db}-wal" "$BACKUP_DIR/${base}-wal" 2>/dev/null || true
    cp "${db}-shm" "$BACKUP_DIR/${base}-shm" 2>/dev/null || true
done
cp -r data/artifacts/ "$BACKUP_DIR/artifacts/"
```

### 3.3 SQLite Online Backup API

For a consistent snapshot without stopping the server:

```python
import sqlite3

src = sqlite3.connect("data/plans.db")
dst = sqlite3.connect("backup/plans.db")
src.backup(dst, pages=100)
dst.close()
src.close()
```

This uses SQLite's built-in incremental backup API and produces a consistent
snapshot even under concurrent writes.

---

## 4. Restore Procedure

```sh
# Stop the backend
pkill -f uvicorn

# Replace data directory
mv data/ data_broken_$(date +%Y%m%d_%H%M%S)/
cp -r data_backup_YYYYMMDD_HHMMSS/ data/

# Restart
uvicorn backend.api.app:app --host 0.0.0.0 --port 8000
```

**RESTORE_SUPPORTED=MANUAL_ONLY** — no automated restore tooling.

---

## 5. Data Integrity

### 5.1 WAL mode

All SQLite stores are opened with:
```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
```

WAL mode provides:
- Readers do not block writers
- Writers do not block readers
- Crash safety: in-progress transactions are rolled back on restart
- No data loss for committed transactions

### 5.2 Content-addressed artifact storage

CAD files in `ArtifactStore` use SHA-256 content-addressed storage. File
references use the hash as the artifact_id. Duplicate uploads do not create
duplicate files.

### 5.3 Immutable report snapshots

Generated report files are referenced by `artifact_id` (opaque, not a path).
Report metadata records are never modified after creation. If a plan changes,
a new report is generated with a new `report_id` — the old record is preserved.

---

## 6. Future Work

The following backup capabilities are documented as future work:

| Capability | Priority | Notes |
|---|---|---|
| Automated scheduled backup (cron) | HIGH | Copy SQLite files + artifacts |
| Point-in-time recovery | MEDIUM | SQLite WAL archiving |
| Encrypted backup | MEDIUM | For customer CAD data |
| Cloud storage integration | MEDIUM | S3/Azure Blob sync |
| Backup integrity verification | MEDIUM | Hash check after copy |
| Automated restore test | HIGH | Verify backup is usable |

---

## 7. Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MACHININGPRO_DATA_DIR` | `data` | Root directory for all persistent storage |

Change this to point to a persistent volume in Docker/cloud deployments:
```sh
export MACHININGPRO_DATA_DIR=/mnt/persistent/machiningpro_data
```

---

## 8. Security Notes

- SQLite files should not be world-readable (`chmod 600 data/*.db`)
- The `data/` directory should be excluded from version control (already in `.gitignore`)
- CAD artifact files may contain customer intellectual property — treat as sensitive
- No passwords, JWT secrets, or API keys are stored in any database column
- See `docs/operations/SECRETS_INVENTORY.md` for the full secrets audit
