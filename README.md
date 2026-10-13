# bellhaven-sync

Keeps CRM parent/child ownership in sync with the Bellhaven Senior Living website.

```
website ──scrape──▶ locations ─┐
                               ├─▶ matcher ─▶ proposals (SQLite queue) ─▶ review app ─approve─▶ CRM API
CRM API ──list────▶ accounts ──┘                                          (nothing writes without approval)
```

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export BH_TOKEN=bh_xxxxxxxx              # your CRM token

python explore.py                        # read-only: field names, parents, Bellhaven-related accounts
python run_pipeline.py --dry-run         # print proposals without queueing
python run_pipeline.py                   # queue proposals
python app.py                            # review at http://127.0.0.1:5050
python -m pytest -q                      # offline tests against a mock site + CRM
```

Optional env vars: `BH_PARENT_ID` (force the canonical Bellhaven parent), `BH_CRM_BROWSER_URL`
(link template for "open in CRM", default `<base>/crm/accounts/{id}`), `BH_SOP_DUP_PARENT=1`.

## Layout

| File | Role |
|---|---|
| `bh/scraper.py` | Crawls home, about and every `/communities?page=N`; parses each detail page by label (Address, Phone, Care Offerings) |
| `bh/matcher.py` | Scoring, duplicate/CHOW detection, SOP, proposal builders |
| `bh/normalize.py` | Street/name/city/ZIP/phone normalization and similarity |
| `bh/store.py` | Proposal queue, fingerprints, run history (re-run safety) |
| `bh/apply.py` | Executes approved operations with precondition checks |
| `bh/crm.py` | API client; detects real field names from live data |
| `app.py` | Review UI (Flask) |
| `run_pipeline.py` | Daily entry point |
| `schedule/crontab.txt`, `.github/workflows/daily-sync.yml` | Schedule configs |

## Proposal types

| Type | When | What approval writes |
|---|---|---|
| Field fix | Matched account has outdated name/address/ZIP, empty phone, wrong care offerings, or non-Active status | PATCH changed fields; note records the old name |
| Re-parent | Website lists it, CRM parent isn't Bellhaven, and **not** (revenue > 0 AND AR > 0) | PATCH `parent_id` |
| Change of ownership | Same, but revenue > 0 AND AR > 0 | POST new account under Bellhaven; PATCH old account's `chow_current_account` only |
| Link CHOW pair | An old-owner record with revenue+AR *and* a Bellhaven record both exist for one facility | PATCH old `chow_current_account` → existing Bellhaven record |
| Duplicate | Several live accounts match one location | Loser: `duplicate_of_account` → survivor, status Inactive |
| Duplicate parent | A second "Bellhaven Senior Living" top-level record | Same as Duplicate |
| New location | No account matches | POST account under Bellhaven |
| Not on website | Under Bellhaven, matches no location | Status Needs Review + note (parent kept) |

## Safety

* The pipeline never writes to the CRM. Only `app.py` does, and only on approve.
* Each proposal has a fingerprint of (type, subject, exact values to write). Approved, rejected,
  applied or failed fingerprints are never queued again; pending items no longer generated become `stale`.
* Approve is atomic (`pending → approved` in one UPDATE), so a double-click cannot apply twice.
* Patches carry an `expect` precondition (e.g. current `parent_id`); if the CRM changed since
  proposal time, the write is refused and the reviewer is told to re-run.
* Creates check that no live account already exists at that street + ZIP.
* Notes are appended, never overwritten.
* The pipeline aborts if the scrape returns fewer than 5 locations, so a broken scrape can't flag the whole portfolio as gone.
