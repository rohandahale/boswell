from datetime import datetime
from pathlib import Path

import pytest

from boswell import paths


def test_make_slug_basic():
    assert paths.make_slug("Standup with Alice") == "standup-with-alice"


def test_make_slug_collapses_punctuation():
    assert paths.make_slug("1:1 — Bob & Co (weekly)!") == "1-1-bob-co-weekly"


def test_make_slug_empty_falls_back():
    assert paths.make_slug("") == "untitled"
    assert paths.make_slug("!!!") == "untitled"


def test_make_slug_trims_length():
    long = "x" * 200
    assert len(paths.make_slug(long)) <= 40


def test_meeting_dirname_format():
    now = datetime(2026, 4, 20, 13, 45)
    assert paths.meeting_dirname("Test", now) == "2026-04-20-1345-test"


def test_meetings_root_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("BOSWELL_MEETINGS_ROOT", str(tmp_path))
    assert paths.meetings_root() == tmp_path


def test_new_meeting_dir_creates_folder(monkeypatch, tmp_path):
    monkeypatch.setenv("BOSWELL_MEETINGS_ROOT", str(tmp_path))
    d = paths.new_meeting_dir("Test Meeting", datetime(2026, 4, 20, 9, 0))
    assert d.is_dir()
    assert d.name == "2026-04-20-0900-test-meeting"


def test_new_meeting_dir_conflict_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("BOSWELL_MEETINGS_ROOT", str(tmp_path))
    now = datetime(2026, 4, 20, 9, 0)
    paths.new_meeting_dir("Test", now)
    with pytest.raises(FileExistsError):
        paths.new_meeting_dir("Test", now)


def test_artifact_paths(tmp_path: Path):
    assert paths.audio_path(tmp_path).name == "audio.wav"
    assert paths.transcript_path(tmp_path).name == "transcript.md"
    assert paths.metadata_path(tmp_path).name == "metadata.json"
