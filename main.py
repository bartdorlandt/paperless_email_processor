import logging
import smtplib
import ssl
import time
from email.message import EmailMessage
from pathlib import Path
from typing import NoReturn, Protocol

import requests
from environs import Env, validate

# Load environment variables
env = Env()
env.read_env()

# expected path. e.g.: process_folder/to_paperless
# expected path. e.g.: process_folder/done/to_paperless
main_path = Path("process_folder")
to_paperless = main_path / "to_paperless"
to_bookkeeping = main_path / "to_bookkeeping"
to_all = main_path / "to_all"

CHECK_INTERVAL = 300  # 5 minutes
# CHECK_INTERVAL = 10

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


class FileProcessor(Protocol):
    def process(self, filepath: Path) -> bool: ...


class PaperlessAPIProcessor:
    api_token = env.str("PAPERLESS_API_TOKEN")
    api_path = env.str("PAPERLESS_API_PATH")
    api_url = env.str("PAPERLESS_API_URL")

    def process(self, filepath: Path) -> bool:
        url = f"{self.api_url.rstrip('/')}{self.api_path}"
        headers = {"Authorization": f"Token {self.api_token}"}
        files = {"document": filepath.open("rb")}
        response = requests.post(url, headers=headers, files=files)
        if response.status_code == 200:
            logger.info(f"Uploaded to Paperless: {filepath}")
            return True
        else:
            logger.error(
                f"Failed to upload {filepath} to Paperless: {response.status_code} {response.text}"
            )
            return False


class BookkeepingEmailProcessor:
    port = env.int("SMTP_PORT")
    server = env.str("SMTP_SRV")
    user = env.str("SMTP_USR", validate=[validate.Length(min=4), validate.Email()])
    password = env.str("SMTP_PWD")
    to = env.str("SMTP_TO", validate=[validate.Length(min=4), validate.Email()])

    def process(self, filepath: Path) -> bool:
        msg = EmailMessage()
        msg["Subject"] = filepath.name
        msg["From"] = self.user
        msg["To"] = self.to
        with filepath.open("rb") as f:
            msg.add_attachment(
                f.read(),
                maintype="application",
                subtype="octet-stream",
                filename=filepath.name,
            )
        try:
            with smtplib.SMTP_SSL(
                self.server, self.port, context=ssl.create_default_context()
            ) as server:
                server.ehlo()
                server.login(self.user, self.password)
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
    p_of_p = filepath.parent.parent
    done_dir = p_of_p / "done" / parent
    done_dir.mkdir(parents=True, exist_ok=True)
    target = done_dir / filepath.name
    filepath.rename(target)
    logger.info(f"Moved {filepath} to {target}")


def process_folder(folder: Path, processors=None) -> None:
    folder.mkdir(exist_ok=True)
    for file in list(folder.iterdir()):
        if not file.is_file():
            continue
        if processors:
            # Track if any processor succeeded
            processed = False
            for processor in processors:
                # Only move to done if all processors succeed
                result = processor.process(file)
                processed = processed or result
            # If at least one processor succeeded, move to done
            if processed:
                move_to_done(file)


def main() -> NoReturn:
    logger.info("Starting snelstart-email-processor service...")
    paperless_processor = PaperlessAPIProcessor()
    bookkeeping_processor = BookkeepingEmailProcessor()
    while True:
        process_folder(to_paperless, processors=[paperless_processor])
        process_folder(to_bookkeeping, processors=[bookkeeping_processor])
        process_folder(to_all, processors=[paperless_processor, bookkeeping_processor])
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
