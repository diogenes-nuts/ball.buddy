"""Name bridging: match Yahoo roster names against pool player names (R3).

Loud, not fuzzy-only: the ladder is alias table -> exact normalized full
name -> first-name-optional containment -> unmatched (with last-name
suggestions). Ambiguity (two-or-more candidates) is NEVER auto-picked — it is
reported and the user resolves it by adding an alias entry to
``data/aliases.json`` (``{"roster name": "pool name"}``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}


def normalize(name: str) -> str:
    """Casefold and strip everything but letters/digits/space; collapse runs.

    Kills apostrophes, periods, and hyphens: ``O'Neal`` -> ``oneal``,
    ``De'Anthony`` -> ``deanthony``.
    """
    cleaned = re.sub(r"[^0-9a-z\s]", "", name.casefold())
    return re.sub(r"\s+", " ", cleaned).strip()


def split_suffix(name: str) -> tuple[str, str]:
    """Split a normalized name into (base, suffix); suffix in {jr, sr, ...}.

    "james harden jr" -> ("james harden", "jr").
    """
    parts = name.split()
    if len(parts) > 1 and parts[-1] in _SUFFIXES:
        return " ".join(parts[:-1]), parts[-1]
    return name, ""


@dataclass
class MatchReport:
    """Result of bridging roster names against the pool."""

    matched: dict[str, str] = field(default_factory=dict)  # roster -> pool
    ambiguous: dict[str, list[str]] = field(default_factory=dict)  # roster -> pool candidates
    unmatched: list[tuple[str, list[str]]] = field(default_factory=list)  # (roster, suggestions)
    pool_unused: int = 0

    @property
    def problem_count(self) -> int:
        return len(self.ambiguous) + len(self.unmatched)

    def banner_text(self) -> str:
        """The loud banner line; empty when every roster name resolved."""
        bits = []
        if self.unmatched:
            bits.append(f"{len(self.unmatched)} roster players unmatched")
        if self.ambiguous:
            bits.append(f"{len(self.ambiguous)} ambiguous")
        if not bits:
            return ""
        return " · ".join(bits) + " — add aliases.json entries to fix"


def last_name(normalized: str) -> str:
    return normalized.split()[-1] if normalized else ""


def bridge(
    roster_names: list[str],
    pool_names: list[str],
    aliases: dict[str, str] | None = None,
) -> MatchReport:
    """Bridge roster (Yahoo) names against pool (Hashtag) names.

    Steps per roster name:
      1. alias table — exact roster-name key wins (case-sensitive on the raw
         roster name; the alias value is looked up in the pool exactly);
      2. exact normalized full-name hit in the pool;
      3. first-name-optional containment ("Nikola Jokic" <-> "Jokic");
      4. else unmatched with top-3 last-name suggestions.
    Step 2/3 with 2+ pool candidates -> ambiguous (never auto-picked).
    """
    aliases = aliases or {}
    pool_norm: dict[str, list[str]] = {}
    for pool_name in pool_names:
        pool_norm.setdefault(normalize(pool_name), []).append(pool_name)
    used_pool: set[str] = set()

    report = MatchReport()
    for roster_name in roster_names:
        alias = aliases.get(roster_name)
        if alias is not None:
            alias_norm = normalize(alias)
            if alias_norm in pool_norm:
                report.matched[roster_name] = alias
                used_pool.update(pool_norm[alias_norm])
                continue
            report.unmatched.append((roster_name, _suggest(pool_norm, roster_name, pool_norm)))
            continue

        norm = normalize(roster_name)
        exact = pool_norm.get(norm, [])
        if len(exact) == 1:
            report.matched[roster_name] = exact[0]
            used_pool.add(exact[0])
            continue
        if len(exact) > 1:
            report.ambiguous[roster_name] = exact
            continue

        # Step 3: containment, first name optional.
        base, suffix = split_suffix(norm)
        candidates: list[str] = []
        for pool_norm_name, pool_display in pool_norm.items():
            pool_base, pool_suffix = split_suffix(pool_norm_name)
            if not pool_base:
                continue
            first_last_match = base == pool_base
            first_only_match = (
                pool_base in base or base in pool_base
            ) and pool_base != base
            suffix_ok = (suffix == pool_suffix) if (suffix or pool_suffix) else True
            if (first_last_match or first_only_match) and suffix_ok:
                candidates.extend(pool_display)
        if len(candidates) == 1:
            report.matched[roster_name] = candidates[0]
            used_pool.add(candidates[0])
        elif len(candidates) > 1:
            report.ambiguous[roster_name] = sorted(set(candidates))
        else:
            report.unmatched.append((roster_name, _suggest(pool_norm, roster_name, pool_norm)))

    report.pool_unused = len(pool_names) - len(used_pool)
    return report


def _suggest(
    pool_norm: dict[str, list[str]],
    roster_name: str,
    pool_norm_all: dict[str, list[str]],
) -> list[str]:
    """Top-3 suggestions by last-name equality (fallback: last-token prefix)."""
    want = last_name(split_suffix(normalize(roster_name))[0])
    if not want:
        return []
    exact = sorted(
        display
        for pool_norm_name, displays in pool_norm.items()
        if last_name(split_suffix(pool_norm_name)[0]) == want
        for display in displays
    )
    if exact:
        return exact[:3]
    prefix = sorted(
        display
        for pool_norm_name, displays in pool_norm_all.items()
        if last_name(split_suffix(pool_norm_name)[0]).startswith(want[:5]) and len(want) >= 5
        for display in displays
    )
    return prefix[:3]


__all__ = ["MatchReport", "bridge", "last_name", "normalize", "split_suffix"]
