import os
import uuid
from typing import Dict, List

from appwrite.client import Client
from appwrite.input_file import InputFile
from appwrite.services.storage import Storage

from autonomous.config.settings import settings


def create_appwrite_client() -> Client:
    """Create and return an Appwrite Client instance."""
    client = Client()
    client.set_endpoint(settings.APPWRITE_REGION)
    client.set_project(settings.APPWRITE_PROJECT_ID)
    client.set_key(settings.APPWRITE_API_KEY)
    return client


def fetch_images_from_appwrite() -> List[Dict[str, str]]:
    """
    Fetch all image files from the Appwrite storage bucket configured in settings.

    Returns:
        List[Dict[str, str]]: A list of dictionaries containing file details:
            - file_id, name, url
    """
    client: Client = create_appwrite_client()
    storage: Storage = Storage(client)
    images: List[Dict[str, str]] = []

    response: Dict = storage.list_files(settings.APPWRITE_BUCKET_ID)
    for file in response["files"]:
        images.append(
            {
                "file_id": file["$id"],
                "name": file["name"],
                "url": (
                    f"{settings.APPWRITE_REGION}/storage/buckets/"
                    f"{settings.APPWRITE_BUCKET_ID}/files/{file['$id']}/view"
                    f"?project={settings.APPWRITE_PROJECT_ID}&mode=admin"
                ),
            }
        )

    return images


def upload_images_to_appwrite() -> List[Dict[str, str]]:
    """
    Upload images from the local folder specified by settings.FOLDER_PATH
    to the Appwrite bucket specified by settings.APPWRITE_BUCKET_ID.

    Returns:
        List[Dict[str, str]]: A list of dictionaries with uploaded file info:
            - file_id, name, appwrite_id
    """
    client: Client = create_appwrite_client()
    storage: Storage = Storage(client)
    uploaded_files: List[Dict[str, str]] = []

    for filename in os.listdir(settings.FOLDER_PATH):
        if filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            file_path: str = os.path.join(settings.FOLDER_PATH, filename)
            file_id: str = str(uuid.uuid4())

            input_file: InputFile = InputFile.from_path(file_path)
            response: Dict = storage.create_file(
                settings.APPWRITE_BUCKET_ID, file_id, input_file
            )

            uploaded_files.append(
                {"file_id": file_id, "name": filename, "appwrite_id": response["$id"]}
            )
            print(f"Uploaded {filename} as {file_id}")

    return uploaded_files
