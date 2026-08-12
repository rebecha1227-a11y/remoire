import hashlib
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.backup_database import (
    create_backup,
    prune_expired_backups,
    verify_backup,
)


class BackupDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.database = self.root / "source.db"
        self.backups = self.root / "backups"
        with sqlite3.connect(self.database) as db:
            db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE memories (id TEXT PRIMARY KEY, content TEXT NOT NULL);
                INSERT INTO memories VALUES ('one', 'first');
                INSERT INTO memories VALUES ('two', 'second');
                """
            )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_create_backup_is_consistent_and_checksummed(self):
        now = datetime(2026, 8, 12, 5, 0, tzinfo=timezone.utc)
        result = create_backup(self.database, self.backups, now=now)

        backup = Path(result["backup"])
        checksum_file = backup.with_suffix(".db.sha256")
        expected_hash = hashlib.sha256(backup.read_bytes()).hexdigest()

        self.assertTrue(backup.is_file())
        self.assertEqual(result["verification"]["quick_check"], "ok")
        self.assertEqual(result["verification"]["memories"], 2)
        self.assertEqual(result["checksum"], expected_hash)
        self.assertEqual(
            checksum_file.read_text(encoding="ascii"),
            f"{expected_hash}  {backup.name}\n",
        )
        self.assertEqual(os.stat(backup).st_mode & 0o777, 0o600)
        self.assertEqual(os.stat(self.backups).st_mode & 0o777, 0o700)
        self.assertFalse(Path(f"{backup}-wal").exists())
        self.assertFalse(Path(f"{backup}-shm").exists())
        self.assertFalse(any(self.backups.glob(".remoire-*.tmp*")))

    def test_backup_remains_readable_after_source_changes(self):
        result = create_backup(self.database, self.backups)
        with sqlite3.connect(self.database) as db:
            db.execute("DELETE FROM memories")

        verification = verify_backup(Path(result["backup"]))
        self.assertEqual(verification["memories"], 2)

    def test_prune_deletes_only_expired_strictly_named_backups(self):
        now = datetime(2026, 8, 12, tzinfo=timezone.utc)
        old_stamp = (now - timedelta(days=31)).strftime("%Y%m%dT%H%M%SZ")
        recent_stamp = (now - timedelta(days=2)).strftime("%Y%m%dT%H%M%SZ")
        self.backups.mkdir()
        old = self.backups / f"remoire-{old_stamp}.db"
        recent = self.backups / f"remoire-{recent_stamp}.db"
        unrelated = self.backups / "keep-me.db"
        for path in (old, recent, unrelated):
            path.write_bytes(b"test")
        old.with_suffix(".db.sha256").write_text("hash", encoding="ascii")

        deleted = prune_expired_backups(self.backups, 30, now=now)

        self.assertEqual(deleted, [old.name])
        self.assertFalse(old.exists())
        self.assertFalse(old.with_suffix(".db.sha256").exists())
        self.assertTrue(recent.exists())
        self.assertTrue(unrelated.exists())

    def test_verify_rejects_corrupt_database(self):
        corrupt = self.root / "corrupt.db"
        corrupt.write_bytes(b"not sqlite")
        with self.assertRaises(sqlite3.DatabaseError):
            verify_backup(corrupt)


if __name__ == "__main__":
    unittest.main()
