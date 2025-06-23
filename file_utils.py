import os
import uuid
from pathlib import Path
from typing import Tuple
from fastapi import UploadFile, HTTPException, status

# Base directory for file uploads (creates an 'uploads' folder in your project root)
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


async def save_upload_file(upload_file: UploadFile, subfolder: str = "grievances") -> Tuple[str, str, int]:
    """
    Save an uploaded file to the server.

    Args:
        upload_file: The uploaded file
        subfolder: Subfolder within UPLOAD_DIR to save the file

    Returns:
        Tuple of (file_path, original_filename, file_size)
    """
    try:
        # Create directory if it doesn't exist
        file_dir = Path(UPLOAD_DIR) / subfolder
        file_dir.mkdir(parents=True, exist_ok=True)

        # Generate a unique filename while preserving the extension
        file_ext = Path(upload_file.filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = file_dir / unique_filename

        # Save the file
        file_content = await upload_file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(file_content)

        return str(file_path), upload_file.filename, len(file_content)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving file: {str(e)}"
        )


def delete_file(file_path: str) -> bool:
    """
    Delete a file from the server.

    Args:
        file_path: Path to the file to delete

    Returns:
        bool: True if file was deleted, False otherwise
    """
    try:
        path = Path(file_path)
        if path.exists():
            path.unlink()
            return True
        return False
    except Exception:
        return False


def get_mime_type(file_path: str) -> str:
    """
    Get the MIME type of a file based on its extension.
    """
    import mimetypes
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type or 'application/octet-stream'