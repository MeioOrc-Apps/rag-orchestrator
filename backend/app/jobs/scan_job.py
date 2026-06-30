import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Chunk, File, WatchedFolder
from app.pipeline.scanner import compute_hash, scan

logger = logging.getLogger(__name__)


def run_scan(db: Session, folders: list[WatchedFolder]) -> dict:
    total = {"scanned": 0, "inserted": 0, "updated": 0, "deleted": 0, "skipped": 0}
    for folder in folders:
        if not folder.enabled:
            continue
        r = _scan_folder(db, folder)
        for k, v in r.items():
            total[k] += v
    return total


def _scan_folder(db: Session, folder: WatchedFolder) -> dict:
    source_dir = Path(folder.host_path)
    domain = folder.dest_subdir

    files_on_disk = list(scan(source_dir, recursive=folder.recursive))
    paths_on_disk = {str(p) for p in files_on_disk}

    db_files = (
        db.query(File)
        .filter(
            File.path.like(f"{folder.host_path}/%"),
            File.deleted_at.is_(None),
        )
        .all()
    )
    db_by_path = {f.path: f for f in db_files}

    inserted = updated = deleted = skipped = 0

    for file_path in files_on_disk:
        path_str = str(file_path)
        current_hash = compute_hash(file_path)
        size = file_path.stat().st_size

        if path_str in db_by_path:
            existing = db_by_path[path_str]
            if existing.file_hash == current_hash:
                skipped += 1
            else:
                _mark_chunks_deleted(db, existing)
                existing.file_hash = current_hash
                existing.file_size_bytes = size
                existing.parse_status = "pending"
                existing.parse_error = None
                existing.updated_at = datetime.now(timezone.utc)
                db.commit()
                updated += 1
                logger.info("UPDATED %s", file_path.name)
        else:
            file_row = File(
                path=path_str,
                filename=file_path.name,
                domain=domain,
                file_hash=current_hash,
                file_size_bytes=size,
            )
            db.add(file_row)
            db.commit()
            inserted += 1
            logger.info("INSERTED %s (domain=%s)", file_path.name, domain)

    for path_str, file_row in db_by_path.items():
        if path_str not in paths_on_disk:
            _mark_chunks_deleted(db, file_row)
            file_row.deleted_at = datetime.now(timezone.utc)
            file_row.updated_at = datetime.now(timezone.utc)
            db.commit()
            deleted += 1
            logger.info("SOFT-DELETED %s", file_row.filename)

    return {
        "scanned": len(files_on_disk),
        "inserted": inserted,
        "updated": updated,
        "deleted": deleted,
        "skipped": skipped,
    }


def _mark_chunks_deleted(db: Session, file_row: File) -> None:
    db.query(Chunk).filter(
        Chunk.file_id == file_row.id,
        Chunk.index_status != "deleted",
    ).update({"index_status": "deleted"})
    db.commit()
