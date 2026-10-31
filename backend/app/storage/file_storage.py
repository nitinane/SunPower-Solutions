from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import settings

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


def _root() -> Path:
    root = Path(settings.storage_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


async def save_file(upload: UploadFile) -> str:
    if upload.content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError("Unsupported file type")
    limit = settings.max_upload_mb * 1024 * 1024
    content = await upload.read(limit + 1)
    if len(content) > limit:
        raise ValueError("File exceeds configured size limit")
    key = f"{uuid4().hex}{Path(upload.filename or '').suffix.lower()}"
    (_root() / key).write_bytes(content)
    return key


def read_file(storage_key: str) -> bytes:
    key = PurePosixPath(storage_key)
    if key.is_absolute() or len(key.parts) != 1 or key.name in {"", ".", ".."}:
        raise ValueError("Invalid storage key")
    root = _root()
    path = (root / key.name).resolve()
    if path.parent != root:
        raise ValueError("Invalid storage key")
    return path.read_bytes()


# ---------------------------------------------------------------- Byte-level helpers
# Keys look like "2026/11/<uuid4>.png". The uploaded filename is never used on disk.

def save_bytes(content: bytes, ext: str) -> str:
    """Write bytes under STORAGE_DIR and return the new storage key."""
    now = datetime.now(UTC)
    key = f"{now:%Y}/{now:%m}/{uuid4().hex}.{ext}"
    path = _path_for(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return key


def open_bytes(storage_key: str) -> bytes:
    """Read a file saved by save_bytes. Unknown or unsafe key -> FileNotFoundError / ValueError."""
    return _path_for(storage_key).read_bytes()


def _path_for(storage_key: str) -> Path:
    key = PurePosixPath(storage_key)
    if key.is_absolute() or len(key.parts) != 3 or any(p in {"", ".", ".."} for p in key.parts):
        raise ValueError("Invalid storage key")
    root = _root()
    path = (root / Path(*key.parts)).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Invalid storage key")
    return path
