import json
import re


def _normalize(text: str) -> str:
    """Return a canonical lowercase key for a hierarchy label or entity.

    Multi-level (e.g. "8.38.1.5"):
        Strip the "Paragraph " prefix so all variations collapse to the bare ID:
            "8.38.1.5"           →  "8.38.1.5"
            "Paragraph 8.38.1.5" →  "8.38.1.5"

    Single-label (e.g. "Paragraph 1", "Annex 3"):
        Keep the full lowercased form — bare "1" does NOT collide with "paragraph 1":
            "Paragraph 1"  →  "paragraph 1"
            "1"            →  "1"
            "Annex 3"      →  "annex 3"
    """
    t = text.strip().lower()
    if t.startswith("paragraph "):
        bare = t[len("paragraph "):].strip()
        if "." in bare:
            return bare          # multi-level: strip prefix
        return t                 # single-label: keep full form
    return t


def _is_intro_paragraph_entity(entity: str) -> bool:
    """True for any 'Paragraph X' entity without an Annex prefix.

    Covers both single-digit and multi-level references:
        "Paragraph 1"    → True  (matches Introduction > Paragraph 1)
        "Paragraph 2.4"  → True  (matches Introduction > 2 > 2.4)
        "Paragraph 8.38" → True  (try Introduction first, fall back to general)
    Compound entities like "Annex 3 paragraph 4.1" are caught by
    _parse_compound_entity before this check is reached.
    """
    t = entity.strip().lower()
    return t.startswith("paragraph ")


def _parse_compound_entity(entity: str) -> dict | None:
    """Parse compound entity references into their components.

    Recognised patterns:

    1. "Annex X paragraph N.N.N" / "Annex X Paragraph N"
       → {"type": "annex_sub", "annex": "annex x", "sub_key": "<normalised sub>"}

    2. "Appendix N to Annex X"
       → {"type": "appendix_to_annex", "fp_prefix": "annex x - appendix n"}

    Returns None for everything else.
    """
    t = entity.strip()

    # Pattern 1: "Annex X paragraph/Paragraph <sub>"
    m = re.match(r"^(Annex \d+)\s+[Pp]aragraph\s+(\S+)$", t, re.IGNORECASE)
    if m:
        annex = m.group(1).lower()
        sub = m.group(2)
        # Normalise the sub-reference the same way hierarchy labels are stored:
        # multi-level (has dots) → bare number; single digit → "paragraph N"
        if "." in sub:
            sub_key = sub.lower()
        else:
            sub_key = f"paragraph {sub.lower()}"
        return {"type": "annex_sub", "annex": annex, "sub_key": sub_key}

    # Pattern 2: "Appendix N to Annex X"
    m = re.match(r"^Appendix (\S+)\s+to\s+(Annex \d+)$", t, re.IGNORECASE)
    if m:
        appendix_label = m.group(1)
        annex = m.group(2).lower()
        fp_prefix = f"{annex} - appendix {appendix_label.lower()}"
        return {"type": "appendix_to_annex", "fp_prefix": fp_prefix}

    return None


def link_entities_to_paragraphs(data: list[dict]) -> list[dict]:
    """Resolve entity strings to paragraphIds.

    Lookup tables built once, then used per entity:

    norm_to_id
        Normalised hierarchy label → paragraphId (general fallback).

    intro_para_to_id
        "Paragraph X" entities only → paragraphId whose full_path starts with
        "Introduction >" (prevents matching same-labelled Annex sections).

    annex_sub_to_id
        (annex_prefix, normalised_leaf_hierarchy) → paragraphId.
        Resolves "Annex 3 paragraph 4.1.1" and "Annex 3 Paragraph 4".

    full_path_to_id
        full_path.lower() → paragraphId.
        Resolves "Appendix N to Annex X" via the exact Appendix heading entry.
    """
    # --- build lookups ---
    norm_to_id: dict[str, str] = {}
    intro_para_to_id: dict[str, str] = {}
    annex_sub_to_id: dict[tuple[str, str], str] = {}
    full_path_to_id: dict[str, str] = {}

    for entry in data:
        pid = entry["paragraphId"]
        hierarchy = entry.get("hierarchy", "")
        fp = entry.get("full_path", "").strip()
        fp_lower = fp.lower()

        # General hierarchy lookup
        if hierarchy:
            norm_to_id[_normalize(hierarchy)] = pid

        # Full-path lookup (used for Appendix references)
        if fp_lower:
            full_path_to_id[fp_lower] = pid

        # Intro lookup: ALL hierarchy entries whose full_path is under Introduction.
        # Keyed by normalised hierarchy so both "Paragraph 1" → "paragraph 1"
        # and "2.4" (multi-level) → "2.4" resolve correctly.
        if fp_lower.startswith("introduction >") and hierarchy:
            intro_para_to_id[_normalize(hierarchy)] = pid

        # Annex sub-reference lookup: key = (annex_root, normalised_hierarchy)
        if fp_lower.startswith("annex ") and hierarchy:
            annex_root = fp_lower.split(">")[0].strip()   # e.g. "annex 3"
            norm_hier = _normalize(hierarchy)
            if norm_hier:
                annex_sub_to_id[(annex_root, norm_hier)] = pid

    # --- resolve entities ---
    for entry in data:
        seen: set[str] = set(entry.get("targetIDs", []))

        for entity in entry.get("entities", []):
            matched_id: str | None = None

            compound = _parse_compound_entity(entity)
            if compound:
                if compound["type"] == "annex_sub":
                    matched_id = annex_sub_to_id.get(
                        (compound["annex"], compound["sub_key"])
                    )
                elif compound["type"] == "appendix_to_annex":
                    # Match the Appendix heading itself or any entry whose
                    # full_path starts with the appendix prefix.
                    prefix = compound["fp_prefix"]
                    matched_id = full_path_to_id.get(prefix)
                    if not matched_id:
                        # Fallback: scan for any entry whose full_path starts with prefix
                        for fp_key, pid in full_path_to_id.items():
                            if fp_key.startswith(prefix):
                                matched_id = pid
                                break

            elif _is_intro_paragraph_entity(entity):
                norm_entity = _normalize(entity)
                # Prefer Introduction-scoped match; fall back to general lookup
                # for references that happen to use "Paragraph X" form but live
                # in an Annex (e.g. "Paragraph 8.38.1.5" in regulatory text).
                matched_id = intro_para_to_id.get(norm_entity) or norm_to_id.get(norm_entity)

            else:
                matched_id = norm_to_id.get(_normalize(entity))

            if matched_id and matched_id != entry["paragraphId"] and matched_id not in seen:
                entry["targetIDs"].append(matched_id)
                seen.add(matched_id)

    return data


def unlink(data: list[dict]) -> list[dict]:
    """Clear all targetIDs, resetting every entry to an empty list."""
    for entry in data:
        entry["targetIDs"] = []
    return data


if __name__ == "__main__":
    with open("output.json", "r", encoding="utf-8") as fh:
        data = json.load(fh)
    updated_data = link_entities_to_paragraphs(data)
    with open("output.json", "w", encoding="utf-8") as fh:
        json.dump(updated_data, fh, indent=2, ensure_ascii=False)
    # unlinked_data = unlink(data)
    # with open("output.json", "w", encoding="utf-8") as fh:
    #     json.dump(unlinked_data, fh, indent=2, ensure_ascii=False)