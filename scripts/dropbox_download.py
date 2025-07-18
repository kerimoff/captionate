import dropbox
import os

# Dropbox Access Token (get this from your Dropbox App console)
ACCESS_TOKEN = os.getenv('DROPBOX_ACCESS_TOKEN')
DROPBOX_FOLDER_PATH = '/temp/20_52_07'  # Root path or subfolder

# Local folder to save files
LOCAL_SAVE_PATH = './downloaded_files_2'

# Create local directory if not exists
os.makedirs(LOCAL_SAVE_PATH, exist_ok=True)

# Initialize Dropbox client
dbx = dropbox.Dropbox(ACCESS_TOKEN)

# List and download all files in the shared folder
def download_folder(path, local_path):
    try:
        entries = dbx.files_list_folder(path).entries
        for entry in entries:
            if isinstance(entry, dropbox.files.FileMetadata):
                file_path = entry.path_lower
                file_name = os.path.basename(file_path)
                local_file = os.path.join(local_path, file_name)
                print(f"Downloading {file_name}...")
                with open(local_file, "wb") as f:
                    metadata, res = dbx.files_download(path=file_path)
                    f.write(res.content)
            elif isinstance(entry, dropbox.files.FolderMetadata):
                subfolder = os.path.join(local_path, entry.name)
                os.makedirs(subfolder, exist_ok=True)
                download_folder(entry.path_lower, subfolder)
    except Exception as e:
        print(f"Error: {e}")

download_folder(DROPBOX_FOLDER_PATH, LOCAL_SAVE_PATH)