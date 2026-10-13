# Writeup (draft — edit numbers after the real run)

## Matching approach

**Scrape.** I crawl the homepage, About page and every directory page, and collect community
links from all of them. The directory lists 34 communities, but Bellhaven Meadows of Findlay
is only linked from the homepage "new this year" banner, so directory-only scraping misses it.
Detail pages are parsed by label (Address / Phone / Care Offerings) rather than by CSS class,
and care offerings are split against a known vocabulary because the markup renders them back to back.

**Match.** Every location is scored against every CRM account on: normalized street (St/Street,
N/North, suite stripped), ZIP, city, state, phone and name similarity (name similarity ignores
"Bellhaven", "of", "the" and so on, since rebrands change exactly those words). A pair counts as a match only with
address evidence (street + ZIP or city), phone + ZIP/city, or a near-identical name in the same city,
and **never** when states differ or when both records have street addresses that disagree. That keeps
"Bellhaven of Carlisle, PA" away from "Bellhaven of New Carlisle, OH", and stops a same-named
facility at a different address from being swallowed.

Accounts that already carry `chow_current_account` or `duplicate_of_account` are resolved to the
record they point at before matching, so finished CHOW pairs and resolved duplicates are not
re-flagged. Each account is assigned to the single location it scores best against.

**Classify.** For each location:
- No match → *New location* (create under Bellhaven, with the nearest-name CRM accounts as evidence).
- Several matches → pick a survivor (under Bellhaven, Active, has billing history, strongest match,
  most complete, oldest id). Losers become *Duplicate* (`duplicate_of_account` + Inactive), except an
  old-owner record with revenue AND AR next to a Bellhaven record: that's a change-of-ownership pair that's
  missing its link, so I set `chow_current_account` and leave everything else alone.
- Parent isn't Bellhaven → SOP: revenue > 0 AND AR > 0 → *Change of ownership* (new account under Bellhaven,
  old account untouched except `chow_current_account`); otherwise *Re-parent*.
- Field differences → one *Field fix* proposal (name, street, city, ZIP, care offerings, status → Active).
  Renames record the former name in the note. Phone is only filled when empty, because the CRM may hold a direct line.

Accounts under Bellhaven that no longer appear on the website get **Needs Review + a note**, not Inactive
and not a parent change. The site can't tell me whether the facility closed or was sold or who owns it now,
and clearing the parent would itself be a parent move that needs the billing check. A human should make that call.

Choices worth flagging:
- *Duplicate Bellhaven parent records* (e.g. "Bellhaven Senior Living, LLC"): children are moved to the
  canonical parent as a plain re-parent, because ownership didn't change; it's the same owner in a split
  record. (Configurable with `BH_SOP_DUP_PARENT=1` if billing wants the CHOW treatment anyway.)
- Notes are appended, not overwritten, and every note is tagged `[bellhaven-sync]` with a date.

## Re-run safety
Proposals are fingerprinted on (type, account/location, exact values to write). Decided fingerprints
never come back; if the website changes later, the new target makes a new fingerprint, which is the
right behaviour. Approval is atomic, patches re-check preconditions against the live record, and
creates refuse if an account already exists at the address.

## How I used AI tools
I used Claude to read the site and API spec, propose the architecture, and write the first version of
the code. I checked its work by building a mock site and CRM seeded with each trap (CHOW with and
without AR, duplicate parent, duplicate facility records, finished CHOW pair, missing CHOW link,
rebrand, wrong ZIP, inactive account, homepage-only location, same-named facility in another state)
and asserting the end state of the CRM, plus re-run, double-approve and stale-write tests. It caught
two real bugs: the care-offerings parser grabbing the phone line on one markup, and noisy
proposals from phone diffs. Then I ran `explore.py` on the real sandbox and tuned against it: _[fill in]_.

## Results on my CRM copy
_[fill in: N locations scraped, N matched, proposals by type, approved/rejected and why]_

## What I'd build next
- Durable shared state (Postgres) instead of SQLite, plus reviewer identity on each decision.
- Alerts when the scrape shape changes (location count drops, labels missing).
- A "reassign" control on duplicates so a reviewer can pick a different survivor.
- Use the other operators' websites (Harborview, Cedar Trail) to work out where orphaned facilities went.
- Contact moves on CHOW (contacts currently stay on the old account).
- Precision tracking: approve/reject rate per proposal type and confidence, to tune thresholds.

## Time spent
_[honest estimate]_
