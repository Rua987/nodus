# -*- coding: utf-8 -*-
"""Tests du sink de télémétrie Grafana (mode mock — sans token, déterministe)."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from linus_grafana import GrafanaSink, sink_from_env, EVENT_KINDS  # noqa: E402


def test_mock_record_kind_validation():
    sink = GrafanaSink(mode="mock")
    sink.record("task", task="hello")
    sink.record("plan", source="linus", names=["read_file"])
    # kind inconnu → normalisé vers "task" (ne bloque jamais un run)
    sink.record("bogus_kind", x=1)
    assert len(sink.events) == 3
    assert sink.events[0]["kind"] == "task"
    assert sink.events[2]["kind"] == "task"
    assert sink.events[1]["source"] == "linus"
    sink.close()


def test_mock_jsonl_output(tmp_path):
    path = tmp_path / "events.jsonl"
    sink = GrafanaSink(mode="mock", jsonl_path=str(path))
    sink.record("tool_call", name="grep", args='{"pattern": "x"}')
    sink.record("tool_result", name="grep", success=True, output="hits")
    sink.close()
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    evt = json.loads(lines[0])
    assert evt["kind"] == "tool_call" and evt["name"] == "grep"


def test_off_mode_noop():
    sink = GrafanaSink(mode="off")
    sink.record("task", task="x")
    assert sink.events == []
    sink.close()


def test_summary_timeline():
    sink = GrafanaSink(mode="mock")
    sink.record("task", task="make a file")
    sink.record("plan", source="linus", names=["read_file", "write_file"])
    sink.record("tool_call", name="read_file", args="{}")
    sink.record("tool_result", name="read_file", success=True, output="ok")
    sink.record("result", answer="done")
    text = sink.summary()
    assert "▶ task: make a file" in text
    assert "∘ plan [linus]" in text
    assert "↳ tool read_file" in text
    assert "● result: done" in text
    sink.close()


def test_event_kinds_set():
    assert set(EVENT_KINDS) == {"task", "plan", "tool_call", "tool_result", "verdict", "result"}


def test_sink_from_env_mock(monkeypatch):
    monkeypatch.delenv("NODUS_GRAFANA", raising=False)
    sink = sink_from_env()
    assert sink.mode == "mock"
    sink.close()


def test_sink_from_env_jsonl(monkeypatch, tmp_path):
    target = tmp_path / "out.jsonl"
    monkeypatch.setenv("NODUS_GRAFANA", f"jsonl:{target}")
    sink = sink_from_env()
    assert sink.mode == "mock"
    assert sink._jsonl is not None
    sink.record("plan", source="linus", names=[])
    assert target.exists()
    sink.close()


def test_sink_from_env_off(monkeypatch):
    monkeypatch.setenv("NODUS_GRAFANA", "off")
    sink = sink_from_env()
    assert sink.mode == "off"
    sink.record("task", task="x")
    assert sink.events == []
    sink.close()


def test_context_manager_closes(tmp_path):
    path = tmp_path / "ctx.jsonl"
    with GrafanaSink(mode="mock", jsonl_path=str(path)) as sink:
        sink.record("plan", source="cloud", steps=3)
    # __exit__ close() ne doit pas lever
    assert path.exists()
