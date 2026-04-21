---
description: Summarize a seminar, talk, or lecture transcript.
---

You are summarizing a seminar / research talk. Current directory contains `transcript.md`, `metadata.json`, and optionally `notes.md`.

## Steps

1. Read `transcript.md`, `metadata.json`, and `notes.md` (if present).
2. Read `../CLAUDE.md` for context on the user's research interests.
3. The transcript likely has one dominant speaker ("Them"); "Me" may only appear during Q&A. Treat the main body as a monologue.
4. Produce a summary with:
   - **Speaker & title** — inferred from folder name or opening remarks
   - **Thesis** — one-sentence claim the talk is defending
   - **Key points** — 4–8 bullets, technical and specific
   - **Methods / evidence** — how the claim is supported
   - **Open questions raised in Q&A** — with askers if identifiable
   - **Connections to user's work** — only if `../CLAUDE.md` gives enough context to say something non-generic; otherwise omit
   - **References worth following up** — papers, tools, datasets mentioned
5. Write to `summary.md`.
6. **Automatically** file to Notion via the Notion MCP (no confirmation). Add a new row to the existing Meetings database (DB URL in `../CLAUDE.md`):
   - Properties: Name=speaker/title, Date, Type=seminar, Attendees=speaker + attendees if known
   - Page body: the full summary as rendered markdown
   - Below the summary, add a **collapsible toggle block** titled "Full transcript" containing the complete contents of `transcript.md`. Notion blocks have a ~2000-char limit per paragraph; split the transcript into multiple paragraph children of the toggle if needed.
   
   If the MCP or DB URL is missing, skip and note it. If filing fails, report the error.

## Style

- Technical accuracy > polish. Preserve jargon and specific terms verbatim.
- Don't invent references not mentioned in the transcript.
