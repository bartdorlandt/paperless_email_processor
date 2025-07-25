# Paperless and Email Processor

With this script you can process files to be send to paperless api or email. It will check the `process_folder` for files in the `to_paperless`, `to_bookkeeping`, or `to_both` directories and process them accordingly.

## Requirements
- Python 3.13 or higher
- Required Python packages are specified in `pyproject.toml`
- Environment variables must be set for configuration, see env.example for details.

~~## Docker~~

~~The docker-compose file is provided to run the processor in a Docker container. It mounts the `process_folder` and sets the necessary environment variables.~~
~~It reads the `PROCESS_FOLDER` environment variable to set the main path for processing files.~~

## uv

It used to have a docker setup, with docker-compose and a Dockerfile. The challenge with it and dropbox is the notification to the filesystem when changes happen within the docker. Because of this, the cloud sync on my Synology NAS is not seeing the updates and therefore doesn't sync the files back to dropbox.

Since, I've been using `uv` to run the script directly on my server/nas. This allows for better integration with the filesystem and ensures that changes are detected immediately.

## Possible workflow
1. Use dropbox on your phone for taking pictures of receipts.
2. Drop the file in the desired folder:
   - `to_paperless` for paperless processing
   - `to_bookkeeping` for bookkeeping processing
   - `to_both` for both paperless and bookkeeping processing
3. Have dropbox synced on your server/nas (e.g. Synologoy with cloud sync)
4. Have the script running regularly on your server/nas.
5. The script will process the files in the specified folders and move them to the `done` folder after processing.

## Usage
Provide the main folder along with the environment variables in a `.env` file.

Run `task run` to start the script.