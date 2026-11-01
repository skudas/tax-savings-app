"""
Encryption/decryption for sensitive financial fields.

Encrypts fields like bank account numbers at rest using Fernet (symmetric encryption).
Requires ENCRYPTION_KEY environment variable (base64-encoded Fernet key).

Generate a key:
    from cryptography.fernet import Fernet
    key = Fernet.generate_key()
    print(key.decode())
"""

import os
from cryptography.fernet import Fernet, InvalidToken
from typing import Optional


class EncryptionManager:
    """Handles encryption and decryption of sensitive fields."""

    def __init__(self):
        """Initialize with key from environment variable."""
        key = os.getenv("ENCRYPTION_KEY")
        if not key:
            raise ValueError(
                "ENCRYPTION_KEY environment variable not set. "
                "Generate one: from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())"
            )

        try:
            self.cipher = Fernet(key.encode() if isinstance(key, str) else key)
        except Exception as e:
            raise ValueError(f"Invalid ENCRYPTION_KEY format: {e}")

    def encrypt(self, plaintext: Optional[str]) -> Optional[str]:
        """
        Encrypt a string.

        Args:
            plaintext: String to encrypt (None returns None)

        Returns:
            Encrypted string (base64-encoded)
        """
        if plaintext is None:
            return None

        encrypted = self.cipher.encrypt(plaintext.encode())
        return encrypted.decode()

    def decrypt(self, ciphertext: Optional[str]) -> Optional[str]:
        """
        Decrypt a string.

        Args:
            ciphertext: Encrypted string (base64-encoded)

        Returns:
            Decrypted plaintext string

        Raises:
            InvalidToken: If decryption fails
        """
        if ciphertext is None:
            return None

        try:
            decrypted = self.cipher.decrypt(ciphertext.encode())
            return decrypted.decode()
        except InvalidToken:
            raise ValueError("Failed to decrypt value - possible tampering or wrong key")


# Global instance
_manager: Optional[EncryptionManager] = None


def get_encryption_manager() -> EncryptionManager:
    """Get or create the global encryption manager."""
    global _manager
    if _manager is None:
        _manager = EncryptionManager()
    return _manager


def encrypt(value: Optional[str]) -> Optional[str]:
    """Encrypt a value using the global manager."""
    return get_encryption_manager().encrypt(value)


def decrypt(value: Optional[str]) -> Optional[str]:
    """Decrypt a value using the global manager."""
    return get_encryption_manager().decrypt(value)
