import os
from azure.storage.blob import BlobServiceClient
import streamlit as st
import uuid
from datetime import datetime, timezone

def upload_to_blob(file, folder: str = "raw/") -> str:
    """
    Upload a file-like object (e.g. an uploaded PDF/DOCX) to Azure Blob Storage.

    The file will be saved under the specified folder with a date prefix and a
    random suffix to avoid name collisions. For example, a file named
    `document.pdf` uploaded on 2025‑07‑26 would be stored as
    `raw/2025-07-26/document_abcdef.pdf`.

    Args:
        file: A file-like object obtained from Streamlit's file uploader.
        folder: The top‑level folder in the container to store the file. Defaults
            to `raw/`.

    Returns:
        The path of the uploaded blob within the container.
    """
    # Get date folder for grouping uploads
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Construct a unique blob name preserving the original extension
    base_name, ext = os.path.splitext(file.name)
    full_path = f"{folder}{today}/{base_name}_{uuid.uuid4().hex[:6]}{ext}"

    # Retrieve connection parameters from Streamlit secrets
    connection_string = st.secrets["AZURE_STORAGE_CONNECTION_STRING"]
    container_name = st.secrets["AZURE_CONTAINER_NAME"]

    # Connect to Azure Blob storage and upload the file
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=full_path)
    blob_client.upload_blob(file, overwrite=True)
    return full_path


def upload_text_to_blob(text: str, folder: str = "results/") -> str:
    """
    Upload a plain text string to Azure Blob Storage.

    This helper creates an in-memory file from the provided text and uploads it
    to the configured Azure container. The blob will be stored in a folder
    structure organized by date. A UUID is appended to the filename to avoid
    collisions.

    Args:
        text: The string content to upload.
        folder: The folder path within the blob container where the text file
            will be saved. Defaults to `results/`.

    Returns:
        The path of the uploaded blob within the container.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"result_{uuid.uuid4().hex[:6]}.txt"
    blob_path = f"{folder}{today}/{filename}"
    connection_string = st.secrets["AZURE_STORAGE_CONNECTION_STRING"]
    container_name = st.secrets["AZURE_CONTAINER_NAME"]
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_path)
    # Upload the text by converting it to bytes
    blob_client.upload_blob(text.encode("utf-8"), overwrite=True)
    return blob_path



