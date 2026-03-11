"""Hierarchical reference lookup in regulatory documents.

Algorithm:
  0. Pre-pass: walk paragraphLinks with fast regex heuristics to assign each
     paragraph a depth and ancestor chain (no LLM needed).
  1. For each paragraph, call an LLM with the paragraph text AND its ancestor
     chain so entities are extracted with document-level context.
  2. Generate embeddings:
       - One "hierarchy_embedding" per paragraph — embeds the FULL ancestor
         path ("Annex 1 > Paragraph 2 > 2.1") so identically-numbered sections
         in different Annexes get distinct embeddings.
       - One embedding per extracted NER entity (contextualised entity string).
  3. Build a vector store keyed by paragraph ID using hierarchy embeddings only.
  4. For each NER embedding, find the closest hierarchy embedding (cosine
     similarity) and record the matching paragraph ID as a targetID.
  5. Write the augmented results to an output JSON file.
"""

import argparse
import json
import re
import sys
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

from llm_factory import LLMFactory

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
SIMILARITY_THRESHOLD = 0.50

# Headings that are only depth-0 when the ENTIRE paragraph text is that word.
# This prevents "Preamble The environmental benefits..." (a sub-section inside
# Annex 2) from being mistaken for a top-level document reset.
_STANDALONE_HEADINGS = {"preamble", "introduction", "foreword"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def extract_hierarchy(text: str) -> tuple[str, str]:
    """Split a paragraph into its leading numeric section ID and body text.

    Example:
        "8.38.1.5. The rotational speed..." → ("8.38.1.5", "The rotational speed...")
    """
    match = re.match(r"^\s*(\d+(?:\.\d+)*\.?)\s+", text)
    if match:
        hierarchy = match.group(1).rstrip(".")
        body = text[match.end():].strip()
        return hierarchy, body
    return "", text.strip()


def _extract_label_and_depth(text: str) -> tuple[str, int]:
    """Return (label, depth) using precise text patterns — no keyword assumptions.

    depth = -1  → no recognisable heading (body paragraph / unknown)
    depth =  0  → top-level section heading (Annex, Appendix, standalone word)
    depth >= 1  → numeric section; depth = number of dot-separated parts

    Key rules that distinguish this from a naive keyword check:
    • "Annex X – Appendix Y …" → depth 0, label "Annex X – Appendix Y"
    • "Annex X …"              → depth 0, label "Annex X"
    • "Preamble"  (exact)      → depth 0  (the whole text IS the heading word)
    • "Preamble The environmental benefits…" → depth -1  (heading word + body text
      on the same line means it is a child section, NOT a document-level reset)
    """
    t = text.strip()

    # "Annex X - Appendix Y …" (must be checked before plain "Annex X")
    m = re.match(r"^(Annex \d+\s*[-–]\s*Appendix \w+)", t, re.IGNORECASE)
    if m:
        return m.group(1).strip(), 0

    # "Annex X …"
    m = re.match(r"^(Annex \d+)\b", t, re.IGNORECASE)
    if m:
        return m.group(1).strip(), 0

    # Standalone heading: the ENTIRE text must be just the heading word.
    if t.lower() in _STANDALONE_HEADINGS:
        return t, 0

    # Numeric section: "8.38.1.5 …" or "1. Title"
    m = re.match(r"^(\d+(?:\.\d+)*\.?)\s", t)
    if m:
        label = m.group(1).rstrip(".")
        return label, len(label.split("."))

    return "", -1


def build_document_hierarchy(
    paragraph_links: list[dict],
    complete_text_path: str | None = None,
) -> list[dict]:
    """Pre-pass: annotate every paragraph with depth, parent_id, and ancestor_labels.

    If ``complete_text_path`` is provided the function reads that file (one
    paragraph per line, in the same order as ``paragraph_links``) and uses the
    actual line text for heading detection.  This avoids the keyword-list
    heuristic that confuses lines like "Preamble The environmental benefits…"
    (a child section inside Annex 2) with a top-level document reset.

    Added fields per paragraph:
        _depth           int          structural depth (-1 if unknown)
        _parent_id       str | None   paragraphId of the immediate parent
        _ancestor_labels list[str]    ordered list of ancestor hierarchy labels
        _quick_label     str          label extracted from the heading (may be empty)
    """
    if complete_text_path:
        with open(complete_text_path, encoding="utf-8") as fh:
            ref_lines: list[str] = [ln.rstrip("\n") for ln in fh]
    else:
        ref_lines = [p["text"] for p in paragraph_links]

    depth_tracker: dict[int, tuple[str, str]] = {}

    for para, ref_text in zip(paragraph_links, ref_lines):
        # Use the reference text (from file or para itself) for precise detection.
        label, depth = _extract_label_and_depth(ref_text)

        if depth == 0:
            depth_tracker = {0: (para["id"], label)}
            parent_id = None
            ancestor_labels: list[str] = []

        elif depth >= 1:
            parent_entry = depth_tracker.get(depth - 1)
            parent_id = parent_entry[0] if parent_entry else None
            ancestor_labels = [
                depth_tracker[d][1]
                for d in sorted(depth_tracker)
                if d < depth and depth_tracker[d][1]
            ]
            depth_tracker[depth] = (para["id"], label)
            for d in [d for d in list(depth_tracker) if d > depth]:
                del depth_tracker[d]

        else:
            # Body-only paragraph: inherit current ancestors, don't update tracker.
            parent_id = (
                depth_tracker.get(max(depth_tracker, default=-1), (None, None))[0]
            )
            ancestor_labels = [
                depth_tracker[d][1]
                for d in sorted(depth_tracker)
                if depth_tracker[d][1]
            ]

        para["_depth"] = depth
        para["_parent_id"] = parent_id
        para["_ancestor_labels"] = ancestor_labels
        para["_quick_label"] = label

    return paragraph_links


def build_full_path(ancestor_labels: list[str], current_hierarchy: str) -> str:
    """Combine ancestor labels and the current hierarchy into a path string.

    Example:
        ["Annex 1", "1"] + "1.1"  →  "Annex 1 > 1 > 1.1"
    """
    parts = [l for l in ancestor_labels if l]
    if current_hierarchy:
        parts.append(current_hierarchy)
    return " > ".join(parts) if parts else current_hierarchy


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def find_closest_paragraph(
    query: np.ndarray,
    vector_store: list[dict],
    exclude_id: str,
    threshold: float = SIMILARITY_THRESHOLD,
) -> str | None:
    """Return the paragraphId whose full-path embedding is closest to ``query``.

    Skips the source paragraph itself and returns ``None`` if no match exceeds
    ``threshold``.
    """
    best_score = threshold
    best_id: str | None = None
    for entry in vector_store:
        if entry["paragraphId"] == exclude_id:
            continue
        score = cosine_similarity(query, entry["embedding"])
        if score > best_score:
            best_score = score
            best_id = entry["paragraphId"]
    return best_id


# ---------------------------------------------------------------------------
# Core algorithm steps
# ---------------------------------------------------------------------------


def build_paragraph_records(
    paragraph_links: list[dict],
    llm: Any,
    embed_model: SentenceTransformer,
) -> list[dict]:
    """Steps 1–2: Extract entities via LLM and generate embeddings.

    Returns a list of dicts:
        {
            "paragraphId":        str,
            "hierarchy":          str,   # LLM-returned section label
            "full_path":          str,   # full ancestor path used for embedding
            "hierarchy_embedding": np.ndarray,
            "NER": [{"entity": str, "embedding": np.ndarray}, ...],
        }
    """
    records: list[dict] = []

    for para in paragraph_links:
        para_id: str = para["id"]
        text: str = para["text"]
        ancestor_labels: list[str] = para.get("_ancestor_labels", [])
        parent_chain: str = " > ".join(ancestor_labels)

        # LLM: extract hierarchy label + cross-reference entities (context-aware).
        extraction = llm.extract_entities(text, parent_chain=parent_chain)
        entities: list[str] = extraction.get("entities", [])

        # Prefer LLM-identified hierarchy; fall back to quick regex label.
        hierarchy: str = extraction.get("hierarchy", "").strip()
        if not hierarchy:
            hierarchy = para.get("_quick_label", "")

        _, body = extract_hierarchy(text)

        # Hierarchy embedding uses the FULL ancestor path so that identically-
        # numbered sections in different Annexes get distinct vector positions.
        full_path = build_full_path(ancestor_labels, hierarchy)
        hier_text = full_path if full_path else text[:128]
        hier_emb: np.ndarray = embed_model.encode(hier_text, convert_to_numpy=True)

        # NER embeddings: entity string includes its parent-qualified label,
        # so it naturally aligns with the corresponding full-path embedding.
        ner_records: list[dict] = []
        for entity in entities:
            context = f"{entity} — {body[:200]}"
            emb: np.ndarray = embed_model.encode(context, convert_to_numpy=True)
            ner_records.append({"entity": entity, "embedding": emb})

        records.append(
            {
                "paragraphId": para_id,
                "hierarchy": hierarchy,
                "full_path": full_path,
                "hierarchy_embedding": hier_emb,
                "NER": ner_records,
            }
        )
        print(
            f"  [{para_id[:12]}]  path={full_path!r}  "
            f"entities={[n['entity'] for n in ner_records]}"
        )

    return records


def resolve_references(
    records: list[dict], threshold: float = SIMILARITY_THRESHOLD
) -> list[dict]:
    """Steps 3–4: Build full-path vector store, resolve each NER to a targetID.

    Returns the augmented list:
        {
            "paragraphId": str,
            "hierarchy":   str,
            "full_path":   str,
            "entities":    [str, ...],
            "targetIDs":   [str, ...],
        }
    """
    # Vector store: full-path hierarchy embeddings only.
    vector_store: list[dict] = [
        {
            "paragraphId": r["paragraphId"],
            "full_path": r["full_path"],
            "embedding": r["hierarchy_embedding"],
        }
        for r in records
    ]

    results: list[dict] = []
    for record in records:
        target_ids: list[str] = []
        for ner in record["NER"]:
            matched_id = find_closest_paragraph(
                ner["embedding"],
                vector_store,
                exclude_id=record["paragraphId"],
                threshold=threshold,
            )
            if matched_id and matched_id not in target_ids:
                target_ids.append(matched_id)

        results.append(
            {
                "paragraphId": record["paragraphId"],
                "hierarchy": record["hierarchy"],
                "full_path": record["full_path"],
                "entities": [n["entity"] for n in record["NER"]],
                "targetIDs": target_ids,
            }
        )

    return results


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run(
    input_path: str,
    provider: str,
    output_path: str,
    threshold: float = SIMILARITY_THRESHOLD,
    complete_text_path: str | None = None,
    **llm_kwargs: Any,
) -> None:
    print(f"Loading '{input_path}' ...")
    with open(input_path, encoding="utf-8") as fh:
        data = json.load(fh)

    paragraph_links: list[dict] = data.get("paragraphLinks", [])
    if not paragraph_links:
        print("ERROR: No 'paragraphLinks' found in the input file.", file=sys.stderr)
        sys.exit(1)

    print(f"LLM provider   : {provider}")
    print(f"Embedding model: {EMBEDDING_MODEL}")
    print(f"Paragraphs     : {len(paragraph_links)}")
    if complete_text_path:
        print(f"Document text  : {complete_text_path}")
    print()

    print("=== Phase 0: building document hierarchy (pre-pass) ===")
    paragraph_links = build_document_hierarchy(
        paragraph_links, complete_text_path=complete_text_path
    )

    llm = LLMFactory.create(provider, **llm_kwargs)
    embed_model = SentenceTransformer(EMBEDDING_MODEL)

    print("\n=== Phase 1: extracting entities & building embeddings ===")
    records = build_paragraph_records(paragraph_links, llm, embed_model)

    print("\n=== Phase 2: resolving references via vector store ===")
    results = resolve_references(records, threshold=threshold)

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)

    print(f"\nDone. Results written to '{output_path}'")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hierarchical reference lookup in regulatory documents using LLMs."
    )
    parser.add_argument("input", help="Path to input JSON file")
    parser.add_argument(
        "--provider",
        default="openai",
        choices=["openai", "anthropic", "gemini"],
        help="LLM provider to use (default: openai)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override the default model name for the chosen provider",
    )
    parser.add_argument(
        "--output",
        default="output.json",
        help="Path for the output JSON file (default: output.json)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=SIMILARITY_THRESHOLD,
        help=f"Cosine similarity threshold for reference matching "
             f"(default: {SIMILARITY_THRESHOLD})",
    )
    parser.add_argument(
        "--complete-text",
        default=None,
        metavar="FILE",
        help="Path to the complete_text_data.txt file (one paragraph per line, "
             "same order as the input JSON). When provided, heading detection "
             "uses the actual document text instead of keyword heuristics.",
    )
    args = parser.parse_args()

    llm_kwargs: dict[str, Any] = {}
    if args.model:
        llm_kwargs["model"] = args.model

    run(
        args.input,
        args.provider,
        args.output,
        threshold=args.threshold,
        complete_text_path=args.complete_text,
        **llm_kwargs,
    )


if __name__ == "__main__":
    main()
