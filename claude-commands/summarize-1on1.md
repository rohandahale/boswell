---
description: Summarize a 1:1 meeting transcript from the current meeting folder.
---

You are summarizing a 1:1 meeting. The current working directory is a meeting folder containing:

- `transcript.md` — stereo-split transcript with "Me" and "Them" labels
- `metadata.json` — recording metadata (title, date, duration)
- `notes.md` — optional handwritten notes (read if present)

## Steps

1. Read `transcript.md`, `metadata.json`, and `notes.md` (if present) from the current directory.
2. Read `../CLAUDE.md` for standing context about the user and collaborators. Identify who "Them" likely is based on the folder name / title.
3. Produce a structured summary with these sections:
   - **Participants** — Me and the other party (inferred name if possible)
   - **Topics discussed** — bullet list, 1 line each
   - **Decisions** — concrete things agreed upon
   - **Action items** — bulleted, prefixed with owner ("Me:" / "<Name>:") and due date if mentioned
   - **Open questions** — anything left unresolved
   - **Notable quotes** — ≤3 verbatim lines that capture the meeting's thrust
4. Write the summary to `summary.md` in the current folder.
5. **Automatically** file to Notion (no confirmation prompt). Use the Notion MCP to add a new row (Notion calls each row a "page") to the existing Meetings database (see `../CLAUDE.md` for the DB URL):
   - Properties: Name=meeting title, Date=meeting date, Type=1on1, Attendees=inferred list, Action Items
   - Page body: the full summary as rendered markdown
   - Below the summary, add a **collapsible toggle block** titled "Full transcript" containing the complete contents of `transcript.md`. Notion blocks have a ~2000-char limit per paragraph; split the transcript into multiple paragraph children of the toggle if needed.
   
   If the Notion MCP isn't configured or the DB URL is missing, skip filing and note that in the final message. If filing fails, report the error but leave `summary.md` in place.

## Style

- Favor signal over completeness. A 30-minute 1:1 should summarize in under a screen.
- Preserve names verbatim from the transcript; don't invent.
- If the transcript is short or mostly silence, say so rather than padding.
