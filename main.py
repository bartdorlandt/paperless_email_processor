import logging
import smtplib
import ssl
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

main_path: Path
CHECK_INTERVAL = 300  # 5 minutes

# Logging setup: log to file and console, rotate at 10MB
LOG_FILENAME = Path(__file__).parent / "paperless_email_processor.log"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logger.hasHandlers():
    file_handler = RotatingFileHandler(
        LOG_FILENAME, maxBytes=10 * 1024 * 1024, backupCount=2, encoding="utf-8"
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    logger.addHandler(file_handler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    logger.addHandler(console_handler)


class FileProcessor(Protocol):
    def process(self, filepath: Path) -> bool:
        """Process the file and return True if successful, False otherwise."""


class PaperlessAPIProcessor:
    def __init__(self) -> None:
        self.PAPERLESS_API_TOKEN = env.str("PAPERLESS_API_TOKEN")
        self.PAPERLESS_API_PATH = env.str("PAPERLESS_API_PATH")
        self.PAPERLESS_API_URL = env.str("PAPERLESS_API_URL")

    def process(self, filepath: Path) -> bool:
        url = f"{self.PAPERLESS_API_URL.rstrip('/')}{self.PAPERLESS_API_PATH}"
        headers = {"Authorization": f"Token {self.PAPERLESS_API_TOKEN}"}
        files = {"document": filepath.open("rb")}
        try:
            response = requests.post(url, headers=headers, files=files)
        except requests.ConnectionError as e:
            logger.error(f"Failed to connect to Paperless API: {e}")
            return False
        except urllib3.exceptions.MaxRetryError as e:
            logger.error(f"Max retries exceeded while connecting to Paperless API: {e}")
            return False
        except urllib3.exceptions.NameResolutionError as e:
            logger.error(
                f"Name resolution error while connecting to Paperless API: {e}"
            )
            return False
        logger.debug(f"Response from Paperless: {response.status_code} {response.text}")
        if response.status_code == 200:
            logger.info(f"Uploaded to Paperless: {filepath}")
            return True
        else:
            logger.error(
                f"Failed to upload {filepath} to Paperless: {response.status_code} {response.text}"
            )
            return False


class BookkeepingEmailProcessor:
    def __init__(self) -> None:
        self.SMTP_PORT = env.int("SMTP_PORT")
        self.SMTP_SRV = env.str("SMTP_SRV")
        self.SMTP_USR = env.str(
            "SMTP_USR", validate=[validate.Length(min=4), validate.Email()]
        )
        self.SMTP_PWD = env.str("SMTP_PWD")
        self.SMTP_TO = env.str(
            "SMTP_TO", validate=[validate.Length(min=4), validate.Email()]
        )

    def process(self, filepath: Path) -> bool:
        msg = EmailMessage()
        msg["Subject"] = filepath.name
        msg["From"] = self.SMTP_USR
        msg["To"] = self.SMTP_TO
        with filepath.open("rb") as f:
            msg.add_attachment(
                f.read(),
                maintype="application",
                subtype="octet-stream",
                filename=filepath.name,
            )
        try:
            with smtplib.SMTP_SSL(
                self.SMTP_SRV, self.SMTP_PORT, context=ssl.create_default_context()
            ) as server:
                server.ehlo()
                server.login(self.SMTP_USR, self.SMTP_PWD)
                server.send_message(msg)
        except Exception as e:
            logger.error(f"Failed to send {filepath} via email: {e}")
            return False
        else:
            logger.info(f"Sent to bookkeeping: {filepath}")
            return True


def move_to_done(filepath: Path) -> None:
    # Get the parent directory name (e.g., to_paperless, to_bookkeeping, to_all)
    parent = filepath.parent.name
    done_dir = main_path / "done" / parent
    done_dir.mkdir(parents=True, exist_ok=True)
    target = done_dir / filepath.name
    filepath.rename(target)
    logger.info(f"Moved {filepath} to {target}")


def process_folder(folder: Path, processors: list[FileProcessor]) -> None:
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

        if processed == len(processors):
            move_to_done(file)


def main() -> None:
    # logger.info("Starting paperless-email-processor service...")
    paperless_processor = PaperlessAPIProcessor()
    bookkeeping_processor = BookkeepingEmailProcessor()
    process_folder(main_path / "to_paperless", processors=[paperless_processor])
    process_folder(main_path / "to_bookkeeping", processors=[bookkeeping_processor])
    process_folder(
        main_path / "to_both", processors=[paperless_processor, bookkeeping_processor]
    )


if __name__ == "__main__":
    # Vars
    PROCESS_FOLDER = env.str("PROCESS_FOLDER", default="process_folder")
    main_path = Path(PROCESS_FOLDER)
    main()
