"""Unit tests for clearing the output directory."""

from pathlib import Path
from unittest.mock import patch
import pytest

from main import clear_output_directory, parse_args, main


def test_clear_output_directory_deletes_files_and_subdirs(tmp_path: Path):
    """Verify clear_output_directory removes files and folders but keeps the root directory."""
    # Create test files and nested folders
    file1 = tmp_path / "sample1.csv"
    file1.write_text("a,b,c\n1,2,3")
    file2 = tmp_path / "sample2.csv"
    file2.write_text("x,y,z\n4,5,6")
    sub_dir = tmp_path / "nested"
    sub_dir.mkdir()
    sub_file = sub_dir / "nested.csv"
    sub_file.write_text("nested")

    assert file1.exists()
    assert file2.exists()
    assert sub_file.exists()

    deleted_count = clear_output_directory(tmp_path)

    # 2 files + 1 subdir = 3 deleted items
    assert deleted_count == 3
    assert tmp_path.exists()
    assert list(tmp_path.iterdir()) == []


def test_clear_output_directory_empty(tmp_path: Path):
    """Verify clear_output_directory returns 0 on an already empty directory."""
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()

    deleted_count = clear_output_directory(empty_dir)
    assert deleted_count == 0
    assert empty_dir.exists()


def test_clear_output_directory_creates_if_not_exists(tmp_path: Path):
    """Verify clear_output_directory creates the folder if it does not exist and returns 0."""
    non_existent = tmp_path / "new_output"
    assert not non_existent.exists()

    deleted_count = clear_output_directory(non_existent)
    assert deleted_count == 0
    assert non_existent.exists()


def test_main_clean_flag_calls_clear(tmp_path: Path, capsys):
    """Verify running main with --clean clears output and exits cleanly."""
    file1 = tmp_path / "test.csv"
    file1.write_text("data")

    with patch("sys.argv", ["main.py", "--clean"]), \
         patch("main.clear_output_directory", return_value=1) as mock_clear:
        main()
        mock_clear.assert_called_once_with("output")

    captured = capsys.readouterr()
    assert "cleared 1 file(s)" in captured.out
