# Meetings folder — standing context for Claude Code

This file lives at `~/Meetings/CLAUDE.md` and is auto-discovered when `claude` is invoked from any meeting subfolder. Fill in the sections below with your own details — they're the context that makes summaries useful instead of generic.

## About me

<!-- 2-4 sentences: your role, field, institution, current projects. The more specific, the better the summaries. -->

TODO: fill in.

## Frequent collaborators

<!-- One line per person: name — role — how they relate to you. The summarizer uses this to attribute action items and infer who "Them" is in 1:1s. -->

- TODO: Alice — PI — advisor on project X
- TODO: Bob — postdoc collaborator — co-author on Y

## Ongoing projects

<!-- Named projects with a one-line description. Helps the summarizer connect meeting content to work streams. -->

- TODO: Project X — one-line description
- TODO: Project Y — one-line description

## Notion Meetings database

<!-- Paste the URL of your Notion Meetings database here once you've set it up (Phase 2). The slash commands read this to know where to file summaries. -->

Database URL: TODO

Expected schema:
- **Title** (title)
- **Date** (date)
- **Type** (select: 1on1, working-group, seminar, interview, other)
- **Attendees** (multi-select or text)
- **Summary** (rich text / page body)
- **Action Items** (rich text, checkboxes)

## Conventions

- Transcripts produced by Boswell label channels "Me" (left/mic) and "Them" (right/BlackHole). For 1:1s "Them" is the other person; for group calls it's everyone else mixed. For in-person meetings the BlackHole channel is empty, so everything is labeled "Speaker".
- Meeting folder names follow `YYYY-MM-DD-HHMM-<slug>`. The slug is often the best hint at the meeting type and participants.
