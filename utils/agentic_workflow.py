import os
import tempfile
from datetime import datetime, timezone
from typing import Optional
import dotenv
import yaml
from azure.storage.blob import BlobServiceClient
from docx import Document
from PyPDF2 import PdfReader

def _download_blob_to_local(blob_path: str) -> str:
    print(f"[⏬] Downloading blob: {blob_path}")
    connection_string = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    container_name = os.environ["AZURE_CONTAINER_NAME"]

    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_path)

    _, ext = os.path.splitext(os.path.basename(blob_path))
    fd, tmp_path = tempfile.mkstemp(suffix=ext)
    os.close(fd)

    with open(tmp_path, "wb") as f:
        f.write(blob_client.download_blob().readall())

    print(f"[✅] Blob saved: {tmp_path}")
    return tmp_path

def _extract_text(file_path: str) -> str:
    print(f"[📄] Extracting text: {file_path}")
    if file_path.endswith(".pdf"):
        with open(file_path, "rb") as f:
            reader = PdfReader(f)
            return "\n".join([p.extract_text() or "" for p in reader.pages])
    elif file_path.endswith(".docx"):
        return "\n".join([p.text for p in Document(file_path).paragraphs])
    raise ValueError("Unsupported file type")

async def generate_case_from_blob(blob_path: Optional[str], user_prompt: str) -> str:
    print("[📘] Starting basic case generation...")

    dotenv.load_dotenv()
    try:
        guide_text = _extract_text(_download_blob_to_local("internal-docs/CaseWritingGuide.pdf"))
    except Exception as e:
        return f"❌ Failed to load internal guide: {e}"

    if blob_path:
        try:
            user_file = _download_blob_to_local(blob_path)
            user_text = _extract_text(user_file)
            guide_text += f"\n\n---\n\nAdditional Context from Uploaded File:\n\n{user_text}"
        except Exception as e:
            return f"❌ Failed to load user file: {e}"

    return f"📄 Combined Guide and User Content:\n\nPrompt: {user_prompt}\n\n{guide_text}"
