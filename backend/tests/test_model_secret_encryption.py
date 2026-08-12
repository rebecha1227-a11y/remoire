import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet

from app import database
from app.services import model_settings_service


class ModelSecretEncryptionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_path = database.DATABASE_PATH
        database.DATABASE_PATH = str(Path(self.tempdir.name) / "model-secrets.db")
        await database.init_db()

    async def asyncTearDown(self):
        database.DATABASE_PATH = self.original_path
        self.tempdir.cleanup()

    async def test_new_preset_is_encrypted_at_rest_and_decrypted_for_runtime(self):
        key = Fernet.generate_key().decode("ascii")
        secret = "sk-private-model-key"

        with patch.object(model_settings_service, "MODEL_SECRET_ENCRYPTION_KEYS", [key]):
            public = await model_settings_service.create_preset({
                "nickname": "私有模型",
                "provider": "openai-compatible",
                "api_key": secret,
                "base_url": "https://api.example.com/v1",
                "model_name": "example-model",
            })
            runtime = await model_settings_service.get_preset(public["id"])

        async with database.get_db() as db:
            async with db.execute("SELECT api_key FROM model_presets WHERE id = ?", (public["id"],)) as cur:
                stored = (await cur.fetchone())["api_key"]

        self.assertEqual(public["api_key"], "********")
        self.assertEqual(runtime["api_key"], secret)
        self.assertTrue(stored.startswith("fernet:v1:"))
        self.assertNotIn(secret, stored)

    async def test_startup_migration_encrypts_legacy_plaintext_once(self):
        key = Fernet.generate_key().decode("ascii")
        async with database.get_db() as db:
            await db.execute(
                """INSERT INTO model_presets
                   (id, nickname, provider, api_key, base_url, model_name, created_at, updated_at)
                   VALUES ('legacy', '旧配置', 'openai-compatible', 'sk-legacy',
                           'https://api.example.com/v1', 'example-model', 'now', 'now')"""
            )
            await db.commit()

        with patch.object(model_settings_service, "MODEL_SECRET_ENCRYPTION_KEYS", [key]):
            first = await model_settings_service.migrate_preset_secrets()
            second = await model_settings_service.migrate_preset_secrets()
            runtime = await model_settings_service.get_preset("legacy")

        async with database.get_db() as db:
            async with db.execute("SELECT api_key FROM model_presets WHERE id = 'legacy'") as cur:
                stored = (await cur.fetchone())["api_key"]

        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        self.assertEqual(runtime["api_key"], "sk-legacy")
        self.assertTrue(stored.startswith("fernet:v1:"))

    def test_encrypted_secret_fails_closed_without_the_server_key(self):
        key = Fernet.generate_key().decode("ascii")
        with patch.object(model_settings_service, "MODEL_SECRET_ENCRYPTION_KEYS", [key]):
            encrypted = model_settings_service._encrypt_api_key("sk-private")

        with patch.object(model_settings_service, "MODEL_SECRET_ENCRYPTION_KEYS", []):
            with self.assertRaises(model_settings_service.SecretEncryptionError):
                model_settings_service._decrypt_api_key(encrypted)

    def test_required_encryption_rejects_missing_server_key(self):
        with patch.object(model_settings_service, "MODEL_SECRET_ENCRYPTION_KEYS", []), patch.object(
            model_settings_service, "MODEL_SECRET_ENCRYPTION_REQUIRED", True
        ):
            with self.assertRaises(model_settings_service.SecretEncryptionError):
                model_settings_service._encrypt_api_key("sk-must-not-be-plaintext")

    def test_rotation_rewraps_old_token_with_primary_key(self):
        old_key = Fernet.generate_key().decode("ascii")
        new_key = Fernet.generate_key().decode("ascii")
        with patch.object(model_settings_service, "MODEL_SECRET_ENCRYPTION_KEYS", [old_key]):
            old_token = model_settings_service._encrypt_api_key("sk-rotate-me")

        with patch.object(model_settings_service, "MODEL_SECRET_ENCRYPTION_KEYS", [new_key, old_key]):
            rotated = model_settings_service._normalize_stored_api_key(old_token)
            self.assertEqual(model_settings_service._decrypt_api_key(rotated), "sk-rotate-me")

        self.assertNotEqual(rotated, old_token)
        with patch.object(model_settings_service, "MODEL_SECRET_ENCRYPTION_KEYS", [new_key]):
            self.assertEqual(model_settings_service._decrypt_api_key(rotated), "sk-rotate-me")


if __name__ == "__main__":
    unittest.main()
