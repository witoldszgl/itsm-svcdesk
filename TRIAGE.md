---
lab5_triage:
  image: ghcr.io/witoldszgl/itsm-svcdesk@sha256:2a6b2fd7260e1922e855a4bfbd0cb60183e1fdd736572356e478a04b46d06698
  sarif_receipt: 443
---
<!-- ai-generated: 85% - Claude Code (Opus 5.5) drafted the rows and the bake-off from the pipeline logs, the receipted SARIF and bakeoff.json; I reviewed the decisions -->
# Triage

What the gates and the reporting scanners found on my service, and what I did about each (CI-SPEC.md P-11, P-12).
One row per rule of one tool. The image is the one pushed and attested by the green `main` run 44117166218 (commit
b3fc342); `gh attestation verify` passes for it, provenance and SBOM. `.trivyignore` and `.gitleaksignore` are
empty: nothing needed an ignore.

| Tool | Rule | Decision | Reason |
|---|---|---|---|
| trivy | CVE-2025-62727 | fix | starlette 0.46.2 (Range header DoS, HIGH) in src/requirements.txt; pinned starlette 1.10.0 and fastapi 0.163.1 (the first FastAPI line that accepts starlette 1.x); 46 own tests still pass |
| trivy | CVE-2026-48818 | fix | starlette 0.46.2 StaticFiles UNC-path SSRF (HIGH), fixed in 1.1.0; gone with the same bump of src/requirements.txt to starlette 1.10.0 |
| trivy | CVE-2026-54283 | fix | starlette 0.46.2 form limits ignored for urlencoded bodies (HIGH), fixed in 1.3.1; gone with the bump to starlette 1.10.0 in src/requirements.txt |
| trivy | CVE-2025-71176 | fix | pytest 8.3.5 in tests/requirements.txt line 1 (MEDIUM, tmpdir handling); pinned pytest 9.0.3, the fixed version; the test image rebuilt and 46 tests pass |
| grype | GHSA-6w46-j5rx-g56g-pytest | fix | the same pytest 8.3.5 advisory as CVE-2025-71176, at tests/requirements.txt line 1; fixed by the pin to pytest 9.0.3 |
| osv-scanner | CVE-2025-71176 | fix | the same pytest 8.3.5 advisory, reported twice (file:///src/tests/requirements.txt, no region); fixed by the pin to pytest 9.0.3 |

The image gate was green on its first wired run because the Dockerfile was hardened before the push: the base is
`python:3.13-slim` pinned by the 2026-11-17 digest, `apt-get upgrade -y` runs right after `FROM`, and pip is
uninstalled after `pip install` (its vendored msgpack, urllib3 and pkg_resources are what the course warns about;
svcdesk never calls pip at run time). Locally Trivy 0.74.0 reports zero fixable HIGH/CRITICAL in that image.
Semgrep `p/default` and gitleaks report nothing outside `lab5-canary/`.

## Bake-off

The canary set has 9 labelled defects: 4 in code (path traversal A03, YAML deserialization A09, `eval` injection A11,
SSRF A16), 3 hard-coded credentials (C01 backup.sh, C04 jwt_secret.py, C05 mailer.py) and 2 vulnerable pins
(D01 cryptography, D03 Jinja2).

- **Trivy** TP 2, FP 0, FN 7: precision 1.0, recall 0.2222, F1 0.3636. Both pins, nothing else; its secret scanner
  found none of the three credentials.
- **Grype** and **OSV-Scanner**: identical cells, TP 2, FP 0, FN 7 (precision 1.0, recall 0.2222). Grype wrote 26
  results, OSV-Scanner 36 (22 distinct advisories, most of them twice) and Trivy 18 for the same two packages; under the matching rule the many advisories collapse to two
  defects, which is the right unit for a reader.
- **gitleaks** TP 1, FP 0, FN 8: precision 1.0, recall 0.1111, F1 0.2. It saw only the `curl -u user:password` in
  backup.sh; the JWT signing key and the mailer password are plain string assignments without a recognisable token
  shape, and no default rule matches them. That was the surprise of the matrix: the secrets gate turned the canary
  red on one credential out of three.
- **Semgrep** TP 2, FP 3, FN 7: precision 0.4, recall 0.2222, F1 0.2857. It found `yaml.load` (A09) and `eval`
  (A11), missed the path traversal and the SSRF (no taint source it recognised), and its three FPs are the decoys:
  a SHA-1 ETag in etag.py (not a security control) and one formatted SQL line in ticket_counts.py reported by two
  rules.

**What I would gate on.** Trivy fs stays the dependency gate: precision 1.0 on this set and on the practice set,
one tool covering the same defects as Grype and OSV-Scanner, and it understands `.trivyignore` with expiry. Running
Grype and OSV-Scanner beside it adds no recall here (2 of 2 pins each), only volume, so I keep them as reporters
for a second advisory database, not as gates. gitleaks stays a gate because a precision of 1.0 means every red build
is real, but its recall of 0.11 says a green secrets job proves little: I would add a custom rule for
`*_SECRET`/`*_PASSWORD = "<literal>"` assignments and test it against these two misses. Semgrep at precision 0.4 is
exactly the alert-fatigue profile of Lecture 5 (Tricorder's bar is under 10 % effective false positives, this is
60 %), so it reports and is triaged, it never blocks a merge.

No detector found the path traversal (A03) or the SSRF (A16): both need data flow from a request parameter to
`os.path.join`/`open` or to an HTTP client, which pattern rules without taint configuration do not follow. And every
recall here is an upper bound: seeded defects are written to be found, sit in short files, and published studies
report detection rates several times lower on real bugs. Precision is the more trustworthy number of the two.
