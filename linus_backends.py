#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🏛️ TEMPLE IAM - LINUS BACKENDS
⚡ Multi-backend : Ollama (local) · DeepSeek · Anthropic (Claude)
🔥 Même boucle ReAct, modèle local OU API capable

Copyright © 2024 Temple IAM - All Rights Reserved

SÉCURITÉ : les clés API ne sont JAMAIS hardcodées ni passées en clair.
    Lecture depuis .{provider}_api_key (fichier) ou variable d'environnement.

Architecture :
    detect_backend(model)   → "ollama" | "deepseek" | "anthropic" (pur)
    chat_api(messages, ...)  → appelle le bon backend, NORMALISE la réponse
                               vers le format Ollama attendu par la boucle :
        {"role":"assistant", "content": str,
         "tool_calls": [{"id":.., "function":{"name":.., "arguments": dict|str}}]}

    Les traductions de format (OpenAI ↔ Anthropic) sont des fonctions pures,
    testées avec HTTP mocké (pas besoin de vraies clés pour les tests).
"""

import json
import os
from pathlib import Path
from typing import List, Optional, Tuple

import requests

# ── Endpoints ─────────────────────────────────────────────────────────────────
DEEPSEEK_URL      = "https://api.deepseek.com/v1/chat/completions"
OPENROUTER_URL    = "https://openrouter.ai/api/v1/chat/completions"
ANTHROPIC_URL     = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
API_TIMEOUT       = 300
ANTHROPIC_MAX_TOKENS = 4096
OPENROUTER_PREFIX = "openrouter/"

_HERE = Path(__file__).parent.resolve()


# ── Détection du backend ──────────────────────────────────────────────────────

def detect_backend(model: str) -> str:
    """
    Détermine le backend à partir du nom de modèle.

    Règles (fonction pure, sans ambiguïté avec les modèles Ollama) :
        - "openrouter/*"                   → "openrouter" (préfixe explicite)
        - "claude-*"                       → "anthropic"
        - "deepseek-chat" / "deepseek-reasoner" → "deepseek" (noms API exacts)
        - tout le reste (qwen3.5:2b, granite4.1:3b, deepseek-coder:latest, …)
                                           → "ollama"

    Args:
        model: Nom du modèle

    Returns:
        "ollama" | "deepseek" | "anthropic" | "openrouter"

    Example:
        >>> detect_backend("openrouter/anthropic/claude-3.5-sonnet")
        'openrouter'
        >>> detect_backend("claude-sonnet-4-5")
        'anthropic'
        >>> detect_backend("deepseek-chat")
        'deepseek'
        >>> detect_backend("qwen3.5:2b")
        'ollama'
        >>> detect_backend("deepseek-coder:latest")
        'ollama'
    """
    name = (model or "").strip().lower()
    if name.startswith(OPENROUTER_PREFIX):
        return "openrouter"
    if name.startswith("claude-"):
        return "anthropic"
    if name in ("deepseek-chat", "deepseek-reasoner"):
        return "deepseek"
    return "ollama"


# ── Lecture des clés (jamais hardcodées) ──────────────────────────────────────

def load_api_key(provider: str) -> Optional[str]:
    """
    Lit la clé API d'un provider depuis un fichier ou l'environnement.

    Ordre :
        1. fichier .{provider}_api_key dans le dossier du module
        2. variable d'environnement {PROVIDER}_API_KEY

    Args:
        provider: "deepseek" | "anthropic"

    Returns:
        La clé (strippée) ou None si introuvable.
    """
    key_file = _HERE / f".{provider}_api_key"
    try:
        if key_file.exists():
            content = key_file.read_text(encoding="utf-8").strip()
            if content:
                return content
    except OSError:
        pass
    return os.environ.get(f"{provider.upper()}_API_KEY")


# ── Backend Ollama-style (DeepSeek = OpenAI-compatible) ────────────────────────

def _normalize_openai_message(data: dict) -> dict:
    """
    Normalise une réponse OpenAI-compatible vers le format de la boucle.

    OpenAI renvoie {"choices":[{"message":{content, tool_calls:[{id,
    function:{name, arguments(str JSON)}}]}}]}. La boucle attend un message
    assistant avec le même schéma tool_calls — on extrait juste de l'enveloppe.

    Args:
        data: JSON de réponse OpenAI/DeepSeek

    Returns:
        Message assistant normalisé (Ollama-style).
    """
    choices = data.get("choices") or []
    if not choices:
        return {"role": "assistant", "content": ""}
    msg = choices[0].get("message", {}) or {}
    normalized = {
        "role": "assistant",
        "content": msg.get("content") or "",
    }
    if msg.get("tool_calls"):
        normalized["tool_calls"] = msg["tool_calls"]
    return normalized


def _chat_openai_compatible(
    messages: list,
    model: str,
    tools: Optional[list],
    url: str,
    api_key: str,
    extra_headers: Optional[dict] = None,
) -> dict:
    """
    Appel générique vers une API OpenAI-compatible (DeepSeek, OpenRouter…).

    Args:
        messages:      Historique (format OpenAI/Ollama)
        model:         Identifiant du modèle côté API
        tools:         TOOL_SCHEMAS (format OpenAI)
        url:           Endpoint chat/completions
        api_key:       Clé Bearer
        extra_headers: En-têtes additionnels (ex: OpenRouter referer/title)

    Returns:
        Message assistant normalisé.
    """
    payload: dict = {"model": model, "messages": messages, "stream": False}
    if tools:
        payload["tools"] = tools
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    resp = requests.post(url, json=payload, headers=headers, timeout=API_TIMEOUT)
    resp.raise_for_status()
    return _normalize_openai_message(resp.json())


def _chat_deepseek(messages: list, model: str, tools: Optional[list]) -> dict:
    """
    Appel DeepSeek (API OpenAI-compatible).

    Raises:
        RuntimeError: si la clé API est absente.
    """
    api_key = load_api_key("deepseek")
    if not api_key:
        raise RuntimeError(
            "DeepSeek API key missing — create .deepseek_api_key or set DEEPSEEK_API_KEY"
        )
    return _chat_openai_compatible(messages, model, tools, DEEPSEEK_URL, api_key)


def _openrouter_model_id(model: str) -> str:
    """
    Retire le préfixe 'openrouter/' pour obtenir l'id de modèle réel.

    Fonction pure (préserve la casse de l'id réel).

    Args:
        model: Nom complet (ex: 'openrouter/anthropic/claude-3.5-sonnet')

    Returns:
        Id de modèle OpenRouter (ex: 'anthropic/claude-3.5-sonnet').

    Example:
        >>> _openrouter_model_id("openrouter/openai/gpt-4o")
        'openai/gpt-4o'
        >>> _openrouter_model_id("plain-model")
        'plain-model'
    """
    if model.lower().startswith(OPENROUTER_PREFIX):
        return model[len(OPENROUTER_PREFIX):]
    return model


def _chat_openrouter(messages: list, model: str, tools: Optional[list]) -> dict:
    """
    Appel OpenRouter (API OpenAI-compatible, accès multi-modèles via 1 clé).

    Le nom de modèle est préfixé 'openrouter/' ; on le retire avant l'appel.

    Raises:
        RuntimeError: si la clé API est absente.
    """
    api_key = load_api_key("openrouter")
    if not api_key:
        raise RuntimeError(
            "OpenRouter API key missing — create .openrouter_api_key or set OPENROUTER_API_KEY"
        )
    real_model = _openrouter_model_id(model)
    extra_headers = {
        "HTTP-Referer": "https://temple-iam.local",
        "X-Title": "LINUS Agent",
    }
    return _chat_openai_compatible(
        messages, real_model, tools, OPENROUTER_URL, api_key, extra_headers,
    )


# ── Backend Anthropic (traduction de format) ──────────────────────────────────

def _to_anthropic_tools(tools: Optional[list]) -> list:
    """
    Convertit des tools OpenAI vers le format Anthropic.

    OpenAI:   {type:function, function:{name, description, parameters}}
    Anthropic:{name, description, input_schema}

    Args:
        tools: Liste de tools OpenAI (ou None)

    Returns:
        Liste de tools Anthropic (vide si None).
    """
    if not tools:
        return []
    out = []
    for t in tools:
        fn = t.get("function", {})
        out.append({
            "name": fn.get("name", ""),
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
        })
    return out


def _to_anthropic_messages(messages: list) -> Tuple[str, list]:
    """
    Convertit l'historique Ollama-style vers (system, messages) Anthropic.

    - role system            → concaténé dans la chaîne system (param séparé)
    - role user (str)        → {role:user, content:[{type:text,text}]}
    - role assistant         → blocs text + tool_use (depuis tool_calls)
    - role tool              → {role:user, content:[{type:tool_result,
                                tool_use_id, content}]}

    Args:
        messages: Historique (format Ollama)

    Returns:
        Tuple (system_str, anthropic_messages).
    """
    system_parts: List[str] = []
    out: List[dict] = []
    for m in messages:
        role = m.get("role")
        content = m.get("content") or ""
        if role == "system":
            if content:
                system_parts.append(content)
        elif role == "user":
            out.append({"role": "user", "content": [{"type": "text", "text": content}]})
        elif role == "assistant":
            blocks: List[dict] = []
            if content:
                blocks.append({"type": "text", "text": content})
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function", {})
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"_raw": args}
                blocks.append({
                    "type": "tool_use",
                    "id": tc.get("id", "call_0"),
                    "name": fn.get("name", ""),
                    "input": args,
                })
            out.append({"role": "assistant", "content": blocks or [{"type": "text", "text": ""}]})
        elif role == "tool":
            out.append({"role": "user", "content": [{
                "type": "tool_result",
                "tool_use_id": m.get("tool_call_id", "call_0"),
                "content": content,
            }]})
    return "\n\n".join(system_parts), out


def _from_anthropic_response(data: dict) -> dict:
    """
    Normalise une réponse Anthropic vers le format de la boucle.

    Anthropic renvoie content = liste de blocs [{type:text,text},
    {type:tool_use, id, name, input}]. On reconstruit un message assistant
    Ollama-style.

    Args:
        data: JSON de réponse Anthropic

    Returns:
        Message assistant normalisé.
    """
    blocks = data.get("content") or []
    text_parts: List[str] = []
    tool_calls: List[dict] = []
    for block in blocks:
        btype = block.get("type")
        if btype == "text":
            text_parts.append(block.get("text", ""))
        elif btype == "tool_use":
            tool_calls.append({
                "id": block.get("id", "call_0"),
                "function": {
                    "name": block.get("name", ""),
                    "arguments": block.get("input", {}),
                },
            })
    normalized = {"role": "assistant", "content": "".join(text_parts)}
    if tool_calls:
        normalized["tool_calls"] = tool_calls
    return normalized


def _chat_anthropic(messages: list, model: str, tools: Optional[list]) -> dict:
    """
    Appel Anthropic Messages API avec traduction de format complète.

    Args:
        messages: Historique (format Ollama)
        model:    Nom du modèle Claude
        tools:    TOOL_SCHEMAS (format OpenAI)

    Returns:
        Message assistant normalisé.

    Raises:
        RuntimeError: si la clé API est absente.
    """
    api_key = load_api_key("anthropic")
    if not api_key:
        raise RuntimeError(
            "Anthropic API key missing — create .anthropic_api_key or set ANTHROPIC_API_KEY"
        )
    system, anthropic_messages = _to_anthropic_messages(messages)
    payload: dict = {
        "model": model,
        "max_tokens": ANTHROPIC_MAX_TOKENS,
        "messages": anthropic_messages,
    }
    if system:
        payload["system"] = system
    anthropic_tools = _to_anthropic_tools(tools)
    if anthropic_tools:
        payload["tools"] = anthropic_tools
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "Content-Type": "application/json",
    }
    resp = requests.post(ANTHROPIC_URL, json=payload, headers=headers, timeout=API_TIMEOUT)
    resp.raise_for_status()
    return _from_anthropic_response(resp.json())


# ── Dispatcher ────────────────────────────────────────────────────────────────

def chat_api(messages: list, model: str, tools: Optional[list]) -> dict:
    """
    Route vers le backend API approprié (DeepSeek ou Anthropic).

    NE gère PAS Ollama (laissé à linus_agent._chat pour préserver le chemin
    local existant). Appeler uniquement quand detect_backend != "ollama".

    Args:
        messages: Historique
        model:    Nom du modèle
        tools:    TOOL_SCHEMAS

    Returns:
        Message assistant normalisé (Ollama-style).

    Raises:
        ValueError: si le backend n'est pas un backend API.
    """
    backend = detect_backend(model)
    if backend == "deepseek":
        return _chat_deepseek(messages, model, tools)
    if backend == "openrouter":
        return _chat_openrouter(messages, model, tools)
    if backend == "anthropic":
        return _chat_anthropic(messages, model, tools)
    raise ValueError(f"chat_api called for non-API backend: {backend}")
