import base64
import os
import secrets
import struct

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class EncryptionConfigError(RuntimeError):
    """ENCRYPTION_KEY is needed to encrypt or decrypt but is missing or too short."""


MIN_KEY_CHARS = 32


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

    def __init__(self, key: str | None = None) -> None:
        """
        Initialize encryption service.

        Args:
            key: Optional encryption key. If not provided, ENCRYPTION_KEY is read from the
                 environment when the key is first needed. If neither is set, encrypt() and
                 decrypt() raise EncryptionConfigError; there is no random-key or
                 unencrypted fallback.
        """
        self._explicit_key = key
        self._key_cache: bytes | None = None

    @property
    def _key(self) -> bytes:
        """The derived AES key, resolved on first use so startup does not need it."""
        if self._key_cache is None:
            secret = self._explicit_key or os.environ.get("ENCRYPTION_KEY")
            if not secret:
                raise EncryptionConfigError(
                    "ENCRYPTION_KEY is not set. Generate one with "
                    '`python -c "import secrets; print(secrets.token_hex(32))"` '
                    "and set it in the environment."
                )
            if len(secret) < MIN_KEY_CHARS:
                raise EncryptionConfigError(
                    f"ENCRYPTION_KEY must be at least {MIN_KEY_CHARS} characters. Generate one "
                    'with `python -c "import secrets; print(secrets.token_hex(32))"`.'
                )
            self._key_cache = self._derive_key(secret)
        return self._key_cache

    def _derive_key(self, password: str) -> bytes:
        """
        Derive a 256-bit key from a password using PBKDF2.

        This allows using human-readable passwords while still getting
        a cryptographically strong key.
        """
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

        key = self._key  # raises EncryptionConfigError before anything is produced

        # Generate random IV
        iv = secrets.token_bytes(self.IV_LENGTH)

        # Create cipher and encrypt
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(iv, plaintext.encode(), None)

        # Pack: version (1 byte) + IV (12 bytes) + ciphertext
        packed = struct.pack("B", version) + iv + ciphertext

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
        version = struct.unpack("B", packed[:1])[0]

        _ = self._key  # fail with a clear configuration error before parsing further

        if version == 1:
            return self._decrypt_v1(packed[1:])
        else:
            raise ValueError(f"Unknown encryption version: {version}")

    def _decrypt_v1(self, data: bytes) -> str:
        """Decrypt version 1 format."""
        # Extract IV and ciphertext
        iv = data[: self.IV_LENGTH]
        ciphertext = data[self.IV_LENGTH :]

        # Decrypt
        aesgcm = AESGCM(self._key)
        try:
            plaintext = aesgcm.decrypt(iv, ciphertext, None)
        except InvalidTag:
            raise ValueError(
                "Value could not be decrypted: ENCRYPTION_KEY is not the key it was encrypted "
                "with, or the stored data is damaged"
            ) from None

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
        return struct.unpack("B", packed[:1])[0]

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
_default_service: EncryptionService | None = None


def get_encryption_service() -> EncryptionService:
    """Get the default encryption service instance."""
    global _default_service
    if _default_service is None:
        _default_service = EncryptionService()
    return _default_service
