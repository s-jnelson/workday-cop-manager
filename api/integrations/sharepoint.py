"""
SharePoint integration stub — ready to wire up when a SharePoint site is available.

To activate:
  1. Register an Azure app with Sites.ReadWrite.All (or Sites.Selected) permission.
  2. Save the tenant_id, client_id, client_secret, and site_url via POST /api/sharepoint/config.
  3. Install the Microsoft Graph SDK:  pip install msgraph-sdk
  4. Replace the stub methods below with real Graph API calls.
"""

from __future__ import annotations
import json
import os
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"
_CONFIG_FILE = DATA_DIR / "config.json"


def _load_sp_config() -> dict:
    if not _CONFIG_FILE.exists():
        return {}
    try:
        cfg = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        return cfg.get("sharepoint", {})
    except Exception:
        return {}


def is_configured() -> bool:
    """Return True if all required SharePoint fields are present in config."""
    cfg = _load_sp_config()
    return all(cfg.get(k) for k in ("site_url", "tenant_id", "client_id", "client_secret"))


def test_connection() -> dict:
    """
    Test the SharePoint connection.
    Returns {"ok": bool, "message": str, "site_url": str | None}
    """
    cfg = _load_sp_config()
    if not is_configured():
        return {"ok": False, "message": "SharePoint not configured — add credentials in Settings.", "site_url": None}

    # TODO: Replace stub with real Graph API call once msgraph-sdk is installed:
    #   from msgraph import GraphServiceClient
    #   from azure.identity import ClientSecretCredential
    #   credential = ClientSecretCredential(cfg["tenant_id"], cfg["client_id"], cfg["client_secret"])
    #   client = GraphServiceClient(credential, scopes=["https://graph.microsoft.com/.default"])
    #   site = await client.sites.by_site_id(cfg["site_id"]).get()
    #   return {"ok": True, "message": f"Connected to {site.display_name}", "site_url": cfg["site_url"]}

    return {"ok": False, "message": "SharePoint SDK not yet installed — stub mode.", "site_url": cfg.get("site_url")}


def sync_asset(asset: dict) -> str | None:
    """
    Upload/update an asset to SharePoint Documents.
    Returns the SharePoint document URL, or None if not configured.

    TODO: implement with Graph API PUT /sites/{site-id}/drive/root:/{path}:/content
    """
    if not is_configured():
        return None
    # Stub — return None until SDK is wired up
    return None


def get_document_url(object_id: str, object_type: str) -> str | None:
    """
    Resolve a SharePoint URL for a given CoP object.
    Returns the URL or None if the object has no SharePoint record.
    """
    if not is_configured():
        return None
    # Stub — future: query SharePoint list for matching object_id metadata
    return None


def sync_all_assets(assets: list[dict]) -> dict:
    """
    Bulk-sync all assets to SharePoint.
    Returns {"synced": int, "failed": int, "errors": list}
    """
    if not is_configured():
        return {"synced": 0, "failed": 0, "errors": ["SharePoint not configured"]}
    # Stub
    return {"synced": 0, "failed": 0, "errors": ["SharePoint SDK not yet installed"]}
