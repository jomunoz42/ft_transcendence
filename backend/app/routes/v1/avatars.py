"""Avatar routes: upload and remove my avatar, and serve avatars and the default image."""

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.current_user import current_user
from app.crud.avatar import (
    MAX_BYTES, AvatarTooLarge, NotAnAcceptedImage, delete_avatar, process_image, read_avatar, save_avatar,
)
from app.crud.friendship import is_blocked
from app.db import get_session
from app.db.models import User
from app import errors

router = APIRouter()

DEFAULT_AVATAR_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">'
    b'<rect width="256" height="256" fill="#d9dce1"/>'
    b'<circle cx="128" cy="100" r="48" fill="#9aa1ab"/>'
    b'<path d="M40 232c0-48.6 39.4-88 88-88s88 39.4 88 88z" fill="#9aa1ab"/>'
    b'</svg>'
)
TOO_LARGE = HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Avatar must be at most 2 MB and 25 million pixels")
NOT_AN_IMAGE = HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Avatar must be a PNG, JPEG or WebP image")


@router.put("/profiles/me/avatar")
def upload_my_avatar(file: UploadFile = File(), me: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    """Replace my avatar with this image; 200 with the new avatar_url, 413 too large, 415 not a PNG/JPEG/WebP."""
    try:
        webp = process_image(file.file.read(MAX_BYTES + 1))
    except AvatarTooLarge:
        raise TOO_LARGE from None
    except NotAnAcceptedImage:
        raise NOT_AN_IMAGE from None
    url = save_avatar(session, me, webp)
    session.commit()
    return {"avatar_url": url}


@router.delete("/profiles/me/avatar")
def delete_my_avatar(me: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    """Go back to the default avatar; 200 with the default avatar_url, also when I had none."""
    url = delete_avatar(session, me)
    session.commit()
    return {"avatar_url": url}


@router.get("/avatars/default")
def default_avatar() -> Response:
    """The placeholder shown for anyone without an uploaded avatar; public and static."""
    return Response(DEFAULT_AVATAR_SVG, media_type="image/svg+xml", headers={
        "X-Content-Type-Options": "nosniff", "Cache-Control": "public, max-age=86400",
    })


@router.get("/avatars/{user_id}")
def get_avatar(user_id: int, me: User = Depends(current_user), session: Session = Depends(get_session)) -> Response:
    """Someone's uploaded avatar as WebP, for logged-in users; 404 if they have none or either of us blocked the other."""
    data = None if is_blocked(session, me.id, user_id) else read_avatar(session, user_id)
    if data is None:
        raise errors.HTTP_404_NOT_FOUND
    # no-store: a cached copy would still show after logout, a block or account deletion.
    return Response(data, media_type="image/webp", headers={
        "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store",
    })
