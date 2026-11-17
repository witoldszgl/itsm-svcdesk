# ai-generated: 95% - Claude Code (Opus 5.5) wrote the rules of CI-SPEC.md section 3 into this file; checked against lab5-practice/expected.json
"""bakeoff.py - scanner SARIF + a labels file -> a per-tool confusion matrix (CI-SPEC.md P-14..P-23).

    python3 bakeoff.py --labels labels.json a.sarif b.sarif > bakeoff.json

Standard library only; runs as `python3 -S -E bakeoff.py`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from urllib.parse import unquote

# P-19: the course's classes and their CWE numbers.
CLASS_CWES: dict[str, tuple[int, ...]] = {
    "secret": (259, 260, 321, 798),
    "injection": (74, 77, 78, 79, 80, 88, 89, 90, 91, 94, 95, 96, 611, 776, 917, 943, 1336),
    "deserialization": (502,),
    "weak-crypto": (261, 326, 327, 328, 330, 331, 338, 759, 760, 916),
    "insecure-transport": (295, 297, 319, 322, 757),
    "path-traversal": (22, 23, 35, 36, 73),
    "ssrf": (918,),
    "vulnerable-dependency": (937, 1035, 1104, 1395),
    "misconfiguration": (16, 215, 250, 489, 668, 732, 1188),
    "access-control": (284, 285, 639, 862, 863),
}
CWE_TO_CLASSES: dict[int, set[str]] = {}
for _cls, _cwes in CLASS_CWES.items():
    for _n in _cwes:
        CWE_TO_CLASSES.setdefault(_n, set()).add(_cls)

SEMGREP_NAMES = {"semgrep", "semgrep oss", "semgrep ce", "semgrep community edition", "semgrep pro"}
FIXED_NAMES = {"trivy", "grype", "osv-scanner", "gitleaks"}
TRIVY_TAG_CLASSES = {"vulnerability": "vulnerable-dependency", "secret": "secret", "misconfiguration": "misconfiguration"}

CWE_RE = re.compile(r"(?<![A-Za-z0-9])[Cc][Ww][Ee]-([0-9]+)")
TOKEN_RE = re.compile(r"[A-Za-z0-9._-]+")
PEP503_RE = re.compile(r"[-_.]+")
NO_RULE = object()  # a result without a ruleId string: differs from every string (P-21)


def _obj(value) -> dict:
    """A JSON object, or an empty one for anything else (null counts as absent)."""
    return value if isinstance(value, dict) else {}


def _arr(value) -> list:
    """An array member that is not an array has no entries (P-16)."""
    return value if isinstance(value, list) else []


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


# ---------------------------------------------------------------- P-15 tools
def tool_id(run: dict) -> str:
    tool = run.get("tool")
    driver = tool.get("driver") if isinstance(tool, dict) else None
    name = driver.get("name") if isinstance(driver, dict) else None
    if not isinstance(name, str):
        return "unknown"
    name = name.strip()
    low = name.lower()
    if low in FIXED_NAMES:
        return low
    if low in SEMGREP_NAMES:
        return "semgrep"
    slug = re.sub(r"[^a-z0-9]+", "-", low).strip("-")
    return slug or "unknown"


# ---------------------------------------------------------------- P-17 paths
def result_file(uri: str, root: str) -> str | None:
    path = unquote(uri)
    if path[:7].lower() == "file://":
        path = path[7:]
    if path.startswith("./"):
        path = path[2:]
    parts = path.split("/")
    last = None
    for i, part in enumerate(parts):
        if part == root:
            last = i
    if last is None:
        return None
    return "/".join(parts[last:])


# ---------------------------------------------------------------- P-18 lines
def result_lines(physical: dict) -> tuple[int, int] | None:
    region = _obj(physical.get("region"))
    start = region.get("startLine")
    if not _is_int(start) or start < 1:
        return None
    end = region.get("endLine")
    if not _is_int(end) or end < start:
        end = start
    return start, end


# ---------------------------------------------------------------- P-19 classes
def _string_tags(holder: dict) -> list[str]:
    return [t for t in _arr(_obj(holder.get("properties")).get("tags")) if isinstance(t, str)]


def result_classes(result: dict, rule: dict | None, tool: str) -> set[str]:
    cls = _obj(result.get("properties")).get("class")
    if isinstance(cls, str) and cls in CLASS_CWES:
        return {cls}
    rule_tags = _string_tags(rule) if rule is not None else []
    if tool == "gitleaks":
        return {"secret"}
    if tool in ("grype", "osv-scanner"):
        return {"vulnerable-dependency"}
    if tool == "trivy":
        found = {TRIVY_TAG_CLASSES[t.lower()] for t in rule_tags if t.lower() in TRIVY_TAG_CLASSES}
        if found:
            return found
    found: set[str] = set()
    for tag in _string_tags(result) + rule_tags:
        for m in CWE_RE.finditer(tag):
            found |= CWE_TO_CLASSES.get(int(m.group(1)), set())
    return found or {"other"}


# ---------------------------------------------------------------- P-20 matching
def _pep503(name: str) -> str:
    return PEP503_RE.sub("-", name.lower())


def message_tokens(result: dict) -> set[str]:
    text = _obj(result.get("message")).get("text")
    if not isinstance(text, str):
        return set()
    tokens = set()
    for tok in TOKEN_RE.findall(text):
        tok = tok.strip("._-")
        if tok:
            tokens.add(_pep503(tok))
    return tokens


def matches(finding: dict, defect: dict) -> bool:
    if finding["file"] != defect.get("file") or defect.get("class") not in finding["classes"]:
        return False
    if defect["class"] == "vulnerable-dependency":
        package = defect.get("package")
        return isinstance(package, str) and _pep503(package) in finding["tokens"]
    lines = finding["lines"]
    if lines is None:
        return False
    return lines[0] <= defect["end_line"] and defect["start_line"] <= lines[1]


# ---------------------------------------------------------------- P-16 results
def collect(sarif_documents: list, root: str) -> dict[str, list[dict]]:
    """Per tool id: the in-set findings (P-15..P-19). Every tool with a run is a key."""
    tools: dict[str, list[dict]] = {}
    for doc in sarif_documents:
        for run in _arr(_obj(doc).get("runs")):
            if not isinstance(run, dict):
                continue
            tid = tool_id(run)
            findings = tools.setdefault(tid, [])
            driver = _obj(_obj(run.get("tool")).get("driver"))
            rules = [r for r in _arr(driver.get("rules")) if isinstance(r, dict)]
            for result in _arr(run.get("results")):
                if not isinstance(result, dict):
                    continue
                kind = result.get("kind")
                if kind is not None and kind != "fail":
                    continue
                if result.get("suppressions"):
                    continue
                locations = _arr(result.get("locations"))
                if not locations:
                    continue
                physical = _obj(_obj(locations[0]).get("physicalLocation"))
                uri = _obj(physical.get("artifactLocation")).get("uri")
                if not isinstance(uri, str) or uri == "":
                    continue
                file = result_file(uri, root)
                if file is None:
                    continue
                rule_id = result.get("ruleId")
                rule = None
                if rule_id is not None:
                    rule = next((r for r in rules if r.get("id") == rule_id), None)
                findings.append({
                    "rule_id": rule_id if isinstance(rule_id, str) else NO_RULE,
                    "file": file,
                    "lines": result_lines(physical),
                    "classes": result_classes(result, rule, tid),
                    "tokens": message_tokens(result),
                })
    return tools


# ---------------------------------------------------------------- P-21, P-22
def _ratio(num: int, den: int):
    return None if den == 0 else round(num / den, 4)


def confusion_matrix(labels: dict, sarif_documents: list) -> dict:
    root = labels["set"]
    defects = [d for d in _arr(labels.get("defects")) if isinstance(d, dict)]
    out: dict[str, dict] = {}
    for tid, findings in sorted(collect(sarif_documents, root).items()):
        found: set[int] = set()
        fp_keys = set()
        for f in findings:
            hit = False
            for i, d in enumerate(defects):
                if matches(f, d):
                    found.add(i)
                    hit = True
            if not hit:
                start, end = f["lines"] if f["lines"] is not None else (None, None)
                key_rule = ("", f["rule_id"]) if isinstance(f["rule_id"], str) else ("none", None)
                fp_keys.add((key_rule, f["file"], start, end))
        tp, fp = len(found), len(fp_keys)
        fn = len(defects) - tp
        out[tid] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": _ratio(tp, tp + fp),
            "recall": _ratio(tp, tp + fn),
            "f1": _ratio(2 * tp, 2 * tp + fp + fn),
        }
    return {"set": root, "defects": len(defects), "tools": out}


def _load(path: str):
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="per-tool confusion matrix of SARIF against labels (CI-SPEC.md P-23)")
    parser.add_argument("--labels", required=True, help="the labels file (P-14)")
    parser.add_argument("sarif", nargs="+", help="SARIF 2.1.0 files")
    args = parser.parse_args(argv)
    with open(args.labels, "r", encoding="utf-8-sig") as fh:
        labels = json.load(fh)
    documents = [_load(p) for p in args.sarif]
    json.dump(confusion_matrix(labels, documents), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
