import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bh.scraper import Scraper  # noqa: E402

VARIANTS = {
    "dl": """<main><h1>Bellhaven Meadows of Findlay</h1><dl><dt>Address</dt><dd>1800 N Blanchard St<br>Findlay, OH 45840</dd>
             <dt>Phone</dt><dd>(231) 533-2969</dd><dt>Care Offerings</dt><dd><ul><li>Assisted Living</li><li>Memory Support</li></ul></dd>
             <dt>Administrator</dt><dd>Sam Pruitt</dd></dl></main>""",
    "inline-strong": """<main><h1>Bellhaven Meadows of Findlay</h1><p><strong>Address</strong><br>1800 N Blanchard St<br>Findlay, OH 45840</p>
             <p><strong>Care Offerings</strong><br><span>Assisted Living</span><span>Memory Support</span></p>
             <p><strong>Phone</strong><br>(231) 533-2969</p></main>""",
    "concatenated": """<main><h1>Bellhaven Meadows of Findlay</h1><div class=label>Address:</div><div>1800 N Blanchard St, Findlay, OH 45840</div>
             <div class=label>Care Offerings</div><div>Assisted LivingMemory Support</div></main>""",
}


def test_variants():
    s = Scraper(base_url="http://x")
    for name, html in VARIANTS.items():
        loc = s.parse_detail(f"<html><body>{html}<footer>400 Bellhaven Way, Columbus, OH 43215</footer></body></html>",
                             "/communities/bellhaven-meadows-of-findlay")
        assert loc["name"] == "Bellhaven Meadows of Findlay", name
        assert (loc["street"], loc["city"], loc["state"], loc["zip"]) == ("1800 N Blanchard St", "Findlay", "OH", "45840"), (name, loc)
        assert loc["care_offerings"] == ["Assisted Living", "Memory Support"], (name, loc["care_offerings"])
