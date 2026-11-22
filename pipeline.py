"""Compare two inventories and build static redirect rules only for approved pairs."""

import csv
import io
import re
from collections import defaultdict
from difflib import SequenceMatcher

TITLE = "Doc Link Migration"
DESCRIPTION = "Map retired documentation paths to reviewed replacements and export static-host redirect rules and an unresolved-route queue."
PROMPT = "Explain alias conflicts and closest title or path suggestions. Treat fuzzy similarity as a review aid, never as proof the target documents the same feature."


def text(value, field):
    if not isinstance(value, str) or not value.strip() or len(value) > 4000:
        raise ValueError(f"{field} must be nonempty text up to 4,000 characters.")
    return value.strip()


def objects(value, field, cap=500):
    if (
        not isinstance(value, list)
        or len(value) > cap
        or any(not isinstance(row, dict) for row in value)
    ):
        raise ValueError(f"{field} must be an array of at most {cap} objects.")
    return value


def spreadsheet_text(value):
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def csv_file(columns, rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows(rows)
    return output.getvalue()


def selected(evidence, approved):
    available = {item["id"]: item for item in evidence["candidates"]}
    seen = set()
    result = []
    for item in approved:
        key = item["id"]
        if key not in available or key in seen:
            raise ValueError("Approval contains an unknown or duplicate decision.")
        seen.add(key)
        result.append(available[key])
    return result


def route(value):
    if (
        not isinstance(value, str)
        or len(value) > 300
        or not value.startswith("/")
        or "//" in value
    ):
        raise ValueError(
            "Use literal site-root paths with ASCII slugs and no query or dot segments."
        )
    path = value.rstrip("/") or "/"
    if path != "/" and any(
        s in (".", "..") or not re.fullmatch(r"[A-Za-z0-9._~-]+", s)
        for s in path[1:].split("/")
    ):
        raise ValueError(
            "Use literal site-root paths with ASCII slugs and no query or dot segments."
        )
    return path


def inventory(rows, stage):
    result = {}
    for item in objects(rows, stage, 750):
        path = route(item.get("path"))
        if path in result:
            raise ValueError(f"Duplicate canonical route: {path}")
        labels = item.get("aliases", [])
        if not isinstance(labels, list) or len(labels) > 100:
            raise ValueError("Supply a list of at most 100 route aliases.")
        aliases = sorted(set(route(x) for x in labels))
        result[path] = {
            "id": stage + ":" + path,
            "stage": stage,
            "path": path,
            "title": text(item.get("title"), "title"),
            "aliases": aliases,
        }
    return result


def signature(row):
    return " ".join(re.findall(r"\w+", row["title"].casefold(), re.UNICODE))[:160]


def prepare(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Provide old_routes and new_routes arrays.")
    old = inventory(data.get("old_routes"), "old")
    new = inventory(data.get("new_routes"), "new")
    if len(old) * len(new) > 40000:
        raise ValueError(
            "Use a smaller documentation section (up to 40,000 pair comparisons)."
        )
    by_alias = defaultdict(list)
    for path, item in new.items():
        for alias in item["aliases"]:
            by_alias[alias].append(path)
    candidates = []
    unchanged = len(set(old) & set(new))
    unresolved = 0
    signatures = {path: signature(item) for path, item in new.items()}
    for path, item in sorted(old.items()):
        if path in new:
            continue
        matches = sorted(by_alias[path])
        if matches:
            scored = [(1.0, p) for p in matches]
            reason = "Competing aliases" if len(matches) > 1 else "Declared alias"
        else:
            reason = "Suggested by title and path"
            scored = []
            title = signature(item)
            for dest, other in new.items():
                similarity = SequenceMatcher(None, title, signatures[dest]).ratio()
                slug_score = SequenceMatcher(None, path[-120:], dest[-120:]).ratio()
                score = 0.75 * similarity + 0.25 * slug_score
                if score >= 0.55:
                    scored.append((score, dest))
            scored = sorted(scored, key=lambda x: (-x[0], x[1]))[:3]
        if not scored:
            unresolved += 1
        for score, dest in scored:
            candidates.append(
                {
                    "id": f"redirect:{len(path)}:{path}:{dest}",
                    "action": "Approve permanent redirect",
                    "evidence_ids": [item["id"], new[dest]["id"]],
                    "from": path,
                    "to": dest,
                    "basis": reason,
                    "similarity": round(score, 3),
                    "alternatives": len(scored),
                }
            )
    records = [m[k] for m in (old, new) for k in sorted(m)]
    return {
        "summary": f"{len(old) - unchanged} retired legacy routes; {unresolved} without a suggested replacement.",
        "metrics": {
            "Legacy routes": len(old),
            "Unchanged": unchanged,
            "Candidate mappings": len(candidates),
            "Without suggestions": unresolved,
        },
        "records": records,
        "candidates": candidates,
    }


def export(data, evidence, approved):
    mapping = {}
    for c in selected(evidence, approved):
        if c["from"] in mapping:
            raise ValueError("Choose only one destination for each legacy route.")
        mapping[c["from"]] = c["to"]
    active = {r["path"] for r in evidence["records"] if r["stage"] == "new"}
    unresolved = [
        [r["path"], spreadsheet_text(r["title"])]
        for r in evidence["records"]
        if r["stage"] == "old" and r["path"] not in active | mapping.keys()
    ]
    return {
        "_redirects": "".join(f"{a} {b} 301\n" for a, b in sorted(mapping.items())),
        "unresolved-routes.csv": csv_file(["legacy_path", "title"], unresolved),
    }
