"""Scrape every Bellhaven community from the public website.

Discovery is deliberately broader than the paginated directory: detail links are collected
from every page we visit (home, about, each directory page), because some communities are
linked only from the homepage (e.g. a newly acquired one announced in a banner).
"""
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from . import config
from .normalize import clean

CARE_VOCAB = [
    "Short-Term Rehabilitation & Nursing", "Short-Term Rehabilitation and Nursing",
    "Independent Living", "Assisted Living", "Memory Support", "Memory Care",
    "Skilled Nursing", "Long-Term Care", "Respite Care", "Hospice", "Rehabilitation",
]
_CARE_RE = re.compile("|".join(re.escape(v) for v in sorted(CARE_VOCAB, key=len, reverse=True)), re.I)
LABELS = ["address", "phone", "care offerings", "care offering", "services", "administrator",
          "executive director", "email", "hours", "formerly known as", "previously known as"]
_CITY_LINE = re.compile(r"^(?P<city>[A-Za-z .'\-]+),\s*(?P<state>[A-Z]{2})\s+(?P<zip>\d{5})(?:-\d{4})?$")
_DETAIL = re.compile(r"^/communities/[a-z0-9][a-z0-9\-]*/?$")


class Scraper:
    def __init__(self, base_url=None, session=None):
        self.base = (base_url or config.BASE_URL).rstrip("/")
        self.s = session or requests.Session()
        self.s.headers.setdefault("User-Agent", "bellhaven-sync/1.0 (data quality pipeline)")

    def _get(self, url):
        r = self.s.get(url, timeout=30)
        return r

    def _detail_links(self, soup):
        links = set()
        for a in soup.find_all("a", href=True):
            path = urlparse(urljoin(self.base + "/", a["href"])).path
            if _DETAIL.match(path):
                links.add(path.rstrip("/"))
        return links

    def discover(self):
        """Return {path: set(sources)} for every community detail page we can find."""
        found = {}

        def add(links, source):
            for p in links:
                found.setdefault(p, set()).add(source)

        for path in ("/", "/about"):
            r = self._get(self.base + path)
            if r.ok:
                add(self._detail_links(BeautifulSoup(r.text, "html.parser")), f"page:{path}")

        # Walk ?page=N until a page is missing, empty, or repeats links we already have
        # (some servers clamp out-of-range pages to the last page).
        for page_no in range(1, 101):
            url = f"{self.base}/communities" + (f"?page={page_no}" if page_no > 1 else "")
            r = self._get(url)
            if not r.ok:
                break
            links = self._detail_links(BeautifulSoup(r.text, "html.parser"))
            new = {p for p in links if "directory" not in found.get(p, set())}
            add(links, "directory")
            if not links or not new:
                break
        return found

    def parse_detail(self, html, path):
        soup = BeautifulSoup(html, "html.parser")
        main = soup.find("main") or soup.body or soup
        for tag in main.find_all(["nav", "footer", "script", "style", "header"]):
            tag.decompose()
        h1 = main.find("h1") or soup.find("h1")
        name = clean(h1.get_text(" ")) if h1 else ""
        lines = [clean(l) for l in main.get_text("\n").splitlines() if clean(l)]

        def block(*labels):
            for i, line in enumerate(lines):
                if line.lower().rstrip(":") in labels:
                    out = []
                    for nxt in lines[i + 1:]:
                        if nxt.lower().rstrip(":") in LABELS:
                            break
                        out.append(nxt)
                    return out
                m = re.match(rf"^({'|'.join(labels)})\s*:\s*(.+)$", line, re.I)
                if m:
                    return [m.group(2)]
            return []

        addr_lines = block("address")
        street = city = state = zip_ = ""
        joined = ", ".join(addr_lines[:3])
        for i, l in enumerate(addr_lines[:3]):
            m = _CITY_LINE.match(l)
            if m:
                street = ", ".join(addr_lines[:i]) if i else ""
                city, state, zip_ = m["city"].strip(), m["state"], m["zip"]
                break
        if not city:  # single-line "123 Main St, Town, OH 44000"
            m = re.match(r"^(?P<street>.+?),\s*(?P<city>[^,]+),\s*(?P<state>[A-Z]{2})\s+(?P<zip>\d{5})", joined)
            if m:
                street, city, state, zip_ = m["street"], m["city"].strip(), m["state"], m["zip"]

        care = self._care_from_lines(block("care offerings", "care offering", "services")) or self._care_from_dom(main)
        phone = (block("phone") or [""])[0]
        admin = (block("administrator", "executive director") or [""])[0]
        formerly = (block("formerly known as", "previously known as") or [""])[0]
        page_text = " ".join(lines).lower()
        flags = [w for w in ("coming soon", "closed", "no longer", "permanently") if w in page_text]
        return {
            "slug": path.rsplit("/", 1)[-1], "url": self.base + path, "name": name,
            "street": street, "city": city, "state": state, "zip": zip_,
            "phone": phone, "care_offerings": care, "administrator": admin,
            "formerly_known_as": formerly, "page_flags": flags,
        }

    @staticmethod
    def _care_from_lines(lines):
        out = []
        for l in lines:
            hits = _CARE_RE.findall(l)
            rest = _CARE_RE.sub("", l).strip(" ,;|·•")
            out.extend(hits if hits else [l])
            if hits and rest:
                out.append(rest)
        seen, uniq = set(), []
        for c in out:
            if c.lower() not in seen:
                seen.add(c.lower())
                uniq.append(c)
        return uniq

    @staticmethod
    def _care_from_dom(main):
        label = main.find(string=re.compile(r"^\s*care offerings?\s*:?\s*$", re.I))
        if not label:
            return []
        el = label.parent
        for _ in range(3):  # walk forward to the sibling that holds the items
            sib = el.find_next_sibling()
            if sib is not None:
                items = [clean(x.get_text(" ")) for x in sib.find_all(["li", "span", "a"]) if clean(x.get_text(" "))]
                if items:
                    return Scraper._care_from_lines(items)
                txt = clean(sib.get_text(" "))
                if txt:
                    return Scraper._care_from_lines([txt])
            el = el.parent
        return []

    def scrape(self):
        found = self.discover()
        locations, errors = [], []
        for path in sorted(found):
            r = self._get(self.base + path)
            if r.status_code == 404:
                errors.append({"path": path, "error": "404 - linked but page missing"})
                continue
            if not r.ok:
                errors.append({"path": path, "error": f"HTTP {r.status_code}"})
                continue
            loc = self.parse_detail(r.text, path)
            loc["discovered_via"] = sorted(found[path])
            if not loc["name"]:
                errors.append({"path": path, "error": "no name parsed"})
                continue
            locations.append(loc)
        return locations, errors
