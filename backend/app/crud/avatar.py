"""Avatar storage: turn an upload into a clean 256x256 WebP and keep one per user in Postgres."""

import hashlib
import io

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import Avatar, User

DEFAULT_URL = "/api/v1/avatars/default"
MAX_BYTES = 2 * 1024 * 1024
MAX_PIXELS = 5000 * 5000
SIZE = (256, 256)
ACCEPTED_FORMATS = ("PNG", "JPEG", "WEBP")


class AvatarTooLarge(Exception):
    """The upload is over MAX_BYTES or has more than MAX_PIXELS pixels."""


class NotAnAcceptedImage(Exception):
    """The upload is not a readable PNG, JPEG or WebP."""


def process_image(data: bytes) -> bytes:
    """Decode a PNG, JPEG or WebP and re-encode it as a 256x256 WebP; the output keeps no metadata from the input."""
    if len(data) > MAX_BYTES:
        raise AvatarTooLarge()
    try:
        with Image.open(io.BytesIO(data), formats=ACCEPTED_FORMATS) as image:
            # The header gives the size before any pixel is decoded, which stops decompression bombs.
            if image.width * image.height > MAX_PIXELS:
                raise AvatarTooLarge()
            upright = ImageOps.exif_transpose(image).convert("RGBA")
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        raise NotAnAcceptedImage() from None
    output = io.BytesIO()
    ImageOps.fit(upright, SIZE).save(output, "WEBP", quality=85)
    return output.getvalue()


def avatar_url(user_id: int, data: bytes) -> str:
    """URL of this exact image: a new image gives a new URL, so browsers never show a cached old one."""
    return f"/api/v1/avatars/{user_id}?v={hashlib.sha256(data).hexdigest()[:16]}"


def save_avatar(session: Session, user: User, webp: bytes) -> str:
    """Store or replace my avatar and point my profile at it; returns the new URL. Never commits."""
    upsert = insert(Avatar).values(user_id=user.id, data=webp)
    session.execute(upsert.on_conflict_do_update(
        index_elements=[Avatar.user_id], set_={"data": webp, "updated_at": upsert.excluded.updated_at},
    ))
    user.profile.avatar_url = avatar_url(user.id, webp)
    session.flush()
    return user.profile.avatar_url


def delete_avatar(session: Session, user: User) -> str:
    """Remove my avatar, if any, and show the default again; returns the default URL. Never commits."""
    session.execute(delete(Avatar).where(Avatar.user_id == user.id))
    user.profile.avatar_url = DEFAULT_URL
    session.flush()
    return DEFAULT_URL


def read_avatar(session: Session, user_id: int) -> bytes | None:
    """The stored WebP for this user, or None if they never uploaded one."""
    avatar = session.get(Avatar, user_id, populate_existing=True)
    return None if avatar is None else avatar.data
