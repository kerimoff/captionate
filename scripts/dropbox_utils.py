import dropbox
import os
import logging
from typing import Optional
from dropbox.files import WriteMode, FileMetadata, FolderMetadata
from dropbox.exceptions import ApiError, AuthError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_dbx_client():
    """Initializes and returns a Dropbox client that handles token refreshing."""
    app_key = os.getenv('DROPBOX_APP_KEY')
    app_secret = os.getenv('DROPBOX_APP_SECRET')
    refresh_token = os.getenv('DROPBOX_REFRESH_TOKEN')

    if not all([app_key, app_secret, refresh_token]):
        logger.error("Missing one or more Dropbox environment variables: DROPBOX_APP_KEY, DROPBOX_APP_SECRET, DROPBOX_REFRESH_TOKEN.")
        raise ValueError("Missing Dropbox environment variables for token refresh.")

    try:
        dbx = dropbox.Dropbox(
            oauth2_refresh_token=refresh_token,
            app_key=app_key,
            app_secret=app_secret,
        )
        dbx.users_get_current_account()
        logger.info("Successfully connected to Dropbox and refreshed token.")
        return dbx
    except AuthError as e:
        logger.error(f"Dropbox authentication failed: {e}")
        raise ConnectionError("Dropbox authentication failed.") from e
    except Exception as e:
        logger.error(f"Failed to connect to Dropbox: {e}")
        raise ConnectionError("Failed to connect to Dropbox.") from e

def upload_and_get_temporary_link(dbx: dropbox.Dropbox, file_content: bytes, dropbox_path: str) -> Optional[str]:
    """Uploads a file and returns a temporary link."""
    try:
        dbx.files_upload(file_content, dropbox_path, mode=WriteMode('overwrite'))
        logger.info(f"Successfully uploaded to Dropbox: {dropbox_path}")
        
        link_result = dbx.files_get_temporary_link(dropbox_path)
        if link_result:
            logger.info(f"Successfully created temporary link for: {dropbox_path}")
            return link_result.link
        else:
            logger.error(f"Failed to get temporary link for {dropbox_path}")
            return None
    except ApiError as e:
        logger.error(f"Dropbox API error when processing {dropbox_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to upload or get temporary link from Dropbox for {dropbox_path}: {e}")
        return None

def download_from_dropbox(dbx: dropbox.Dropbox, dropbox_folder_path: str) -> str:
    """Download files from a Dropbox folder path using an initialized client."""
    local_save_path = './downloaded_files'
    os.makedirs(local_save_path, exist_ok=True)
    
    logger.info(f"Downloading from Dropbox folder: {dropbox_folder_path}")

    def download_folder_recursive(dropbox_path: str, local_path: str):
        try:
            list_folder_result = dbx.files_list_folder(dropbox_path)
            for entry in list_folder_result.entries:  # type: ignore
                if isinstance(entry, FileMetadata):
                    file_name = os.path.basename(entry.path_lower)
                    local_file = os.path.join(local_path, file_name)
                    logger.info(f"Downloading {file_name}...")
                    dbx.files_download_to_file(local_file, entry.path_lower)
                elif isinstance(entry, FolderMetadata):
                    subfolder = os.path.join(local_path, entry.name)
                    os.makedirs(subfolder, exist_ok=True)
                    download_folder_recursive(entry.path_lower, subfolder)
        except ApiError as e:
            raise RuntimeError(f"Error downloading from Dropbox: {e}") from e

    download_folder_recursive(dropbox_folder_path, local_save_path)
    return local_save_path

def download_single_file_from_dropbox(dbx: dropbox.Dropbox, dropbox_file_path: str, local_folder_path: str) -> str:
    """Download a single file from Dropbox."""
    file_name = os.path.basename(dropbox_file_path)
    local_file = os.path.join(local_folder_path, file_name)
    
    logger.info(f"Downloading {file_name} from Dropbox path '{dropbox_file_path}'...")
    try:
        dbx.files_download_to_file(local_file, dropbox_file_path)
        logger.info(f"Successfully downloaded to {local_file}")
        return local_file
    except ApiError as err:
        if err.error.is_path() and err.error.get_path().is_not_found():
            raise FileNotFoundError(f"File not found on Dropbox: {dropbox_file_path}") from err
        raise RuntimeError(f"Error downloading file from Dropbox: {err}") from err

def upload_to_dropbox(dbx: dropbox.Dropbox, local_file_path: str, dropbox_upload_path: str):
    """Uploads a local file to a specified Dropbox path."""
    logger.info(f"Attempting to upload {local_file_path} to: {dropbox_upload_path}")
    
    with open(local_file_path, "rb") as f:
        try:
            dbx.files_upload(f.read(), dropbox_upload_path, mode=WriteMode('overwrite'))
            logger.info(f"Successfully uploaded {local_file_path} to {dropbox_upload_path}")
        except ApiError as e:
            raise RuntimeError(f"Error during Dropbox upload: {e}") from e 