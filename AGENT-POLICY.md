<!-- ai-generated: 90% - drafted by Claude Code, reviewed by the student -->
# Agent policy

The `reviewer` sub-agent (`.claude/agents/reviewer.md`) reads and comments. Each denied tool below is a
blast-radius decision: what could go wrong if a reviewer could do it, and why that is not the reviewer's call.

- Bash(rm *): the reviewer reads and comments; deleting files is the author's decision, and a wrong delete under src/ or specs/ could lose work that is not yet committed.
- Bash(git push *): pushing publishes to the graded public repository and to origin/main that receipts point at; only the author may decide what becomes public.
- Bash(git tag *): tags lab1/v* are attempts that must never move; a tag created or moved by an agent could void a graded attempt.
- Bash(docker *): docker commands can remove volumes, images and running containers on the author's machine, including the named volume with ticket data; review needs none of that.
- Write: a reviewer that writes files blurs who authored the change and can silently alter code the author thinks they reviewed; findings go into the conversation instead.
- Edit: same blast radius as Write, only smaller per call; an edit to DECISIONS.md or sla.py could break the declared decisions and L1-CORE-4 without the author noticing.
- WebFetch: the review works only from files in the repository; fetching pages could pull untrusted instructions into the session and leak repository content in request URLs.
