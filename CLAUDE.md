<!-- ai-generated: 90% - drafted by Claude Code, reviewed by the student -->
# svcdesk - notes for Claude Code

- Contract: API.md (course package) is authoritative; the specification lives in `specs/001-svcdesk/`.
- Decisions: C1 = wallclock, C2 = immutable, C3 = matrix. `DECISIONS.md` front matter must match what the
  running service does; change both together or not at all.
- Code: `src/svcdesk/` (FastAPI). `sla.py` holds the matrix and both clocks, `app.py` the HTTP layer and
  state machine, `store.py` the SQLite store.
- Run the own tests: `docker compose --profile tests run --rm --build tests`.
- Run the checker: `./itsmlab.sh verify 1` (Windows: `.\itsmlab.ps1 verify 1`).
- Never add bind mounts, never fetch anything at run time, keep the `ai-generated:` header in every file
  under `src/` and `specs/`.
- Tags `lab1/v*` never move; do not push, tag or open issues without the student.
