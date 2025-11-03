import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import main


@pytest.fixture(autouse=True)
def set_env(tmp_path: Path) -> None:
    os.environ["PROCESS_FOLDER"] = str(tmp_path / "process_folder")
    main.MAIN_PATH = Path(os.environ["PROCESS_FOLDER"])
    main.FROM_EMAIL = "from@example.local"
    main.ERROR_EMAIL = "some@email.local"
    main.SMTP_VARS = main.SmtpVars(
        smtp_port=465,
        smtp_srv="smtp.example.com",
        smtp_usr="user@example.com",
        smtp_pwd="password",
    )

@pytest.fixture(autouse=True)
def paperless_vars() -> main.PaperlessVars:
    return main.PaperlessVars(
        api_token="some_token",
        api_path="/api/documents/post_document/",
        api_url="http://localhost:8000",
    )

@pytest.fixture(autouse=True)
def bookkeeping_vars() -> main.EmailVars:
    return main.EmailVars(to="recipient@example.com")

# Fixtures for test files and folders
def setup_test_file(tmp_path, folder_name="to_paperless", filename="test.pdf") -> Path:
    folder = tmp_path / folder_name
    folder.mkdir(parents=True, exist_ok=True)
    file_path = folder / filename
    file_path.write_bytes(b"dummy content")
    return file_path


def test_move_to_done(tmp_path: Path) -> None:
    file_path = setup_test_file(tmp_path / "dir1")
    main.move_to_done(file_path)
    done_file = main.MAIN_PATH / "done" / "to_paperless" / "test.pdf"
    assert done_file.exists()
    assert not file_path.exists()


def test_process_folder_calls_processors(tmp_path: Path) -> None:
    file_path = setup_test_file(tmp_path)
    mock_processor = MagicMock()
    mock_processor.process.return_value = True  # Make processor succeed
    with patch("main.send_email") as mock_send_email:
        main.process_folder(file_path.parent, processors=[mock_processor])
        mock_processor.process.assert_called_with(file_path)
        # Since processor succeeded, send_email should not be called
        mock_send_email.assert_not_called()


def test_process_folder_calls_error_email_on_failure(tmp_path: Path) -> None:
    file_path = setup_test_file(tmp_path)
    mock_processor = MagicMock()
    mock_processor.process.return_value = False  # Make processor fail
    with patch("main.send_email") as mock_send_email:
        main.process_folder(file_path.parent, processors=[mock_processor])
        mock_processor.process.assert_called_with(file_path)
        # Since processor failed, send_email should be called for error notification
        mock_send_email.assert_called_once()


def test_paperless_api_processor_success(tmp_path: Path, paperless_vars: main.PaperlessVars) -> None:
    file_path = setup_test_file(tmp_path)
    processor = main.PaperlessAPIProcessor(vars=paperless_vars)
    with patch("main.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        assert processor.process(file_path) is True


def test_paperless_api_processor_failure(tmp_path: Path, paperless_vars: main.PaperlessVars) -> None:
    file_path = setup_test_file(tmp_path)
    processor = main.PaperlessAPIProcessor(vars=paperless_vars)
    with patch("main.requests.post") as mock_post:
        mock_post.return_value.status_code = 500
        mock_post.return_value.text = "error"
        assert processor.process(file_path) is False


def test_bookkeeping_email_processor_success(tmp_path: Path, bookkeeping_vars: main.EmailVars) -> None:
    file_path = setup_test_file(tmp_path, folder_name="to_bookkeeping")
    processor = main.EmailProcessor(vars=bookkeeping_vars)
    with patch("main.smtplib.SMTP_SSL") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        assert processor.process(file_path) is True
        mock_server.login.assert_called()
        mock_server.send_message.assert_called()


def test_bookkeeping_email_processor_failure(tmp_path: Path, bookkeeping_vars: main.EmailVars) -> None:
    file_path = setup_test_file(tmp_path, folder_name="to_bookkeeping")
    processor = main.EmailProcessor(vars=bookkeeping_vars)
    with patch("main.smtplib.SMTP_SSL", side_effect=Exception("fail")):
        assert processor.process(file_path) is False
