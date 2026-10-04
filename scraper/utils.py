"""Utility functions for Baseball Savant scraper."""

import logging
import shutil
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)


def clear_output_directory(output_dir: Union[str, Path] = "output") -> int:
    """Delete all files and subdirectories inside the output folder while preserving the folder itself.

    Args:
        output_dir: Path to the output directory.

    Returns:
        The count of files/directories removed.
    """
    target_dir = Path(output_dir)
    if not target_dir.exists():
        target_dir.mkdir(parents=True, exist_ok=True)
        return 0

    count = 0
    for item in target_dir.iterdir():
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()
                count += 1
            elif item.is_dir():
                shutil.rmtree(item)
                count += 1
        except Exception as e:
            logger.warning(f"Failed to delete {item}: {e}")

    return count
