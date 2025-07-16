# Paperless and Email Processor

With this script you can process files to be send to paperless or email. It will check the `process_folder` for files in the `to_paperless`, `to_bookkeeping`, or `to_both` directories and process them accordingly.

## Requirements
- Python 3.13 or higher
- Required Python packages are specified in `pyproject.toml`
- Environment variables must be set for configuration, see env.example for details.

## Docker

The docker-compose file is provided to run the processor in a Docker container. It mounts the `process_folder` and sets the necessary environment variables.
It reads the `PROCESS_FOLDER` environment variable to set the main path for processing files.

## Possible workflow
1. Use dropbox on your phone for taking pictures of receipts.
2. Drop the file in the desired folder:
   - `to_paperless` for paperless processing
   - `to_bookkeeping` for bookkeeping processing
   - `to_both` for both paperless and bookkeeping processing
3. Have dropbox synced on your server/nas (e.g. Synologoy with cloud sync)
4. Have the docker container running on your server/nas.
5. The script will automatically process the files in the specified folders and move them to the `done` folder after processing.

## Usage
Provide the main folder along with the environment variables in a `.env` file.

Run `task up` to start the docker container.