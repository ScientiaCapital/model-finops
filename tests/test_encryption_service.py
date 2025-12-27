"""
TDD Tests for Encryption Service (RED Phase)

Test AES-256-GCM encryption for API key storage.
Written BEFORE implementation (TDD approach).
"""

import pytest
import os
from unittest.mock import patch


class TestEncryptionService:
    """Test encryption service for API key storage."""

    def test_encrypt_returns_encrypted_string(self):
        """Encryption should return a non-empty encrypted string."""
        from app.services.encryption_service import EncryptionService
        service = EncryptionService()

        plaintext = "sk-ant-api03-WpxBupWjWFUU-xxx"
        encrypted = service.encrypt(plaintext)

        assert encrypted is not None
        assert len(encrypted) > 0
        assert encrypted != plaintext

    def test_decrypt_returns_original(self):
        """Decryption should return the original plaintext."""
        from app.services.encryption_service import EncryptionService
        service = EncryptionService()

        plaintext = "sk-ant-api03-WpxBupWjWFUU-xxx"
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)

        assert decrypted == plaintext

    def test_encrypt_produces_different_output_each_time(self):
        """Same plaintext should produce different ciphertext (due to random IV)."""
        from app.services.encryption_service import EncryptionService
        service = EncryptionService()

        plaintext = "sk-ant-api03-xxx"
        encrypted1 = service.encrypt(plaintext)
        encrypted2 = service.encrypt(plaintext)

        assert encrypted1 != encrypted2  # Different IVs

    def test_decrypt_wrong_key_fails(self):
        """Decryption with wrong key should fail."""
        from app.services.encryption_service import EncryptionService

        service1 = EncryptionService(key="key1-" + "a" * 26)  # 32 bytes
        service2 = EncryptionService(key="key2-" + "b" * 26)  # Different key

        plaintext = "sk-ant-api03-xxx"
        encrypted = service1.encrypt(plaintext)

        with pytest.raises(Exception):  # Should fail with auth error
            service2.decrypt(encrypted)

    def test_uses_environment_key_by_default(self):
        """Service should use ENCRYPTION_KEY from environment."""
        from app.services.encryption_service import EncryptionService

        test_key = "test-encryption-key-32bytes!"
        with patch.dict(os.environ, {"ENCRYPTION_KEY": test_key}):
            service = EncryptionService()
            plaintext = "test-api-key"
            encrypted = service.encrypt(plaintext)
            decrypted = service.decrypt(encrypted)
            assert decrypted == plaintext

    def test_generates_key_if_not_provided(self):
        """Service should work even without environment key (generates one)."""
        from app.services.encryption_service import EncryptionService

        with patch.dict(os.environ, {}, clear=True):
            # Remove ENCRYPTION_KEY if present
            os.environ.pop("ENCRYPTION_KEY", None)

            service = EncryptionService()
            plaintext = "sk-ant-api03-xxx"
            encrypted = service.encrypt(plaintext)
            decrypted = service.decrypt(encrypted)
            assert decrypted == plaintext

    def test_get_key_last_four(self):
        """Should extract last 4 characters for display."""
        from app.services.encryption_service import EncryptionService
        service = EncryptionService()

        api_key = "sk-ant-api03-WpxBupWjWFUU-ABCD"
        last_four = service.get_key_last_four(api_key)

        assert last_four == "ABCD"

    def test_get_key_last_four_short_key(self):
        """Handle keys shorter than 4 characters."""
        from app.services.encryption_service import EncryptionService
        service = EncryptionService()

        api_key = "AB"
        last_four = service.get_key_last_four(api_key)

        assert last_four == "AB"  # Return full key if shorter

    def test_encrypt_empty_string(self):
        """Should handle empty string."""
        from app.services.encryption_service import EncryptionService
        service = EncryptionService()

        encrypted = service.encrypt("")
        decrypted = service.decrypt(encrypted)
        assert decrypted == ""

    def test_encrypt_unicode(self):
        """Should handle unicode characters."""
        from app.services.encryption_service import EncryptionService
        service = EncryptionService()

        plaintext = "sk-测试-api-🔑"
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)
        assert decrypted == plaintext


class TestEncryptionKeyManagement:
    """Test encryption key generation and validation."""

    def test_generate_key(self):
        """Should generate a valid 32-byte key."""
        from app.services.encryption_service import EncryptionService

        key = EncryptionService.generate_key()
        assert len(key) == 32

    def test_key_is_random(self):
        """Generated keys should be random."""
        from app.services.encryption_service import EncryptionService

        key1 = EncryptionService.generate_key()
        key2 = EncryptionService.generate_key()
        assert key1 != key2


class TestEncryptionVersioning:
    """Test encryption version support for key rotation."""

    def test_encrypt_with_version(self):
        """Encrypted data should include version for future rotation."""
        from app.services.encryption_service import EncryptionService
        service = EncryptionService()

        plaintext = "sk-ant-api03-xxx"
        encrypted = service.encrypt(plaintext)

        # Version should be embedded in the encrypted payload
        version = service.get_encryption_version(encrypted)
        assert version == 1  # Current version

    def test_decrypt_legacy_format(self):
        """Should handle decryption of data encrypted with older versions."""
        from app.services.encryption_service import EncryptionService
        service = EncryptionService()

        # This test ensures forward compatibility when we add new encryption versions
        plaintext = "sk-ant-api03-xxx"
        encrypted_v1 = service.encrypt(plaintext, version=1)
        decrypted = service.decrypt(encrypted_v1)
        assert decrypted == plaintext
