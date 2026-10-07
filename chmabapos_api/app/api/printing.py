"""QZ Tray signing endpoints.

The POS fetches the public certificate and asks this API to sign each QZ print
request with the server-held private key, which is what lets QZ Tray print
without a security prompt. Both endpoints require an authenticated operator; the
sign endpoint also bounds the request size and the request rate so it cannot be
used as a general-purpose signing oracle. See ``docs/native-printing.md``.
"""

from __future__ import annotations

from collections import defaultdict, deque
from time import monotonic

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.config import settings
from app.deps import get_current_user
from app.models import User
from app.schemas import QzSignRead, QzSignRequest
from app.services.printing import QzSigningError, read_qz_material, sign_qz_request, validate_qz_request

router = APIRouter(prefix="/printing", tags=["printing"])

# Every QZ print call is signed, so a busy register signs several requests a
# minute. The window is generous but bounded, and in-process (a multi-worker
# deployment would want a shared counter).
_SIGN_WINDOW_SECONDS = 60
_sign_calls: dict[str, deque[float]] = defaultdict(deque)


def _enforce_sign_rate_limit(user_id: str, per_minute: int) -> None:
    now = monotonic()
    window = _sign_calls[user_id]
    while window and now - window[0] > _SIGN_WINDOW_SECONDS:
        window.popleft()
    if len(window) >= max(1, per_minute):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many signing requests. Try again shortly.")
    window.append(now)


@router.get("/qz/certificate", response_class=Response)
async def qz_certificate(_user: User = Depends(get_current_user)) -> Response:
    """The public QZ Tray certificate the POS hands to the local service."""
    try:
        certificate = read_qz_material(settings.qz_print_certificate_path, label="certificate")
    except QzSigningError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return Response(content=certificate, media_type="text/plain")


@router.post("/qz/sign", response_model=QzSignRead)
async def qz_sign(payload: QzSignRequest, _user: User = Depends(get_current_user)) -> QzSignRead:
    """Sign one QZ Tray request string with the server-held private key."""
    _enforce_sign_rate_limit(str(_user.id), settings.qz_print_sign_rate_limit_per_minute)
    try:
        request = validate_qz_request(payload.request, settings.qz_print_request_max_bytes)
    except QzSigningError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    try:
        private_key = read_qz_material(settings.qz_print_private_key_path, label="private key")
        signature = sign_qz_request(request, private_key, settings.qz_print_signature_algorithm)
    except QzSigningError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return QzSignRead(signature=signature, algorithm=(settings.qz_print_signature_algorithm or "SHA512").upper())
