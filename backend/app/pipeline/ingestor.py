import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.markitdown_client import convert_to_markdown as markitdown_convert
from app.models import ProcessedFile, WatchedFolder
from app.pdf_direct import convert_to_markdown as pdf_direct_convert
from app.pipeline.router import route as get_route
from app.pipeline.scanner import compute_hash, scan

if TYPE_CHECKING:
    from app.docling_client import DoclingClient


def run_pipeline(
    session: Session,
    folders: list[WatchedFolder],
    owner_id: uuid.UUID,
    input_dir: Path,
    docling_client: "DoclingClient | None" = None,
    retry_failed: bool = True,
) -> dict:
    total_processed = total_skipped = total_failed = 0

    logger.info("Sync started — %d folder(s)", len(folders))
    for folder in folders:
        if not folder.enabled:
            continue
        r = _process_folder(session, folder, owner_id, input_dir, docling_client, retry_failed)
        total_processed += r["processed"]
        total_skipped += r["skipped"]
        total_failed += r["failed"]

    logger.info(
        "Sync done — processed=%d skipped=%d failed=%d",
        total_processed, total_skipped, total_failed,
    )
    return {"processed": total_processed, "skipped": total_skipped, "failed": total_failed}


def _process_folder(
    session: Session,
    folder: WatchedFolder,
    owner_id: uuid.UUID,
    input_dir: Path,
    docling_client: "DoclingClient | None",
    retry_failed: bool = True,
) -> dict:
    from app.docling_client import DoclingError

    processed = skipped = failed = 0
    source_dir = Path(folder.host_path)
    files = list(scan(source_dir, recursive=folder.recursive))
    logger.info("Folder %s — %d file(s) found", folder.host_path, len(files))

    for file_path in files:
        try:
            content_hash = compute_hash(file_path)

            existing = (
                session.query(ProcessedFile)
                .filter(
                    ProcessedFile.owner_id == owner_id,
                    ProcessedFile.source_path == str(file_path),
                    ProcessedFile.content_hash == content_hash,
                )
                .first()
            )
            if existing and existing.status == "done":
                logger.debug("SKIP %s (already done)", file_path.name)
                skipped += 1
                continue

            if existing and existing.status == "failed" and not retry_failed:
                logger.debug("SKIP %s (failed, retry_failed=False)", file_path.name)
                skipped += 1
                continue

            route_name = get_route(str(file_path))

            if route_name == "unsupported":
                error_msg = f"Unsupported file type: {file_path.suffix!r}"
                logger.warning("UNSUPPORTED %s — %s", file_path.name, error_msg)
                if existing:
                    existing.status = "failed"
                    existing.error_message = error_msg
                    existing.processed_at = None
                    session.commit()
                else:
                    _save_record(
                        session, owner_id, folder.id, file_path, content_hash,
                        file_path.suffix.lstrip(".") or "unknown", "unsupported",
                        "failed", error_msg,
                    )
                failed += 1
                continue

            logger.info("PROCESSING %s via %s", file_path.name, route_name)
            ext = file_path.suffix
            if existing:
                pf = existing
                pf.status = "processing"
                pf.error_message = None
                pf.dest_path = None
                pf.processed_at = None
                session.commit()
            else:
                pf = _save_record(
                    session, owner_id, folder.id, file_path, content_hash,
                    ext.lstrip(".") or "unknown", route_name, "processing",
                )

            if route_name == "direct":
                try:
                    dest = _copy_direct(file_path, source_dir, input_dir, folder.dest_subdir)
                    pf.dest_path = str(dest)
                    pf.status = "done"
                    pf.processed_at = datetime.now(timezone.utc)
                    session.commit()
                    logger.info("DONE %s → %s", file_path.name, dest)
                    processed += 1
                except OSError as exc:
                    pf.status = "failed"
                    pf.error_message = str(exc)
                    session.commit()
                    logger.error("FAILED %s — %s", file_path.name, exc)
                    failed += 1

            elif route_name == "pdf_direct":
                try:
                    md_content = pdf_direct_convert(str(file_path))
                    dest_name = file_path.stem + ".md"
                    dest = _save_markdown(
                        md_content, dest_name, file_path, source_dir, input_dir, folder.dest_subdir
                    )
                    pf.dest_path = str(dest)
                    pf.status = "done"
                    pf.processed_at = datetime.now(timezone.utc)
                    session.commit()
                    logger.info("DONE %s → %s", file_path.name, dest)
                    processed += 1
                except Exception as exc:
                    pf.status = "failed"
                    pf.error_message = str(exc)
                    session.commit()
                    logger.error("FAILED %s — %s", file_path.name, exc)
                    failed += 1

            elif route_name == "markitdown":
                try:
                    md_content = markitdown_convert(str(file_path))
                    dest_name = file_path.stem + ".md"
                    dest = _save_markdown(
                        md_content, dest_name, file_path, source_dir, input_dir, folder.dest_subdir
                    )
                    pf.dest_path = str(dest)
                    pf.status = "done"
                    pf.processed_at = datetime.now(timezone.utc)
                    session.commit()
                    logger.info("DONE %s → %s", file_path.name, dest)
                    processed += 1
                except Exception as exc:
                    pf.status = "failed"
                    pf.error_message = str(exc)
                    session.commit()
                    logger.error("FAILED %s — %s", file_path.name, exc)
                    failed += 1

            elif route_name == "docling":
                if docling_client is None:
                    pf.status = "failed"
                    pf.error_message = "Docling client not configured"
                    session.commit()
                    logger.error("FAILED %s — Docling client not configured", file_path.name)
                    failed += 1
                    continue
                try:
                    md_content = docling_client.convert(str(file_path))
                    dest_name = file_path.stem + ".md"
                    dest = _save_markdown(
                        md_content, dest_name, file_path, source_dir, input_dir, folder.dest_subdir
                    )
                    pf.dest_path = str(dest)
                    pf.status = "done"
                    pf.processed_at = datetime.now(timezone.utc)
                    session.commit()
                    logger.info("DONE %s → %s", file_path.name, dest)
                    processed += 1
                except DoclingError as exc:
                    pf.status = "failed"
                    pf.error_message = str(exc)
                    session.commit()
                    logger.error("FAILED %s — %s", file_path.name, exc)
                    failed += 1

        except Exception:
            logger.exception("Unexpected error processing %s", file_path)
            session.rollback()
            failed += 1

    return {"processed": processed, "skipped": skipped, "failed": failed}


def _save_record(
    session: Session,
    owner_id: uuid.UUID,
    folder_id: uuid.UUID,
    file_path: Path,
    content_hash: str,
    file_type: str,
    route_name: str,
    status: str,
    error_message: str | None = None,
) -> ProcessedFile:
    pf = ProcessedFile(
        owner_id=owner_id,
        folder_id=folder_id,
        source_path=str(file_path),
        content_hash=content_hash,
        file_type=file_type,
        route=route_name,
        status=status,
        error_message=error_message,
    )
    session.add(pf)
    try:
        session.commit()
    except IntegrityError:
        # Race condition: concurrent sync already inserted this record
        session.rollback()
        return (
            session.query(ProcessedFile)
            .filter(
                ProcessedFile.owner_id == owner_id,
                ProcessedFile.source_path == str(file_path),
                ProcessedFile.content_hash == content_hash,
            )
            .one()
        )
    session.refresh(pf)
    return pf


def _copy_direct(
    file_path: Path,
    source_dir: Path,
    input_dir: Path,
    dest_subdir: str,
) -> Path:
    relative = file_path.relative_to(source_dir)
    dest = input_dir / dest_subdir / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(file_path, dest)
    return dest


def _save_markdown(
    content: str,
    dest_name: str,
    file_path: Path,
    source_dir: Path,
    input_dir: Path,
    dest_subdir: str,
) -> Path:
    relative = file_path.relative_to(source_dir).parent / dest_name
    dest = input_dir / dest_subdir / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    return dest
