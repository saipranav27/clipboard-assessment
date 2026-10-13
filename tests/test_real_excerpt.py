"""Regression test on the real sandbox data (website + 43 Bellhaven-related CRM accounts)."""
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent.parent), str(Path(__file__).resolve().parent)]
from real_excerpt import LOCATIONS, ACCOUNTS  # noqa: E402
from bh import config  # noqa: E402
from bh.matcher import build_proposals  # noqa: E402


def test_real_excerpt():
    fields = {k: next((a for a in v if a in ACCOUNTS[0]), None) for k, v in config.FIELD_ALIASES.items()}
    props, rep = build_proposals(LOCATIONS, ACCOUNTS, fields)
    got = {(p["kind"], p.get("account_id") or p.get("site_slug")) for p in props}
    expect = {
        ("CHOW", "001U6RW32TY0WSXZZB"),          # Tiffin: Cedar Trail, rev + AR
        ("CHOW", "001A34WFSUYHCRBLFT"),          # Marietta: Cedar Trail, rev + AR
        ("REPARENT", "001LGFPBJY4N9MB6KL"),      # Lima: Harborview, rev but AR 0
        ("REPARENT", "001H1JMVZWP46D5VUF"),      # Zanesville: no revenue
        ("REPARENT", "001UKEFGADQ8YCZ4YM"),      # Findlay: no parent, AR 0
        ("DUPLICATE", "001JD2MWRA74LTSN24"), ("DUPLICATE", "001BLYF02K97SZLZHH"),
        ("DUPLICATE", "0011AB44D05WLA9HTX"), ("DUPLICATE", "00159PL81N38KM4FHM"),
        ("DUPLICATE", "001QU150PM4Z15UA71"),
        ("UPDATE_FIELDS", "001RJU1X4NBWC1Q0G7"), ("UPDATE_FIELDS", "0017MN2JYAJBDS8WQZ"),
        ("UPDATE_FIELDS", "0013NUZQHQUEZ8DXEG"), ("UPDATE_FIELDS", "001NXP9X46CWEPSLSV"),
        ("UPDATE_FIELDS", "001CF3LDWVRGL09P4F"),
        ("ORPHAN", "00116ETS45BL7DTQP7"), ("ORPHAN", "0016PVXH4B25HWR7QE"), ("ORPHAN", "001SXSF4ELF0Z2LGDM"),
    }
    assert expect <= got, expect - got
    # Already-correct accounts (incl. Bellhaven-parented ones with AR) get nothing; no cosmetic renames.
    for quiet in ("0019Y4J61ZBG4R00CD", "001R4PXTUD9R6FNN8V", "001KC1NG7EZDEKKA3T", "001TZCSTBZFM6K5BGN",
                  "00191H7JR16471SZ34", "0010KJFP601YNTZVDA", "001RJ0D7Z5MAZN5HX5", "001L3LGR6W69J8DYYV"):
        assert not any(k[1] == quiet for k in got), quiet
    assert all(p["confidence"] != "low" for p in props), [p["title"] for p in props if p["confidence"] == "low"]
