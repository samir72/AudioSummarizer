from dotenv import load_dotenv
import os, uuid
from datetime import datetime, timedelta, timezone
from azure.identity import ManagedIdentityCredential, DefaultAzureCredential
from azure.storage.blob import (
    BlobServiceClient, generate_blob_sas, BlobSasPermissions
)

load_dotenv()
ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT","ytstore7135")
CONTAINER = os.getenv("AZURE_BLOB_CONTAINER","audio")

# Use Managed Identity in Azure; locally DefaultAzureCredential also works
def _credential():
    # Tries MI in Azure; falls back to developer creds locally
    return DefaultAzureCredential(exclude_interactive_browser_credential=False)

def _svc_client():
    url = f"https://{ACCOUNT_NAME}.blob.core.windows.net"
    return BlobServiceClient(account_url=url, credential=_credential())

def upload_and_sign(local_path: str, ttl_minutes: int = 45) -> str:
    svc = _svc_client()
    name = f"{uuid.uuid4()}/{os.path.basename(local_path)}"
    blob = svc.get_blob_client(container=CONTAINER, blob=name)
    with open(local_path, "rb") as f:
        blob.upload_blob(f, overwrite=True, content_type="audio/wav")

    # Get User Delegation Key (no account key needed)
    udk = svc.get_user_delegation_key(
        key_start_time=datetime.now(timezone.utc) - timedelta(minutes=5),
        key_expiry_time=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    sas = generate_blob_sas(
        account_name=ACCOUNT_NAME,
        container_name=CONTAINER,
        blob_name=name,
        user_delegation_key=udk,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
    )
    return f"{blob.url}?{sas}"
