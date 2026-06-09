"""
Google Drive integration for CodeGraph.
Handles auth, saving graphs to Drive, and loading them back.
"""
import json
import os
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import io

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
CREDENTIALS_FILE = Path(__file__).parent / "credentials.json"
TOKEN_FILE = Path(__file__).parent / "token.json"
DRIVE_FOLDER_NAME = "CodeGraph Saves"


def get_drive_service():
    """Authenticate and return a Drive service object."""
    creds = None

    # Load existing token if it exists
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    # If no valid token, do the OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            # Opens browser for user to log in
            creds = flow.run_local_server(port=0)

        # Save token for next time — user won't need to log in again
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


def _get_or_create_folder(service):
    """Get the CodeGraph Saves folder in Drive, create it if it doesn't exist."""
    query = f"name='{DRIVE_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])

    if files:
        return files[0]["id"]

    # Create it
    folder = service.files().create(body={
        "name": DRIVE_FOLDER_NAME,
        "mimeType": "application/vnd.google-apps.folder"
    }, fields="id").execute()
    return folder["id"]


def save_graph_to_drive(graph: dict, repo_name: str) -> str:
    """
    Save a knowledge graph JSON to Google Drive.
    Returns the Drive file ID.
    """
    import tempfile
    service = get_drive_service()
    folder_id = _get_or_create_folder(service)

    file_name = f"{repo_name}_knowledge_graph.json"

    # Use a proper temp file that Windows won't lock
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        delete=False,
        encoding="utf-8"
    ) as tmp:
        json.dump(graph, tmp, indent=2)
        tmp_path = tmp.name

    try:
        query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
        existing = service.files().list(q=query, fields="files(id)").execute().get("files", [])

        media = MediaFileUpload(tmp_path, mimetype="application/json")

        if existing:
            file = service.files().update(
                fileId=existing[0]["id"],
                media_body=media
            ).execute()
            file_id = file["id"]
        else:
            file = service.files().create(
                body={"name": file_name, "parents": [folder_id]},
                media_body=media,
                fields="id"
            ).execute()
            file_id = file["id"]

        # Explicitly close before delete — required on Windows
        media._fd.close()

    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass  # if delete fails, not worth crashing over

    print(f"Graph saved to Drive: {file_name} (id: {file_id})")
    return file_id


def list_saved_graphs() -> list:
    """List all previously saved graphs in Drive."""
    service = get_drive_service()
    folder_id = _get_or_create_folder(service)

    query = f"'{folder_id}' in parents and trashed=false"
    results = service.files().list(
        q=query,
        fields="files(id, name, modifiedTime)",
        orderBy="modifiedTime desc"
    ).execute()

    return results.get("files", [])


def load_graph_from_drive(file_id: str) -> dict:
    """Load a previously saved graph from Drive by file ID."""
    service = get_drive_service()

    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    buffer.seek(0)
    return json.loads(buffer.read().decode("utf-8"))