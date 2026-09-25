"""Only TYPESAFE_API_KEY and this integration's named Windows credential."""
import os
import win32cred
import pywintypes

TARGET = "Codex/jev-bridge/TYPESAFE_API_KEY"

def resolve_key():
    value = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if value:
        return value, "environment"
    try:
        item = win32cred.CredRead(TARGET, win32cred.CRED_TYPE_GENERIC)
        blob = item["CredentialBlob"]
        value = blob.decode("utf-16-le") if isinstance(blob, bytes) else blob
        return value, "windows-credential-manager"
    except pywintypes.error as exc:
        if exc.winerror == 1168:
            return None, "missing"
        raise RuntimeError("CREDENTIAL_STORE_UNAVAILABLE") from None

def save_key(value):
    if not value or not value.isascii() or any(c.isspace() for c in value):
        raise ValueError("Enter a non-empty API key without whitespace.")
    win32cred.CredWrite({"Type": win32cred.CRED_TYPE_GENERIC,
        "TargetName": TARGET, "UserName": "TYPESAFE_API_KEY",
        "CredentialBlob": value,
        "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE}, 0)

def remove_key():
    try:
        win32cred.CredDelete(TARGET, win32cred.CRED_TYPE_GENERIC)
    except pywintypes.error as exc:
        if exc.winerror != 1168:
            raise RuntimeError("CREDENTIAL_DELETE_FAILED") from None
