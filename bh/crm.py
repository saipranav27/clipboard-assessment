"""Thin client for the CRM sandbox API, tolerant of the response envelope shape."""
import time
import requests

from . import config


class CRMError(Exception):
    pass


class CRM:
    def __init__(self, api_base=None, token=None, session=None):
        self.api_base = (api_base or config.API_BASE).rstrip("/")
        token = (token if token is not None else config.TOKEN).strip()
        if not token:
            raise CRMError("Set BH_TOKEN to your CRM API token.")
        self.s = session or requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/json"})
        self.fields = None  # logical -> real key, set by detect_fields()

    # -- low level -----------------------------------------------------------
    def _req(self, method, path, **kw):
        url = self.api_base + path
        for attempt in range(4):
            r = self.s.request(method, url, timeout=30, **kw)
            if r.status_code in (429, 502, 503, 504) and attempt < 3:
                time.sleep(1.5 * (attempt + 1))
                continue
            if r.status_code >= 400:
                raise CRMError(f"{method} {path} -> {r.status_code}: {r.text[:500]}")
            return r.json() if r.content else {}
        raise CRMError(f"{method} {path} failed after retries")

    @staticmethod
    def _items(body):
        if isinstance(body, list):
            return body, None
        for k in ("items", "results", "data", "accounts", "contacts", "records"):
            if isinstance(body.get(k), list):
                total = body.get("total") or body.get("count") or body.get("total_count")
                return body[k], total
        raise CRMError(f"Unrecognised list response keys: {list(body)[:10]}")

    @staticmethod
    def _one(body):
        if isinstance(body, dict):
            for k in ("account", "data", "item", "contact"):
                if isinstance(body.get(k), dict):
                    return body[k]
        return body

    # -- accounts ------------------------------------------------------------
    def list_accounts(self, **filters):
        """All pages. Stops on an empty page, a page with no new ids, or the reported total.
        Never trusts page_size, since servers often cap it."""
        uniq, seen = [], set()
        for page in range(1, 500):
            body = self._req("GET", "/accounts", params={**filters, "page": page, "page_size": 50})
            items, total = self._items(body)
            new = 0
            for a in items:
                key = a.get("account_id") or a.get("id") or repr(sorted(a.items()))
                if key not in seen:
                    seen.add(key)
                    uniq.append(a)
                    new += 1
            if not items or not new or (total and len(uniq) >= int(total)):
                break
        return uniq

    def get_account(self, account_id):
        return self._one(self._req("GET", f"/accounts/{account_id}"))

    def update_account(self, account_id, data):
        return self._one(self._req("PATCH", f"/accounts/{account_id}", json=data))

    def create_account(self, data):
        return self._one(self._req("POST", "/accounts", json=data))

    def list_contacts(self, account_id):
        try:
            items, _ = self._items(self._req("GET", "/contacts", params={"account_id": account_id, "page_size": 100}))
            return items
        except CRMError:
            return []

    # -- field mapping -------------------------------------------------------
    def detect_fields(self, accounts):
        keys = set()
        for a in accounts[:200]:
            keys.update(a.keys())
        mapping = {}
        for logical, aliases in config.FIELD_ALIASES.items():
            mapping[logical] = next((k for k in aliases if k in keys), None)
        self.fields = mapping
        return mapping

    def key(self, logical):
        """Real API key for a logical field (falls back to the first alias)."""
        if self.fields and self.fields.get(logical):
            return self.fields[logical]
        return config.FIELD_ALIASES[logical][0]


def fget(acct, logical, fields=None):
    """Read a logical field from an account dict using detected or alias keys."""
    if fields and fields.get(logical):
        return acct.get(fields[logical])
    for k in config.FIELD_ALIASES[logical]:
        if k in acct:
            return acct[k]
    return None
