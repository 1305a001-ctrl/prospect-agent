"""Detect chains and mark branches.

Three heuristics, in order of precedence:
  1. Domain match  — leads sharing a website root domain are the same chain
  2. Name pattern  — split on '•', '|', ' - ', '@' to find a "<chain> · <branch>" shape
  3. Token-prefix cluster — within (niche × geo_country), if 3+ leads share their
                           first 2-3 normalized name tokens, treat as chain

For each cluster we pick a single 'parent' (most reviews, then no website,
then alphabetical) and mark the rest 'branch'. Leads not in any cluster
stay 'standalone'.

Pure logic — DB I/O lives in db.py.
"""
import logging
import re
from collections import defaultdict
from urllib.parse import urlparse

log = logging.getLogger(__name__)

NAME_SEPARATORS = re.compile(r"\s*[•|@]\s*|\s+-\s+")
NORMALIZE = re.compile(r"[^a-zA-Z0-9 ]+")
WHITESPACE = re.compile(r"\s+")
PARENT_HINTS = ("klinik", "clinic", "restaurant", "restoran", "the", "kedai")


def normalize(name: str) -> str:
    return WHITESPACE.sub(" ", NORMALIZE.sub(" ", name)).lower().strip()


def root_domain(url: str | None) -> str | None:
    """Return the registrable-root-ish part of a URL. Naive — doesn't use a PSL."""
    if not url:
        return None
    try:
        host = urlparse(url).hostname or ""
    except Exception:  # noqa: BLE001
        return None
    host = host.lstrip("www.")
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in {"com", "co", "net"}:
        # e.g. mediviron.com.my → mediviron
        return parts[-3]
    if len(parts) >= 2:
        return parts[-2]
    return host or None


def name_root(name: str) -> str | None:
    """Extract the chain-side of a 'Chain • Branch' style name. None if no clear split."""
    if not name:
        return None
    parts = NAME_SEPARATORS.split(name, maxsplit=1)
    if len(parts) < 2:
        return None
    left, right = parts[0].strip(), parts[1].strip()
    # Accept the split only if both sides are non-trivial
    if len(left) < 4 or len(right) < 2:
        return None
    return left


def token_prefix(name: str, n: int = 2) -> str | None:
    """First n meaningful tokens after normalisation, or None."""
    tokens = [t for t in normalize(name).split() if t and t not in PARENT_HINTS]
    if len(tokens) < n:
        return None
    return " ".join(tokens[:n])


# ─── Cluster + assignment ────────────────────────────────────────────────────


def detect_chains(leads: list[dict]) -> dict[str, dict]:
    """
    Given a list of lead dicts (need: id, business_name, business_website_url,
    business_review_count, niche, geo_country), return a mapping
    `lead_id → {'chain_name': str, 'chain_role': 'parent'|'branch'|'standalone'}`.

    Idempotent — call repeatedly.
    """
    # Step 1: cluster by signal
    by_domain: dict[str, list[dict]] = defaultdict(list)
    by_name_root: dict[tuple[str, str], list[dict]] = defaultdict(list)
    by_token_prefix: dict[tuple[str, str, str], list[dict]] = defaultdict(list)

    for lead in leads:
        d = root_domain(lead.get("business_website_url"))
        if d:
            by_domain[d].append(lead)

        nr = name_root(lead.get("business_name") or "")
        if nr:
            by_name_root[(lead["niche"], normalize(nr))].append(lead)

        tp = token_prefix(lead.get("business_name") or "", n=2)
        if tp:
            key = (lead["niche"], lead["geo_country"], tp)
            by_token_prefix[key].append(lead)

    # Step 2: build clusters in priority order — domain > name_root > token_prefix
    assignments: dict[str, dict] = {}

    def assign(group: list[dict], chain_label: str) -> None:
        if len(group) < 2:
            return
        # Filter out leads already assigned (a domain match wins over a name match)
        unassigned = [g for g in group if g["id"] not in assignments]
        if len(unassigned) < 2:
            # Even if a domain match assigned some, mark the remainder under the same chain
            for g in unassigned:
                assignments[g["id"]] = {"chain_name": chain_label, "chain_role": "branch"}
            return

        # Pick parent: most reviews, then no website, then first alphabetical
        unassigned.sort(
            key=lambda g: (
                -(g.get("business_review_count") or 0),
                bool(g.get("business_website_url")),
                g.get("business_name") or "",
            ),
        )
        parent = unassigned[0]
        assignments[parent["id"]] = {"chain_name": chain_label, "chain_role": "parent"}
        for g in unassigned[1:]:
            assignments[g["id"]] = {"chain_name": chain_label, "chain_role": "branch"}

    # Domain clusters first (highest precision)
    for domain, group in by_domain.items():
        if len(group) >= 2:
            chain_label = _humanize_chain_label(group)
            assign(group, chain_label)

    # Name-root clusters next (Mediviron •, BP Healthcare -, etc.)
    for (_niche, root), group in by_name_root.items():
        if len(group) >= 2:
            assign(group, _humanize(root))

    # Token-prefix clusters last (3+ required to avoid false positives)
    for (_niche, _geo, tp), group in by_token_prefix.items():
        if len(group) >= 3:
            assign(group, _humanize(tp))

    # Any lead not assigned is standalone
    for lead in leads:
        if lead["id"] not in assignments:
            assignments[lead["id"]] = {"chain_name": None, "chain_role": "standalone"}

    return assignments


def _humanize(s: str) -> str:
    """Title-case for chain labels."""
    return " ".join(w.capitalize() for w in s.split())


def _humanize_chain_label(group: list[dict]) -> str:
    """Pick the most common 'name root' from the group, falling back to the domain."""
    roots = [name_root(g.get("business_name") or "") or "" for g in group]
    roots = [r for r in roots if r]
    if roots:
        return _humanize(max(set(roots), key=roots.count))
    # No name pattern — use the domain as label
    return _humanize(root_domain(group[0].get("business_website_url")) or "Unnamed Chain")
