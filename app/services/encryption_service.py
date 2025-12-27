"""
Encryption Service for API Key Storage

Uses AES-256-GCM for authenticated encryption of API keys.
Keys are encrypted before database storage and decrypted only when needed.

Security:
- AES-256-GCM provides both confidentiality and authenticity
- Random IV (nonce) for each encryption operation
- Key derived from ENCRYPTION_KEY environment variable
- Version field for future key rotation support

Usage:
    service = EncryptionService()
    encrypted = service.encrypt("sk-ant-api03-xxx")
    decrypted = service.decrypt(encrypted)
"""

import os
import base64
import secrets
import struct
from typing import Optional

# Import cryptography library for AES-256-GCM
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False


class EncryptionService:
    """
    AES-256-GCM encryption service for secure API key storage.

    Encrypted format (base64):
        [version (1 byte)][IV (12 bytes)][ciphertext + tag]

    The version byte allows for future algorithm changes without breaking
    existing encrypted data.
    """

    CURRENT_VERSION = 1
    IV_LENGTH = 12  # 96 bits recommended for GCM
    KEY_LENGTH = 32  # 256 bits

    # Salt for key derivation (constant, but adds complexity)
    KEY_SALT = b"ai-cost-optimizer-encryption-v1"

    def __init__(self, key: Optional[str] = None):
        """
        Initialize encryption service.

        Args:
            key: Optional encryption key. If not provided, uses ENCRYPTION_KEY
                 environment variable. If that's not set, generates a random key
                 (WARNING: random key means data can't be decrypted after restart).
        """
        if not CRYPTOGRAPHY_AVAILABLE:
            # Fallback to simple encoding if cryptography not installed
            self._use_fallback = True
            self._key = None
            return

        self._use_fallback = False

        if key:
            self._key = self._derive_key(key)
        elif os.environ.get("ENCRYPTION_KEY"):
            self._key = self._derive_key(os.environ["ENCRYPTION_KEY"])
        else:
            # Generate random key (warning: data won't survive restarts)
            self._key = secrets.token_bytes(self.KEY_LENGTH)

    def _derive_key(self, password: str) -> bytes:
        """
        Derive a 256-bit key from a password using PBKDF2.

        This allows using human-readable passwords while still getting
        a cryptographically strong key.
        """
        if not CRYPTOGRAPHY_AVAILABLE:
            # Simple fallback: use first 32 bytes
            return password.encode()[:32].ljust(32, b'\0')

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_LENGTH,
            salt=self.KEY_SALT,
            iterations=100000,  # OWASP recommended minimum
        )
        return kdf.derive(password.encode())

    def encrypt(self, plaintext: str, version: int = None) -> str:
        """
        Encrypt a plaintext string.

        Args:
            plaintext: The string to encrypt
            version: Encryption version (default: current version)

        Returns:
            Base64-encoded encrypted string with version and IV prepended
        """
        if version is None:
            version = self.CURRENT_VERSION

        if self._use_fallback:
            # Fallback: base64 encode (NOT SECURE - just for testing without cryptography)
            return base64.b64encode(
                struct.pack('B', version) + plaintext.encode()
            ).decode()

        # Generate random IV
        iv = secrets.token_bytes(self.IV_LENGTH)

        # Create cipher and encrypt
        aesgcm = AESGCM(self._key)
        ciphertext = aesgcm.encrypt(iv, plaintext.encode(), None)

        # Pack: version (1 byte) + IV (12 bytes) + ciphertext
        packed = struct.pack('B', version) + iv + ciphertext

        return base64.b64encode(packed).decode()

    def decrypt(self, encrypted: str) -> str:
        """
        Decrypt an encrypted string.

        Args:
            encrypted: Base64-encoded encrypted string

        Returns:
            Original plaintext string

        Raises:
            ValueError: If decryption fails (wrong key, corrupted data, etc.)
        """
        packed = base64.b64decode(encrypted)

        # Extract version
        version = struct.unpack('B', packed[:1])[0]

        if self._use_fallback:
            # Fallback: base64 decode (NOT SECURE)
            return packed[1:].decode()

        if version == 1:
            return self._decrypt_v1(packed[1:])
        else:
            raise ValueError(f"Unknown encryption version: {version}")

    def _decrypt_v1(self, data: bytes) -> str:
        """Decrypt version 1 format."""
        # Extract IV and ciphertext
        iv = data[:self.IV_LENGTH]
        ciphertext = data[self.IV_LENGTH:]

        # Decrypt
        aesgcm = AESGCM(self._key)
        plaintext = aesgcm.decrypt(iv, ciphertext, None)

        return plaintext.decode()

    def get_encryption_version(self, encrypted: str) -> int:
        """
        Get the encryption version of an encrypted string.

        Args:
            encrypted: Base64-encoded encrypted string

        Returns:
            Version number
        """
        packed = base64.b64decode(encrypted)
        return struct.unpack('B', packed[:1])[0]

    def get_key_last_four(self, api_key: str) -> str:
        """
        Get the last 4 characters of an API key for display.

        This is the only part of the key that should ever be shown to users.

        Args:
            api_key: The full API key

        Returns:
            Last 4 characters (or full key if shorter than 4 chars)
        """
        if len(api_key) <= 4:
            return api_key
        return api_key[-4:]

    @staticmethod
    def generate_key() -> bytes:
        """
        Generate a new random encryption key.

        Returns:
            32-byte (256-bit) random key
        """
        return secrets.token_bytes(32)

    @staticmethod
    def generate_key_hex() -> str:
        """
        Generate a new random encryption key as hex string.

        Returns:
            64-character hex string (32 bytes = 256 bits)
        """
        return secrets.token_hex(32)


# Singleton instance for convenience
_default_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """Get the default encryption service instance."""
    global _default_service
    if _default_service is None:
        _default_service = EncryptionService()
    return _default_service
