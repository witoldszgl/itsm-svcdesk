<!-- ai-generated: 90% - drafted by Claude Code, reviewed by the student -->
# svcdesk constitution

1. **The contract is API.md.** REQUIREMENTS.md says why; API.md says exactly what. When they differ in
   precision, API.md wins, and the checker (CHECKS.md) is how we know we honour it.
2. **Specification before code.** Nothing is written under `src/` before the specification under `specs/`
   is committed and receipted.
3. **Conflicts are decided, not hidden.** Each contradictory pair is resolved by rejecting the smallest
   conflicting part of one requirement; the decision is written in `DECISIONS.md` and the running service
   must behave exactly as declared.
4. **Time is explicit.** Every clock-dependent behaviour takes `now` from the request (test clock) or from
   real UTC time; there is no hidden global time. Instants are stored and returned in UTC with `Z`.
5. **Small and boring.** Python 3.13, FastAPI, SQLite on a named volume; no network at run time; no bind
   mounts; dependencies installed at build time.
6. **Everything is tested.** Our own pytest suite covers the matrix, the state machine, the reopen window,
   the SLA vectors and breach/pause, and runs against the real container.
7. **Disclosure.** Every source and specification file carries an `ai-generated:` header.
