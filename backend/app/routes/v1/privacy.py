"""Authenticated data export. No export file is retained on the server."""

import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth.current_user import current_user
from app.db import get_session
from app.db.models import User
from app.mail import MailDeliveryError, SMTPMailer, get_mailer
from app.privacy import build_user_export

router = APIRouter()
logger = logging.getLogger(__name__)


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
