---
description: Summarize a working-group / multi-person meeting transcript.
---

You are summarizing a multi-person working-group meeting. Current directory contains `transcript.md`, `metadata.json`, and optionally `notes.md`.

## Steps

1. Read `transcript.md`, `metadata.json`, and `notes.md` (if present).
2. Read `../CLAUDE.md` for standing context on collaborators and ongoing projects.
3. The transcript labels channels "Me" and "Them" — "Them" is a mix of everyone else. Use context (names mentioned, topic handoffs) to attribute turns to individuals where possible. When uncertain, keep the "Them" label rather than guessing.
4. Produce a summary with:
   - **Participants** — list attendees (inferred from transcript / title)
   - **Agenda / topics** — organized by topic, not chronology
   - **Decisions** — concrete outcomes
   - **Action items** — owner-prefixed, with due dates when stated
   - **Blockers / risks** — anything flagged as at-risk
   - **Next meeting** — date/agenda if mentioned
5. Write the summary to `summary.md`.
6. **Automatically** file to Notion via the Notion MCP (no confirmation). Add a new row to the existing Meetings database (DB URL in `../CLAUDE.md`):
   - Properties: Name, Date, Type=working-group, Attendees, Action Items
   - Page body: the full summary as rendered markdown
   - Below the summary, add a **collapsible toggle block** titled "Full transcript" containing the complete contents of `transcript.md`. Notion blocks have a ~2000-char limit per paragraph; split the transcript into multiple paragraph children of the toggle if needed.
   
   If the MCP or DB URL is missing, skip and note it. If filing fails, report the error.

## Style

- Group by topic, not speaker. A working group cares about what was decided, not who said what.
- Call out ambiguity explicitly rather than guessing ownership of action items.
