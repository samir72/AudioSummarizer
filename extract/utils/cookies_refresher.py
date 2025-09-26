import os, time, hashlib, tempfile, threading
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobClient
from dotenv import load_dotenv

load_dotenv()
ACCOUNT  = os.getenv("AZURE_STORAGE_ACCOUNT")  # storage account name
CONTAINER= os.getenv("COOKIES_CONTAINER")
BLOB     = os.getenv("COOKIES_BLOB")
OUT_PATH = os.getenv("COOKIES_PATH")
REFRESH  = int(os.getenv("COOKIES_REFRESH_SEC"))

def _sha256(b: bytes) -> str: return hashlib.sha256(b).hexdigest()
def _read(path: str) -> bytes:
    try:
        with open(path, "rb") as f: return f.read()
    except: return b""

def _atomic_write(path: str, data: bytes):
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".cookies.", dir=d)
    with os.fdopen(fd, "wb") as f: f.write(data)
    os.replace(tmp, path)
    try: os.chmod(path, 0o600)
    except: pass

def refresh_once():
    if not ACCOUNT: 
        print("[cookies] ACCOUNT not set"); return
    cred = DefaultAzureCredential()  # uses ACA managed identity
    bc = BlobClient(
        account_url=f"https://{ACCOUNT}.blob.core.windows.net",
        container_name=CONTAINER,
        blob_name=BLOB,
        credential=cred,
    )
    new = bc.download_blob(max_concurrency=1).readall()
    if not new.strip():
        print("[cookies] WARN: blob is empty; skipping")
        return
    if _sha256(new) != _sha256(_read(OUT_PATH)):
        _atomic_write(OUT_PATH, new)
        print(f"[cookies] updated -> {OUT_PATH} (bytes={len(new)})")

def start_cookies_refresher():
    # initial fetch before serving traffic
    try: refresh_once()
    except Exception as e: print(f"[cookies] initial refresh error: {e}")
    # periodic refresh
    def loop():
        while True:
            time.sleep(REFRESH)
            try: refresh_once()
            except Exception as e: print(f"[cookies] refresh error: {e}")
    threading.Thread(target=loop, daemon=True).start()
