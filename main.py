"""Main script for processing files for Paperless and bookkeeping via email."""

import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Protocol

import requests
import urllib3
from environs import Env, validate

# Load environment variables
env = Env()
env.read_env()

# Logging setup: log to file and console, rotate at 10MB
LOG_FILENAME = Path(__file__).parent / "paperless_email_processor.log"
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
MAIN_PATH: Path
SMTP_VARS: SmtpVars
ERROR_EMAIL: str
FROM_EMAIL: str

if not logger.hasHandlers():
    file_handler = RotatingFileHandler(LOG_FILENAME, maxBytes=10 * 1024 * 1024, backupCount=2, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(file_handler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(console_handler)


@dataclass
class SmtpVars:
    """Email (SMTP) configuration variables."""

    smtp_srv: str
    smtp_usr: str
    smtp_pwd: str
    smtp_port: int = 465


@dataclass
class PaperlessVars:
    """Paperless API configuration variables."""

    api_token: str
    api_path: str
    api_url: str


@dataclass
class EmailVars:
    """Email configuration variables."""

    to: str


class FileProcessor(Protocol):
    """Protocol for file processors."""

    def process(self, filepath: Path) -> bool:
        """Process the file and return True if successful, False otherwise."""


class PaperlessAPIProcessor:
    """Processor for uploading files to the Paperless API."""

    def __init__(self, vars: PaperlessVars) -> None:
        """Initialize with PaperlessVars."""
        self.vars = vars

    def process(self, filepath: Path) -> bool:
        """Process the file and upload it to the Paperless API."""
        url = f"{self.vars.api_url.rstrip('/')}{self.vars.api_path}"
        headers = {"Authorization": f"Token {self.vars.api_token}"}
        files = {"document": filepath.open("rb")}
        try:
            response = requests.post(url, headers=headers, files=files, timeout=10)
        except requests.ConnectionError as e:
            logger.error(f"Failed to connect to Paperless API: {e}")
            return False
        except urllib3.exceptions.MaxRetryError as e:
            logger.error(f"Max retries exceeded while connecting to Paperless API: {e}")
            return False
        except urllib3.exceptions.NameResolutionError as e:
            logger.error(f"Name resolution error while connecting to Paperless API: {e}")
            return False
        logger.debug(f"Response from Paperless: {response.status_code} {response.text}")
        if response.status_code == 200:
            logger.info(f"Uploaded to Paperless: {filepath}")
            return True
        else:
            logger.error(f"Failed to upload {filepath} to Paperless: {response.status_code} {response.text}")
            return False


class EmailProcessor:
    """Processor for sending files via email to bookkeeping."""

    def __init__(self, vars: EmailVars) -> None:
        """Initialize with EmailVars."""
        self.vars = vars

    def process(self, filepath: Path) -> bool:
        """Process the file and send it via email."""
        msg = new_email_message(
            subject=filepath.name,
            smtp_to=self.vars.to,
        )
        with filepath.open("rb") as f:
            msg.add_attachment(
                f.read(),
                maintype="application",
                subtype="octet-stream",
                filename=filepath.name,
            )
        try:
            send_email(msg=msg)
        except Exception as e:
            logger.error(f"Failed to send {filepath} via email: {e}")
            return False
        else:
            logger.info(f"Sent successfully via email: {filepath}")
            return True


def move_to_done(filepath: Path) -> None:
    """Move processed file to the done directory."""
    # Get the parent directory name (e.g., to_paperless, to_bookkeeping, to_all)
    parent = filepath.parent.name
    done_dir = MAIN_PATH / "done" / parent
    done_dir.mkdir(parents=True, exist_ok=True)
    target = done_dir / filepath.name
    filepath.rename(target)
    logger.info(f"Moved {filepath} to {target}")


def process_folder(folder: Path, processors: list[FileProcessor]) -> None:
    """Process all files in the given folder with the provided processors."""
    folder.mkdir(exist_ok=True)
    for file in list(folder.iterdir()):
        if not file.is_file():
            continue

        # Track if any processor succeeded
        processed = 0
        for processor in processors:
            # Only move to done if all processors succeed
            result = processor.process(file)
            processed += result
            if not result:
                error_email(subject="File Processing Error", filename=file.name)

        if processed == len(processors):
            move_to_done(file)


def error_email(subject: str, filename: str) -> None:
    """Send an error email notification."""
    msg = new_email_message(subject, smtp_to=ERROR_EMAIL)
    body = f"An error occurred while processing file: {filename!r}\nCheck the logs for more details."
    msg.set_content(body)

    try:
        send_email(msg=msg)
    except Exception as e:
        logger.error(f"Failed to send error email: {e}")
        raise e
    else:
        logger.info("Sent error email successfully.")


def new_email_message(subject: str, smtp_to: str) -> EmailMessage:
    """Define a new email message."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = smtp_to
    return msg


def send_email(msg: EmailMessage) -> None:
    """Send an email message via SMTP."""
    with smtplib.SMTP_SSL(SMTP_VARS.smtp_srv, SMTP_VARS.smtp_port, context=ssl.create_default_context()) as server:
        server.ehlo()
        server.login(SMTP_VARS.smtp_usr, SMTP_VARS.smtp_pwd)
        server.send_message(msg)


def main() -> None:
    """Main entry point for the script."""
    # Reading the vars here to ensure env dependencies are present and loaded
    paperless_vars = PaperlessVars(
        api_token=env.str("PAPERLESS_API_TOKEN"),
        api_path=env.str("PAPERLESS_API_PATH"),
        api_url=env.str("PAPERLESS_API_URL"),
    )
    bookkeeping_vars = EmailVars(
        to=env.str("BOOKKEEPING_EMAIL", validate=[validate.Length(min=4), validate.Email()]),
    )
    bookkeeper_vars = EmailVars(
        to=env.str("BOOKKEEPER_EMAIL", validate=[validate.Length(min=4), validate.Email()]),
    )
    # logger.info("Starting paperless-email-processor service...")
    paperless_processor = PaperlessAPIProcessor(paperless_vars)
    bookkeeping_processor = EmailProcessor(bookkeeping_vars)
    process_folder(MAIN_PATH / "to_paperless", processors=[paperless_processor])
    process_folder(MAIN_PATH / "to_bookkeeping", processors=[bookkeeping_processor])
    process_folder(MAIN_PATH / "to_both", processors=[paperless_processor, bookkeeping_processor])

    to_person_processor = EmailProcessor(bookkeeper_vars)
    process_folder(MAIN_PATH / "to_bookkeeper", processors=[to_person_processor])


if __name__ == "__main__":
    # Vars
    PROCESS_FOLDER = env.str("PROCESS_FOLDER", default="process_folder")
    MAIN_PATH = Path(PROCESS_FOLDER)

    SMTP_VARS = SmtpVars(
        smtp_srv=env.str("SMTP_SRV"),
        smtp_usr=env.str("SMTP_USR", validate=[validate.Length(min=4), validate.Email()]),
        smtp_pwd=env.str("SMTP_PWD"),
        smtp_port=env.int("SMTP_PORT", default=465),
    )
    ERROR_EMAIL = env.str("ERROR_EMAIL", validate=[validate.Length(min=4), validate.Email()])
    FROM_EMAIL = env.str("SMTP_USR", validate=[validate.Length(min=4), validate.Email()])
    main()
