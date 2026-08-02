"""
Turns a GitHub issue (opened by the static site) into a change to
config/watches.json. Supports three actions, one per issue label:

  watch-request  (add)    - cinema, hall_type, movie, hour_from, hour_to, [email]
  watch-edit     (edit)   - id, hour_from, hour_to, email (email empty = clear it)
  watch-delete   (delete) - id

Run by .github/workflows/process-watch-request.yml.

Usage:
    python parse_issue.py --action add --issue-number 12 --body-file body.txt
    python parse_issue.py --action edit --issue-number 13 --body-file body.txt
    python parse_issue.py --action delete --issue-number 14 --body-file body.txt
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WATCHES_FILE = REPO_ROOT / "config" / "watches.json"


def parse_body(body: str) -> dict:
    """Parses 'key: value' lines into a dict. Keys are lower-cased; a key
    with nothing after the colon is kept as an empty string (distinct from
    the key being absent entirely), which matters for clearing fields."""
    fields = {}
    for line in body.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip().lower()] = value.strip()
    return fields


def load_watches() -> list:
    if WATCHES_FILE.exists():
        return json.loads(WATCHES_FILE.read_text(encoding="utf-8"))
    return []


def save_watches(watches: list) -> None:
    WATCHES_FILE.parent.mkdir(parents=True, exist_ok=True)
    WATCHES_FILE.write_text(json.dumps(watches, ensure_ascii=False, indent=2), encoding="utf-8")


def do_add(fields: dict, issue_number: str) -> int:
    required = ["cinema", "hall_type", "movie"]
    missing = [k for k in required if not fields.get(k)]
    if missing:
        print(f"ERROR: missing required field(s): {', '.join(missing)}", file=sys.stderr)
        return 1

    watches = load_watches()
    new_entry = {
        "id": f"issue-{issue_number}",
        "cinema": fields["cinema"],
        "hall_type": fields["hall_type"],
        "movie": fields["movie"],
        "hour_from": (fields.get("hour_from") or "00").zfill(2),
        "hour_to": (fields.get("hour_to") or "23").zfill(2),
    }
    if fields.get("email"):
        new_entry["email"] = fields["email"]

    dedup_key = (new_entry["cinema"], new_entry["hall_type"], new_entry["movie"])
    if dedup_key in {(w["cinema"], w["hall_type"], w["movie"]) for w in watches}:
        print("This exact watch already exists - skipping duplicate.")
        return 0

    watches.append(new_entry)
    save_watches(watches)
    print(f"Added watch: {new_entry}")
    return 0


def do_edit(fields: dict) -> int:
    watch_id = fields.get("id")
    if not watch_id:
        print("ERROR: edit requires 'id'", file=sys.stderr)
        return 1

    watches = load_watches()
    target = next((w for w in watches if w.get("id") == watch_id), None)
    if target is None:
        print(f"ERROR: no watch found with id '{watch_id}'", file=sys.stderr)
        return 1

    if "hour_from" in fields:
        target["hour_from"] = (fields["hour_from"] or "00").zfill(2)
    if "hour_to" in fields:
        target["hour_to"] = (fields["hour_to"] or "23").zfill(2)
    if "email" in fields:
        if fields["email"]:
            target["email"] = fields["email"]
        else:
            target.pop("email", None)

    save_watches(watches)
    print(f"Updated watch: {target}")
    return 0


def do_delete(fields: dict) -> int:
    watch_id = fields.get("id")
    if not watch_id:
        print("ERROR: delete requires 'id'", file=sys.stderr)
        return 1

    watches = load_watches()
    remaining = [w for w in watches if w.get("id") != watch_id]
    if len(remaining) == len(watches):
        print(f"WARNING: no watch found with id '{watch_id}' (nothing removed)")
        return 0

    save_watches(remaining)
    print(f"Deleted watch id={watch_id}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", required=True, choices=["add", "edit", "delete"])
    parser.add_argument("--issue-number", required=True)
    parser.add_argument("--body-file", required=True)
    args = parser.parse_args()

    body = Path(args.body_file).read_text(encoding="utf-8")
    fields = parse_body(body)

    if args.action == "add":
        return do_add(fields, args.issue_number)
    elif args.action == "edit":
        return do_edit(fields)
    else:
        return do_delete(fields)


if __name__ == "__main__":
    raise SystemExit(main())
