"""Runtime configuration. Everything can be overridden with environment variables."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BASE_URL = os.environ.get("BH_BASE_URL", "https://analyst-assessment-production.up.railway.app").rstrip("/")
API_BASE = os.environ.get("BH_API_BASE", BASE_URL + "/api/v1").rstrip("/")
TOKEN = os.environ.get("BH_TOKEN", "")

DB_PATH = Path(os.environ.get("BH_DB_PATH", ROOT / "data" / "state.db"))
SNAPSHOT_DIR = Path(os.environ.get("BH_SNAPSHOT_DIR", ROOT / "data" / "snapshots"))

# Link template for "open in CRM browser" buttons in the review app. Adjust if the
# CRM browser uses a different URL shape.
CRM_BROWSER_ACCOUNT_URL = os.environ.get("BH_CRM_BROWSER_URL", BASE_URL + "/crm/accounts/{id}")

# Name of the operator whose website we sync against.
OPERATOR_NAME = "Bellhaven Senior Living"
OPERATOR_KEYWORD = "bellhaven"
# Corporate office from the website footer; used to pick the canonical parent account.
CORPORATE_STREET = "400 Bellhaven Way"

# If a facility's parent is a *duplicate copy* of the Bellhaven parent record (same owner,
# split record), moving it to the canonical Bellhaven parent is a data fix, not a change of
# ownership. Set to True to apply the CHOW SOP to those moves too.
SOP_APPLIES_TO_DUPLICATE_PARENT = os.environ.get("BH_SOP_DUP_PARENT", "0") == "1"

NOTE_TAG = "[bellhaven-sync]"

# The API spec does not publish field names, so each logical field lists the names we
# accept. The real key is detected from live data at runtime (see crm.detect_fields).
FIELD_ALIASES = {
    "id": ["id", "account_id"],
    "name": ["name", "account_name"],
    "street": ["street", "address", "address1", "street_address", "address_line1"],
    "city": ["city"],
    "state": ["state"],
    "zip": ["zip", "zip_code", "postal_code", "zipcode"],
    "phone": ["phone", "phone_number"],
    "parent_id": ["parent_id", "parent_account_id"],
    "status": ["status"],
    "note": ["note", "notes"],
    "lifetime_revenue": ["lifetime_revenue"],
    "outstanding_ar": ["outstanding_ar"],
    "duplicate_of_account": ["duplicate_of_account", "duplicate_of"],
    "chow_current_account": ["chow_current_account"],
    "care": ["care_offerings", "care_types", "care_levels", "services", "offerings", "service_lines"],
    "website": ["website", "url"],
}

STATUS_ACTIVE = "Active"
STATUS_INACTIVE = "Inactive"
STATUS_REVIEW = "Needs Review"
