#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🏛️ NODUS — Grafana Cloud telemetry sink
⚡ Stream chaque étape d'un run (tâche → plan → tool calls → verdicts → résultat)
   vers Grafana Cloud via le serveur MCP officiel `mcp-grafana`.

Deux modes :
  - mock (défaut) : aucun token requis, événements collectés en mémoire + JSONL
    (déterministe, testé hors-ligne, idéal pour la démo de développement).
  - mcp (live)    : se connecte à `mcp-grafana` (stdio) via `McpBridge` et
    mappe chaque événement sur `grafana.create_annotation` (tags = nodus,kind).

Le planificateur Nodus garde son vocabulaire de 8 outils natifs ; Grafana est la
couche *observabilité* du harnais : le dashboard devient le « scope » de l'agent.
Aucun échec MCP ne casse jamais un run (fallback silencieux + compteur).
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Les événements normalisés du harnais (une ligne JSON chacun).
EVENT_KINDS = ("task", "plan", "tool_call", "tool_result", "verdict", "result")

# Tags Grafana fixes pour retrouver les annotations d'un run.
_TAGS = ["nodus", "agentic-cinema"]


def _now() -> str:
    """Horodatage ISO-8601 UTC."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class GrafanaSink:
    """Enregistre les événements d'un run Nodus vers Grafana Cloud.

    Args:
        mode:      "mock" (défaut) | "mcp" | "off"
        url:       Grafana instance URL (ex https://my.grafana.net). En mode
                   mcp, défaut = env GRAFANA_URL.
        token:     Service account token (glsa_…). En mode mcp, défaut = env
                   GRAFANA_SERVICE_ACCOUNT_TOKEN.
        jsonl_path: En mode mock, écrire les événements aussi en JSONL.
    """

    def __init__(
        self,
        mode: str = "mock",
        url: Optional[str] = None,
        token: Optional[str] = None,
        jsonl_path: Optional[str] = None,
    ) -> None:
        self.mode = mode
        self.events: List[Dict[str, Any]] = []
        self.errors: List[str] = []
        self._jsonl = None
        self._bridge = None  # McpBridge (import tardif — évite le coût mcp en mock)
        if jsonl_path:
            self._jsonl = Path(jsonl_path)
            self._jsonl.parent.mkdir(parents=True, exist_ok=True)

        if mode == "mcp":
            self._connect_mcp(url=url, token=token)

    # ── Connexion MCP (live) ───────────────────────────────────────────────

    def _connect_mcp(self, url: Optional[str], token: Optional[str]) -> None:
        """Démarre le serveur mcp-grafana (stdio) et l'enregistre dans le bridge."""
        url = url or os.environ.get("GRAFANA_URL", "").strip()
        token = token or os.environ.get("GRAFANA_SERVICE_ACCOUNT_TOKEN", "").strip()
        if not url or not token:
            self.errors.append(
                "mcp mode requires GRAFANA_URL and GRAFANA_SERVICE_ACCOUNT_TOKEN "
                "(set env vars or pass url=/token=). Falling back to mock."
            )
            self.mode = "mock"
            return
        try:
            from linus_mcp_client import McpBridge
        except ImportError:
            self.errors.append("mcp package not installed (pip install mcp). Falling back to mock.")
            self.mode = "mock"
            return

        # mcp-grafana se lance via uvx (officiel) — config stdio à la volée.
        # Sur Windows, uvx.exe peut être préféré ; on laisse PATH décider.
        import tempfile
        import uuid
        import json as _json

        config = {
            "mcpServers": {
                "grafana": {
                    "command": "uvx",
                    "args": ["mcp-grafana"],
                    "env": {
                        "GRAFANA_URL": url,
                        "GRAFANA_SERVICE_ACCOUNT_TOKEN": token,
                    },
                }
            }
        }
        cfg_dir = Path(tempfile.gettempdir()) / f"nodus_mcp_{uuid.uuid4().hex[:8]}"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = cfg_dir / "mcp.json"
        cfg_path.write_text(_json.dumps(config), encoding="utf-8")

        bridge = McpBridge()
        err = bridge.connect_servers(str(cfg_path), ("grafana",))
        if err:
            self.errors.append(f"grafana MCP connect failed: {err}")
            bridge.close()
            self.mode = "mock"
            return
        self._bridge = bridge
        self.mode = "mcp"

    # ── API publique ───────────────────────────────────────────────────────

    def record(self, kind: str, **fields: Any) -> Optional[Dict[str, Any]]:
        """Enregistre un événement structuré. Retourne l'événement (None si off)."""
        if self.mode == "off":
            return None
        if kind not in EVENT_KINDS:
            kind = "task"  # kind inconnu → ne jamais bloquer un run
        evt: Dict[str, Any] = {"ts": _now(), "kind": kind}
        evt.update(fields)
        self.events.append(evt)
        if self._jsonl is not None:
            with self._jsonl.open("a", encoding="utf-8") as f:
                f.write(json.dumps(evt, ensure_ascii=False) + "\n")

        if self.mode == "mcp" and self._bridge is not None:
            self._push_annotation(evt)
        return evt

    def _push_annotation(self, evt: Dict[str, Any]) -> None:
        """Mode live : crée une annotation Grafana à partir d'un événement."""
        try:
            text = _annotation_text(evt)
            self._bridge.call(
                "grafana.create_annotation",
                {"text": text, "tags": _TAGS + [f"nodus:{evt['kind']}"]},
            )
        except Exception as exc:  # jamais fatal
            self.errors.append(f"create_annotation failed: {exc}")

    def search_dashboards(self, query: str = "") -> Any:
        """Mode live : liste les dashboards (read — bon pour la démo)."""
        if self.mode != "mcp" or self._bridge is None:
            return {"mode": self.mode, "error": "search_dashboards requires mcp mode"}
        return self._bridge.call("grafana.search_dashboards", {"query": query})

    def dashboard_summary(self, uid: str) -> Any:
        if self.mode != "mcp" or self._bridge is None:
            return {"mode": self.mode, "error": "dashboard_summary requires mcp mode"}
        return self._bridge.call("grafana.get_dashboard_summary", {"uid": uid})

    def summary(self) -> str:
        """Vue humaine (terminal / vidéo) : timeline compacte du run."""
        lines: List[str] = []
        for evt in self.events:
            kind = evt["kind"]
            if kind == "task":
                lines.append(f"▶ task: {evt.get('task', '')[:120]}")
            elif kind == "plan":
                names = evt.get("names")
                lines.append(f"  ∘ plan [{evt.get('source', '?')}]: {names}")
            elif kind == "tool_call":
                lines.append(f"    ↳ tool {evt.get('name')} {evt.get('args', '')}")
            elif kind == "tool_result":
                ok = "✓" if evt.get("success") else "✗"
                preview = str(evt.get("output", ""))[:80].replace("\n", " ")
                lines.append(f"      {ok} {preview}")
            elif kind == "verdict":
                lines.append(f"  ! verdict: {evt.get('message', '')}")
            elif kind == "result":
                lines.append(f"● result: {evt.get('answer', '')[:120]}")
        return "\n".join(lines) if lines else "(no events)"

    def close(self) -> None:
        if self._bridge is not None:
            try:
                self._bridge.close()
            except Exception:
                pass
            self._bridge = None

    def __enter__(self) -> "GrafanaSink":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


def _annotation_text(evt: Dict[str, Any]) -> str:
    """Réduit un événement à un texte d'annotation lisible."""
    kind = evt["kind"]
    if kind == "task":
        return f"task: {evt.get('task', '')[:200]}"
    if kind == "plan":
        return f"plan [{evt.get('source', '?')}]: {evt.get('names')}"
    if kind == "tool_call":
        return f"tool {evt.get('name')}: {str(evt.get('args', ''))[:120]}"
    if kind == "tool_result":
        status = "ok" if evt.get("success") else "error"
        return f"tool {evt.get('name')} → {status}: {str(evt.get('output', ''))[:100]}"
    if kind == "verdict":
        return f"verdict: {evt.get('message', '')[:200]}"
    return f"result: {str(evt.get('answer', ''))[:200]}"


def sink_from_env() -> GrafanaSink:
    """Sink piloté par l'environnement (pratique pour la démo) :
       NODUS_GRAFANA=mcp → live (GRAFANA_URL + GRAFANA_SERVICE_ACCOUNT_TOKEN) ;
       NODUS_GRAFANA=jsonl:/path → mock + JSONL ; sinon mock."""
    spec = os.environ.get("NODUS_GRAFANA", "").strip()
    if spec == "mcp":
        return GrafanaSink(mode="mcp")
    if spec.startswith("jsonl:"):
        return GrafanaSink(mode="mock", jsonl_path=spec.split(":", 1)[1])
    if spec == "off":
        return GrafanaSink(mode="off")
    return GrafanaSink(mode="mock")
