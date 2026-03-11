"""
Copy targetIDs from output.json into data/test_data.json, matched by paragraphId == id.

output.json      : list of { paragraphId, targetIDs, ... }
test_data.json   : { paragraphLinks: [ { id, targetIds, ... }, ... ], ... }

The script writes the updated document to data/test_data_updated.json so the
original is never overwritten.  Pass --in-place to overwrite the original.
"""

import argparse
import json
from pathlib import Path


def load_json(path: Path) -> dict | list:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: Path, data: dict | list) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    print(f"Saved → {path}")


def build_target_id_map(output: list[dict]) -> dict[str, list]:
    """Return {paragraphId: targetIDs} for every entry in output.json."""
    return {entry["paragraphId"]: entry.get("targetIDs", []) for entry in output}


def copy_target_ids(
    output_path: Path,
    test_data_path: Path,
    *,
    in_place: bool = False,
) -> None:
    output: list[dict] = load_json(output_path)
    test_data: dict = load_json(test_data_path)

    id_map = build_target_id_map(output)

    links: list[dict] = test_data.get("paragraphLinks", [])
    matched = 0
    unmatched_ids: list[str] = []

    for link in links:
        para_id = link.get("id", "")
        if para_id in id_map:
            link["targetIds"] = id_map[para_id]
            if id_map[para_id]:
                matched += 1
        else:
            unmatched_ids.append(para_id)

    print(f"paragraphLinks processed : {len(links)}")
    print(f"Links with non-empty IDs copied : {matched}")
    if unmatched_ids:
        print(f"Paragraph IDs in test_data with no match in output.json ({len(unmatched_ids)}):")
        for uid in unmatched_ids:
            print(f"  {uid}")

    dest = test_data_path if in_place else test_data_path.with_name("test_data_updated.json")
    save_json(dest, test_data)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="output.json",
        help="Path to output.json (default: output.json)",
    )
    parser.add_argument(
        "--test-data",
        default="data/test_data.json",
        help="Path to test_data.json (default: data/test_data.json)",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite test_data.json instead of writing test_data_updated.json",
    )
    args = parser.parse_args()

    copy_target_ids(
        Path(args.output),
        Path(args.test_data),
        in_place=args.in_place,
    )


if __name__ == "__main__":
    main()
