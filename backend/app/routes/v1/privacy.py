"""Authenticated data export. No export file is retained on the server."""

import json
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response as FastAPIResponse, status
from fastapi.responses import Response
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy.orm import Session

from app.auth.constants import SESSION_COOKIE_NAME
from app.auth.current_user import current_user
from app.db import get_session
from app.db.models import User
from app.deletion import (
    DeletionConfigurationError, DeletionRateLimited, DeletionTokenCodec,
    InvalidDeletionToken, confirm_and_delete, create_deletion_request,
)
from app.mail import MailDeliveryError, SMTPMailer, get_mailer
from app.privacy import build_user_export

router = APIRouter()
logger = logging.getLogger(__name__)


class ConfirmDeletionBody(BaseModel):
    token: SecretStr = Field(min_length=1, max_length=2048)
    confirmation: Literal["DELETE"]


@router.post("/export")
def export_my_data(
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
    mailer: SMTPMailer = Depends(get_mailer),
) -> Response:
    payload = build_user_export(session, user)
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    mail_status = "sent"
    try:
        mailer.send_export_confirmation(user.email)
    except MailDeliveryError:
        mail_status = "failed"
        logger.warning("Data export confirmation email delivery failed")
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="myplaylist-data.json"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-Confirmation-Email": mail_status,
        },
    )


@router.post("/deletion-request", status_code=status.HTTP_202_ACCEPTED)
def request_deletion(
    response: FastAPIResponse,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
    mailer: SMTPMailer = Depends(get_mailer),
) -> dict:
    try:
        codec = DeletionTokenCodec.from_environment()
        token, email, expires_at = create_deletion_request(session, user.id, codec)
        mailer.send(
            email,
            "Confirm your MyPlaylist account deletion",
            "A request to permanently delete your MyPlaylist account was made.\n"
            "While signed in, enter this token and explicitly confirm deletion:\n\n"
            f"{token}\n\n"
            f"This token expires at {expires_at.isoformat()}.\n"
            "If you did not request deletion, ignore this email.\n",
        )
        session.commit()
    except DeletionRateLimited as error:
        session.rollback()
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Wait before requesting another deletion email",
            headers={"Retry-After": str(error.retry_after)},
        ) from None
    except (DeletionConfigurationError, MailDeliveryError):
        session.rollback()
        logger.warning("Account deletion confirmation email was not issued")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Deletion confirmation email could not be sent",
        ) from None
    except InvalidDeletionToken:
        session.rollback()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account is no longer active") from None
    response.headers["Cache-Control"] = "no-store"
    return {"detail": "Check your email for the deletion confirmation token"}


@router.post("/deletion-confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_deletion(
    body: ConfirmDeletionBody,
    response: FastAPIResponse,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
    mailer: SMTPMailer = Depends(get_mailer),
) -> None:
    try:
        codec = DeletionTokenCodec.from_environment()
        email = confirm_and_delete(session, user.id, body.token.get_secret_value(), codec)
        session.commit()
    except InvalidDeletionToken:
        session.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired deletion confirmation") from None
    except DeletionConfigurationError:
        session.rollback()
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Deletion is temporarily unavailable") from None

    response.delete_cookie(SESSION_COOKIE_NAME, httponly=True, secure=True, samesite="lax")
    response.headers["Cache-Control"] = "no-store"
    try:
        mailer.send(
            email,
            "Your MyPlaylist account was deleted",
            "Your MyPlaylist account and its associated data were deleted.\n"
            "If you did not request this, contact the project team.\n",
        )
    except Exception:
        logger.warning("Account deletion completion email delivery failed")
