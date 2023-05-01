import os
import time

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from google.oauth2.service_account import Credentials


WATCHED_DIR = os.environ.get("WATCHED_DIR")
CREDENTIALS_FILE = os.environ.get("CREDENTIALS_FILE")


class GoogleDriveClient:
    def __init__(self, credentials_file, token_file):
        self.scopes = ["https://www.googleapis.com/auth/drive"]
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.credentials = self.get_credentials()
        self.service = build("drive", "v3", credentials=self.credentials)
        self.check_authorization(self.credentials)

    def get_credentials(self):
        creds = Credentials.from_service_account_file(self.credentials_file, scopes=self.scopes)
        return creds

    def check_authorization(self, creds):
        try:
            service = build("drive", "v3", credentials=creds)
            about = service.about().get(fields="user, storageQuota").execute()

            print("Authorized")
            print(f"Logged as: {about['user']['emailAddress']}")
            print("Storage:")
            print(f"Total: {about['storageQuota']['limit']} bytes")
            print(f"Used: {about['storageQuota']['usage']} bytes")

        except HttpError as error:
            print(f"Error: {error}")
            return False

        return True

    def upload_file(self, file_path):
        try:
            file_metadata = {
                "name": os.path.basename(file_path),
                "parent": [f'{os.environ.get("DRIVE_FOLDER")}']
            }
            media = MediaFileUpload(file_path, resumable=True)
            file = self.service.files().create(
                body=file_metadata, media_body=media, fields="id",
            ).execute()
            print(f"File ID: {file.get('id')}")
        except HttpError as error:
            print(f"An error occurred: {error}")
            file = None

        return file


class Watcher:
    def __init__(self, watch_dir, drive_client):
        self.watch_dir = watch_dir
        self.drive_client = drive_client

    def on_modified(self, event):
        if event.is_directory:
            return

        file_path, file_extension = os.path.splitext(event.src_path)
        new_file_path = f"{file_path}.png"

        if os.path.exists(new_file_path):
            print(f"New file created: {new_file_path}")
            self.drive_client.upload_file(new_file_path)

    def run(self):
        event_handler = FileSystemEventHandler()
        event_handler.on_modified = self.on_modified

        observer = Observer()
        observer.schedule(event_handler, path=self.watch_dir, recursive=False)
        observer.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()

        observer.join()


def main():
    drive_client = GoogleDriveClient(CREDENTIALS_FILE)

    watcher = Watcher(WATCHED_DIR, drive_client)
    watcher.run()


if __name__ == "__main__":
    main()
