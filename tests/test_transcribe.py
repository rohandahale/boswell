from datetime import date

from boswell.transcribe import (
    Segment,
    format_duration,
    format_timestamp,
    render_transcript_md,
)


def test_format_timestamp_under_hour():
    assert format_timestamp(0) == "00:00:00"
    assert format_timestamp(5) == "00:00:05"
    assert format_timestamp(65) == "00:01:05"


def test_format_timestamp_over_hour():
    assert format_timestamp(3723) == "01:02:03"


def test_format_timestamp_negative_clamps():
    assert format_timestamp(-5) == "00:00:00"


def test_format_duration_short():
    assert format_duration(65) == "1m 5s"


def test_format_duration_long():
    assert format_duration(3723) == "1h 2m 3s"


def test_render_transcript_md_header():
    out = render_transcript_md(
        [],
        title="Weekly 1:1",
        date=date(2026, 4, 20),
        duration_seconds=2832,  # 47m 12s
    )
    assert "# Transcript — Weekly 1:1" in out
    assert "**Date:** 2026-04-20" in out
    assert "**Duration:** 47m 12s" in out
    assert "---" in out


def test_render_transcript_md_segments_in_order():
    segs = [
        Segment(start=11.0, end=14.0, text="Hello there.", speaker="Them"),
        Segment(start=3.0, end=7.5, text="Hi, how are you?", speaker="Me"),
    ]
    # Caller is expected to have sorted; render in the order given.
    segs.sort(key=lambda s: s.start)
    out = render_transcript_md(
        segs, title="t", date=date(2026, 1, 1), duration_seconds=20
    )
    lines = [l for l in out.splitlines() if l.startswith("[")]
    assert lines[0] == "[00:00:03] Me: Hi, how are you?"
    assert lines[1] == "[00:00:11] Them: Hello there."


def test_render_transcript_md_skips_empty_text():
    segs = [
        Segment(start=0.0, end=1.0, text="", speaker="Me"),
        Segment(start=1.0, end=2.0, text="ok", speaker="Me"),
    ]
    out = render_transcript_md(
        segs, title="t", date=date(2026, 1, 1), duration_seconds=2
    )
    assert out.count("\n[") == 1


def test_render_transcript_md_blank_line_between_speaker_turns():
    segs = [
        Segment(start=1.0, end=2.0, text="hi", speaker="Me"),
        Segment(start=3.0, end=4.0, text="hello", speaker="Them"),
        Segment(start=5.0, end=6.0, text="ok", speaker="Them"),
        Segment(start=7.0, end=8.0, text="bye", speaker="Me"),
    ]
    out = render_transcript_md(
        segs, title="t", date=date(2026, 1, 1), duration_seconds=10
    )
    body_lines = out.split("---\n\n", 1)[1].splitlines()
    assert body_lines[0] == "[00:00:01] Me: hi"
    assert body_lines[1] == ""
    assert body_lines[2] == "[00:00:03] Them: hello"
    assert body_lines[3] == "[00:00:05] Them: ok"
    assert body_lines[4] == ""
    assert body_lines[5] == "[00:00:07] Me: bye"
