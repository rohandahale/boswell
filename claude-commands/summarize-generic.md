---
description: Summarize a meeting transcript when the meeting type isn't obvious.
---

You are summarizing a meeting of unknown type. Current directory contains `transcript.md`, `metadata.json`, and optionally `notes.md`.

## Steps

1. Read `transcript.md`, `metadata.json`, and `notes.md` (if present).
2. Read `../CLAUDE.md` for standing context.
3. First, classify the meeting: 1:1, working-group, seminar, interview, or other. State your classification in one line at the top.
4. Produce a summary with:
   - **Meeting type** — your classification
   - **Participants** — inferred
   - **Purpose** — why this meeting happened, inferred from content
   - **Key points** — topic bullets
   - **Decisions** — if any
   - **Action items** — owner-prefixed
   - **Follow-ups** — open items
5. Write to `summary.md`.
6. **Automatically** file to Notion via the Notion MCP (no confirmation). Add a new row to the existing Meetings database (DB URL in `../CLAUDE.md`):
   - Properties: Name, Date, Type=your classification, Attendees, Action Items
   - Page body: the full summary as rendered markdown
   - Below the summary, add a **collapsible toggle block** titled "Full transcript" containing the complete contents of `transcript.md`. Notion blocks have a ~2000-char limit per paragraph; split the transcript into multiple paragraph children of the toggle if needed.
   
   If the MCP or DB URL is missing, skip and note it. If filing fails, report the error.

## Style

- If you're guessing, say so. Better to flag uncertainty than to fabricate structure the meeting doesn't have.
- If the transcript is mostly silence or unintelligible, say so and stop.
