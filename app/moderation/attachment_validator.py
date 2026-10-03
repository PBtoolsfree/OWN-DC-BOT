"""
PB HERO Attachment Validator.

Validates message attachments for image-only, media, and file policies.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger("pbhero.moderation")

# Allowed image types
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}
IMAGE_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "image/bmp", "image/svg+xml", "image/avif",
}

# Video types
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".avi", ".mkv", ".flv"}
VIDEO_CONTENT_TYPES = {
    "video/mp4", "video/webm", "video/quicktime",
    "video/x-msvideo", "video/x-matroska",
}

# Blocked file types (dangerous)
BLOCKED_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".com", ".msi", ".scr", ".pif",
    ".vbs", ".js", ".wsf", ".wsh", ".ps1", ".reg",
}

# Document types
DOCUMENT_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".txt", ".rtf", ".odt", ".ods", ".odp",
}

# Archive types
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"}


@dataclass
class AttachmentInfo:
    """Parsed attachment information."""
    filename: str
    extension: str
    content_type: str
    size: int
    is_image: bool = False
    is_video: bool = False
    is_document: bool = False
    is_archive: bool = False
    is_blocked: bool = False


def classify_attachment(filename: str, content_type: str = "", size: int = 0) -> AttachmentInfo:
    """Classify an attachment by its type."""
    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()

    info = AttachmentInfo(
        filename=filename,
        extension=ext,
        content_type=content_type.lower() if content_type else "",
        size=size,
    )

    # Check content type first (more reliable), then extension
    if content_type:
        ct = content_type.lower()
        if ct in IMAGE_CONTENT_TYPES or ct.startswith("image/"):
            info.is_image = True
        elif ct in VIDEO_CONTENT_TYPES or ct.startswith("video/"):
            info.is_video = True
    
    # Extension-based classification as secondary
    if not info.is_image and not info.is_video:
        if ext in IMAGE_EXTENSIONS:
            info.is_image = True
        elif ext in VIDEO_EXTENSIONS:
            info.is_video = True

    if ext in DOCUMENT_EXTENSIONS:
        info.is_document = True
    if ext in ARCHIVE_EXTENSIONS:
        info.is_archive = True
    if ext in BLOCKED_EXTENSIONS:
        info.is_blocked = True

    return info


def validate_attachments(attachments: list, policy: dict) -> list[dict]:
    """
    Validate a list of Discord attachments against a policy.

    Args:
        attachments: List of discord.Attachment objects
        policy: Dict with allow_images, allow_videos, allow_files keys

    Returns:
        List of violation dicts (empty if all ok)
    """
    violations = []

    for att in attachments:
        info = classify_attachment(
            filename=att.filename,
            content_type=att.content_type or "",
            size=att.size,
        )

        # Always block dangerous files
        if info.is_blocked:
            violations.append({
                "filename": att.filename,
                "reason": f"Blocked file type: {info.extension}",
                "rule": "blocked_extension",
            })
            continue

        # Check image policy
        if info.is_image and policy.get("allow_images") == "deny":
            violations.append({
                "filename": att.filename,
                "reason": "Images are not allowed in this channel",
                "rule": "images_denied",
            })
            continue

        # Check video policy
        if info.is_video and policy.get("allow_videos") == "deny":
            violations.append({
                "filename": att.filename,
                "reason": "Videos are not allowed in this channel",
                "rule": "videos_denied",
            })
            continue

        # Check files policy (non-image, non-video)
        if not info.is_image and not info.is_video:
            if policy.get("allow_files") == "deny":
                violations.append({
                    "filename": att.filename,
                    "reason": "Files are not allowed in this channel",
                    "rule": "files_denied",
                })

    return violations
