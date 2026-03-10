import base64
from pathlib import Path


def encode_image(image_path: str) -> tuple[str, str]:
    """Encode image to base64 and detect MIME type."""
    ext = Path(image_path).suffix.lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".heic": "image/heic",
    }
    mime_type = mime_map.get(ext, "image/png")

    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8"), mime_type
