import base64
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.deps import get_current_user
from app.main import app
from app.services.printing import QzSigningError, read_qz_material, sign_qz_request, validate_qz_request


def _material(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    certificate = "-----BEGIN CERTIFICATE-----\nMIIBdemo\n-----END CERTIFICATE-----\n"
    key_path = tmp_path / "private-key.pem"
    key_path.write_text(private_pem)
    cert_path = tmp_path / "digital-certificate.txt"
    cert_path.write_text(certificate)
    return key, private_pem, certificate, key_path, cert_path


def _verify(public_key, signature_b64: str, request: str) -> None:
    public_key.verify(base64.b64decode(signature_b64), request.encode(), padding.PKCS1v15(), hashes.SHA512())


# --- service: signing ------------------------------------------------------


def test_sign_qz_request_is_verifiable_with_the_public_key(tmp_path) -> None:
    key, private_pem, _cert, _kp, _cp = _material(tmp_path)
    signature = sign_qz_request("1234:print:{}", private_pem)
    _verify(key.public_key(), signature, "1234:print:{}")


def test_sign_qz_request_defaults_to_sha512_and_rejects_unknown_algorithm(tmp_path) -> None:
    _key, private_pem, _cert, _kp, _cp = _material(tmp_path)
    assert sign_qz_request("abc", private_pem, "SHA512")
    with pytest.raises(QzSigningError):
        sign_qz_request("abc", private_pem, "MD5")


def test_sign_qz_request_rejects_an_invalid_key() -> None:
    with pytest.raises(QzSigningError):
        sign_qz_request("abc", "not a pem key")
    with pytest.raises(QzSigningError):
        sign_qz_request("abc", "")


# --- service: validation and file access -----------------------------------


def test_validate_qz_request_bounds_the_payload() -> None:
    assert validate_qz_request("a single line request") == "a single line request"
    with pytest.raises(QzSigningError):
        validate_qz_request("")
    with pytest.raises(QzSigningError):
        validate_qz_request("   ")
    with pytest.raises(QzSigningError):
        validate_qz_request("bad\x00byte")
    with pytest.raises(QzSigningError):
        validate_qz_request("x" * 100, max_bytes=10)


def test_read_qz_material_reports_missing_config_and_files(tmp_path) -> None:
    with pytest.raises(QzSigningError):
        read_qz_material(None, label="certificate")
    with pytest.raises(QzSigningError):
        read_qz_material(str(tmp_path / "nope.pem"), label="private key")
    _key, _priv, certificate, _kp, cert_path = _material(tmp_path)
    assert read_qz_material(str(cert_path), label="certificate") == certificate


# --- endpoints (auth overridden, no database needed) -----------------------


@pytest.mark.asyncio
async def test_qz_endpoints_require_authentication() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/api/v1/printing/qz/certificate")).status_code == 401
        assert (await client.post("/api/v1/printing/qz/sign", json={"request": "x"})).status_code == 401


@pytest.mark.asyncio
async def test_qz_certificate_and_sign_round_trip(monkeypatch, tmp_path) -> None:
    key, _priv, certificate, key_path, cert_path = _material(tmp_path)
    monkeypatch.setattr(settings, "qz_print_certificate_path", str(cert_path))
    monkeypatch.setattr(settings, "qz_print_private_key_path", str(key_path))
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="user-1")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            cert_response = await client.get("/api/v1/printing/qz/certificate")
            assert cert_response.status_code == 200
            assert cert_response.text == certificate

            sign_response = await client.post("/api/v1/printing/qz/sign", json={"request": "req-1:{}"})
            assert sign_response.status_code == 200
            body = sign_response.json()
            assert body["algorithm"] == "SHA512"
            _verify(key.public_key(), body["signature"], "req-1:{}")
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_qz_sign_rejects_an_oversized_request(monkeypatch, tmp_path) -> None:
    _key, _priv, _cert, key_path, _cp = _material(tmp_path)
    monkeypatch.setattr(settings, "qz_print_private_key_path", str(key_path))
    monkeypatch.setattr(settings, "qz_print_request_max_bytes", 8)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="user-oversize")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/printing/qz/sign", json={"request": "x" * 32})
            assert response.status_code == 400
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_qz_sign_is_unavailable_when_signing_is_not_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "qz_print_private_key_path", None)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="user-unconfigured")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/printing/qz/sign", json={"request": "req-2:{}"})
            assert response.status_code == 503
    finally:
        app.dependency_overrides.pop(get_current_user, None)
