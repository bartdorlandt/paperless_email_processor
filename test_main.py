import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import main


@pytest.fixture(scope="session", autouse=True)
def set_env():
    os.environ["PAPERLESS_API_TOKEN"] = "some_token"


# Fixtures for test files and folders
def setup_test_file(tmp_path, folder_name="to_paperless", filename="test.pdf") -> Path:
    folder = tmp_path / folder_name
    folder.mkdir(parents=True, exist_ok=True)
    file_path = folder / filename
    file_path.write_bytes(b"dummy content")
    return file_path


def test_move_to_done(tmp_path: Path) -> None:
    file_path = setup_test_file(tmp_path / "dir1")
    # Override to_done for testing, when testing inside a container
    # OSError: [Errno 18] Invalid cross-device link:
    main.to_done = tmp_path / "done"

    main.move_to_done(file_path)
    done_file = main.to_done / "to_paperless" / "test.pdf"
    assert done_file.exists()
    assert not file_path.exists()


def test_process_folder_calls_processors(tmp_path: Path) -> None:
    file_path = setup_test_file(tmp_path)
    mock_processor = MagicMock()
    main.process_folder(file_path.parent, processors=[mock_processor])
    mock_processor.process.assert_called_with(file_path)


def test_paperless_api_processor_success(tmp_path: Path) -> None:
    file_path = setup_test_file(tmp_path)
    processor = main.PaperlessAPIProcessor()
    with patch("main.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        assert processor.process(file_path) is True


def test_paperless_api_processor_failure(tmp_path: Path) -> None:
    file_path = setup_test_file(tmp_path)
    processor = main.PaperlessAPIProcessor()
    with patch("main.requests.post") as mock_post:
        mock_post.return_value.status_code = 500
        mock_post.return_value.text = "error"
        assert processor.process(file_path) is False


def test_bookkeeping_email_processor_success(tmp_path: Path) -> None:
    file_path = setup_test_file(tmp_path, folder_name="to_bookkeeping")
    processor = main.BookkeepingEmailProcessor()
    with patch("main.smtplib.SMTP_SSL") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        assert processor.process(file_path) is True
        mock_server.login.assert_called()
        mock_server.send_message.assert_called()


def test_bookkeeping_email_processor_failure(tmp_path: Path) -> None:
    file_path = setup_test_file(tmp_path, folder_name="to_bookkeeping")
    processor = main.BookkeepingEmailProcessor()
    with patch("main.smtplib.SMTP_SSL", side_effect=Exception("fail")):
        assert processor.process(file_path) is False
