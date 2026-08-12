#!/usr/bin/env python3
"""Create and verify a consistent SQLite backup for Remoire.

The script uses SQLite's online backup API so it is safe while the application
is running in WAL mode. A backup is published only after ``PRAGMA quick_check``
passes, then a SHA-256 sidecar is written for later integrity checks.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import sqlite3
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote


BACKUP_PATTERN = re.compile(r"^remoire-(\d{8}T\d{6}Z)\.db$")


def _read_only_uri(path: Path, *, immutable: bool = False) -> str:
    options = "mode=ro&immutable=1" if immutable else "mode=ro"
    return f"file:{quote(str(path.resolve()))}?{options}"


def _remove_sqlite_sidecars(path: Path) -> None:
    for suffix in ("-wal", "-shm", "-journal"):
        Path(f"{path}{suffix}").unlink(missing_ok=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_backup(path: Path) -> dict[str, int | str]:
    """Verify SQLite integrity and return safe, non-content metadata."""
    if not path.is_file():
        raise FileNotFoundError(f"backup does not exist: {path}")

    with sqlite3.connect(_read_only_uri(path, immutable=True), uri=True) as db:
        integrity = db.execute("PRAGMA quick_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite quick_check failed: {integrity}")
        has_memories = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='memories'"
        ).fetchone()
        memory_count = (
            db.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            if has_memories
            else 0
        )
    return {
        "quick_check": integrity,
        "memories": memory_count,
        "size_bytes": path.stat().st_size,
    }


@contextmanager
def _exclusive_lock(backup_dir: Path):
    lock_path = backup_dir / ".remoire-backup.lock"
    with lock_path.open("a", encoding="utf-8") as lock_file:
        os.chmod(lock_path, 0o600)
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("another backup is already running") from exc
        yield


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def prune_expired_backups(
    backup_dir: Path,
    retention_days: int,
    *,
    now: datetime | None = None,
) -> list[str]:
    """Delete only expired files matching Remoire's strict backup filename."""
    if retention_days < 1:
        raise ValueError("retention_days must be at least 1")

    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=retention_days)
    deleted: list[str] = []
    for candidate in backup_dir.iterdir():
        match = BACKUP_PATTERN.fullmatch(candidate.name)
        if not match or not candidate.is_file():
            continue
        created = datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(
            tzinfo=timezone.utc
        )
        if created >= cutoff:
            continue
        checksum = candidate.with_suffix(candidate.suffix + ".sha256")
        candidate.unlink()
        if checksum.is_file():
            checksum.unlink()
        deleted.append(candidate.name)
    return deleted


def create_backup(
    database: Path,
    backup_dir: Path,
    retention_days: int = 30,
    *,
    now: datetime | None = None,
) -> dict[str, object]:
    database = database.expanduser().resolve()
    backup_dir = backup_dir.expanduser().resolve()
    if not database.is_file():
        raise FileNotFoundError(f"database does not exist: {database}")
    if backup_dir == Path("/"):
        raise ValueError("backup_dir cannot be the filesystem root")

    backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(backup_dir, 0o700)
    now = now or datetime.now(timezone.utc)
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = backup_dir / f"remoire-{stamp}.db"
    temporary = backup_dir / f".remoire-{uuid.uuid4().hex}.tmp"
    checksum_path = destination.with_suffix(destination.suffix + ".sha256")
    checksum_temporary = checksum_path.with_name(f".{checksum_path.name}.tmp")

    with _exclusive_lock(backup_dir):
        if destination.exists():
            raise FileExistsError(f"backup already exists: {destination}")
        try:
            with sqlite3.connect(_read_only_uri(database), uri=True) as source:
                with sqlite3.connect(temporary) as target:
                    source.backup(target, pages=256, sleep=0.05)
                    target.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    target.execute("PRAGMA journal_mode=DELETE").fetchone()
                    target.commit()

            _remove_sqlite_sidecars(temporary)

            os.chmod(temporary, 0o600)
            verification = verify_backup(temporary)
            with temporary.open("rb") as handle:
                os.fsync(handle.fileno())
            os.replace(temporary, destination)

            checksum = _sha256(destination)
            checksum_temporary.write_text(
                f"{checksum}  {destination.name}\n", encoding="ascii"
            )
            os.chmod(checksum_temporary, 0o600)
            with checksum_temporary.open("rb") as handle:
                os.fsync(handle.fileno())
            os.replace(checksum_temporary, checksum_path)
            _fsync_directory(backup_dir)

            deleted = prune_expired_backups(
                backup_dir, retention_days, now=now
            )
            return {
                "ok": True,
                "backup": str(destination),
                "checksum": checksum,
                "verification": verification,
                "pruned": deleted,
            }
        finally:
            temporary.unlink(missing_ok=True)
            _remove_sqlite_sidecars(temporary)
            checksum_temporary.unlink(missing_ok=True)


def _parser() -> argparse.ArgumentParser:
    backend_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(
            os.getenv("DATABASE_PATH", backend_dir / "data" / "remoire.db")
        ),
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=Path(os.getenv("BACKUP_DIR", "/root/backups")),
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=int(os.getenv("BACKUP_RETENTION_DAYS", "30")),
    )
    parser.add_argument(
        "--verify",
        type=Path,
        help="verify an existing backup without creating a new one",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.verify:
            result: dict[str, object] = {
                "ok": True,
                "backup": str(args.verify.resolve()),
                "checksum": _sha256(args.verify.resolve()),
                "verification": verify_backup(args.verify.resolve()),
            }
        else:
            result = create_backup(
                args.database, args.backup_dir, args.retention_days
            )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {"ok": False, "error": str(exc), "type": type(exc).__name__},
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
