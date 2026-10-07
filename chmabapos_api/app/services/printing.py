"""QZ Tray message signing.

QZ Tray removes its security prompt only when each request is signed. The private
key must never reach the browser, so the POS asks this API for the public
certificate and for a signature of the exact request string QZ hands it (see
``docs/native-printing.md``).

The signature is an RSA PKCS#1 v1.5 signature over SHA-512, base64-encoded,
matching https://qz.io/docs/signing. SHA-1 is only for QZ Tray 2.0 and older.
"""

from __future__ import annotations

import base64
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# QZ accepts these spellings; anything else is refused rather than guessed.
_ALLOWED_ALGORITHMS = {
    "SHA1": hashes.SHA1,
    "SHA256": hashes.SHA256,
    "SHA384": hashes.SHA384,
    "SHA512": hashes.SHA512,
}
_DEFAULT_ALGORITHM = "SHA512"


class QzSigningError(RuntimeError):
    """A caller-safe reason QZ signing could not be performed."""


def read_qz_material(path: str | None, *, label: str) -> str:
    """Read a configured certificate/key path, with a clear error when absent."""
    if not path or not str(path).strip():
        raise QzSigningError(f"QZ Tray {label} is not configured")
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as exc:  # missing file, permissions, ...
        raise QzSigningError(f"QZ Tray {label} could not be read") from exc


def validate_qz_request(payload: str, max_bytes: int = 16_384) -> str:
    """Reject anything that is not plausibly a QZ signing request.

    The endpoint signs whatever string it is given, so bound it: an empty payload,
    an embedded NUL, or a payload larger than ``max_bytes`` is refused. This keeps
    the endpoint from being used as a general-purpose signing oracle.
    """
    if not isinstance(payload, str) or not payload.strip():
        raise QzSigningError("QZ request is empty")
    if "\x00" in payload:
        raise QzSigningError("QZ request contains a NUL byte")
    if len(payload.encode("utf-8")) > max_bytes:
        raise QzSigningError("QZ request is too large")
    return payload


def sign_qz_request(request: str, private_key_pem: str, algorithm: str = _DEFAULT_ALGORITHM) -> str:
    """Return the base64 RSA signature QZ expects for ``request``."""
    hash_factory = _ALLOWED_ALGORITHMS.get((algorithm or _DEFAULT_ALGORITHM).upper())
    if hash_factory is None:
        raise QzSigningError("Unsupported QZ signature algorithm")
    try:
        private_key = serialization.load_pem_private_key(private_key_pem.encode("utf-8"), password=None)
        signature = private_key.sign(request.encode("utf-8"), padding.PKCS1v15(), hash_factory())
    except (ValueError, TypeError, NotImplementedError) as exc:
        raise QzSigningError("QZ Tray private key is invalid") from exc
    return base64.b64encode(signature).decode("ascii")
