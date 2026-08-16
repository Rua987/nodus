# Nodus

**A tiny local planner that turns a natural-language task into an ordered
sequence of tool calls — and an observability layer that streams every step
into Grafana Cloud.**

> Nodus is the public alias of **LINUS**, a research planner developed for a
> 324M-parameter model (trained locally, runs on CPU or a single GPU). The
> planner outputs **only tool names** — no arguments, no replanning. The harness
> fills the arguments, verifies each step, and executes.

---

## Why Nodus?

Agentic loops are expensive: a big frontier model plans each task token-by-token,
then an executor re-derives the same steps. Nodus replaces the planning phase
with a **fixed, tiny, local model** that was fine-tuned on one single task:

> NL task → ordered JSON array of tool names (`["glob", "read_file", "edit_file"]`)

Because the planner is small and local, planning is **free, private, and fast**
— no API call, no prompt re-sent, no data leaving the machine. The executor
keeps the last word (it fills real arguments and verifies), so Nodus is a
*suggestion engine*, not a replacement for the loop.

**Measured on unseen tasks** (120-task fresh holdout, entities never seen in
training):

| Planner | Plan accuracy (raw) | + guardrails |
|---|---|---|
| previous (v2b) | 79% | 91% |
| **Nodus (v5)** | **99%** | **99%** |

- 0 guardrail regressions across all replays.
- **End-to-end significance** (statistical, p = 0.0139, sign test over 200
  runs): Nodus planning *significantly improves* a local executor on multi-step
  tasks — 27 tasks better, 11 worse, effect growing with plan length.

---

## The demo: watch Nodus think, in Grafana

Nodus integrates **Grafana Cloud MCP** (`mcp-grafana`) as its observability
layer. Every run streams structured events — task, plan, each tool call, each
result — into a Grafana dashboard as live annotations:

```
▶ task: deploy the app then verify health
  ∘ plan [linus]: ['bash', 'bash']
    ↳ tool bash {"command": "echo step1"}   ✓ ok
    ↳ tool bash {"command": "echo step2"}   ✓ ok
● result: Done.
```

- **mock mode** (default, zero setup, no token): events collected in memory +
  JSONL — perfect for the video / CI.
- **live mode**: `NODUS_GRAFANA=mcp` + `GRAFANA_URL` + `GRAFANA_SERVICE_ACCOUNT_TOKEN`
  (Grafana Cloud free tier, service account `glsa_…`). Each event becomes a
  `grafana.create_annotation` call through the official `mcp-grafana` server.

---

## Quick start

```bash
# 1. Install Python deps (torch optional — planner runs on CPU)
pip install -r requirements-ci.txt

# 2. Drop the planner checkpoint into checkpoints/
#    (checkpoint_sft_plan_v5.pt, ~940 MB — see "Checkpoints" below)

# 3. Plan a task (mock telemetry, no Grafana account needed)
python linus_plan_local.py --plan-once
#   echo "read src/main.py, then search for request_id, then edit it" | \
#     python linus_plan_local.py --plan-once
#   → {"ok": true, "names": ["read_file", "grep", "edit_file"]}

# 4. Stream the whole run into Grafana (live) or to JSONL (mock)
NODUS_GRAFANA=mcp python linus_agent.py "..." --plan --plan-source linus
NODUS_GRAFANA=jsonl:run.jsonl python linus_agent.py "..." --plan --plan-source linus
```

## Run the demo (30 seconds, zero dependencies)

`demo_agentic_cinema.py` replays the full pipeline end to end — task → plan →
tools → Grafana — deterministically, with **no checkpoint, no Ollama, no token**
required. Add `checkpoints/checkpoint_sft_plan_v5.pt` (or set `LINUS_PLAN_CKPT`)
and the same command uses the **real 324M planner** instead of the gold plan:

```bash
python demo_agentic_cinema.py                 # plan → tools → timeline
python demo_agentic_cinema.py --list-tasks    # show the curated demo tasks
python demo_agentic_cinema.py --contrast      # plan vs no-plan side by side
python demo_agentic_cinema.py --live          # real Ollama executor (optional)
```

It streams every step through the same `GrafanaSink` — mock mode prints the
timeline, `NODUS_GRAFANA=mcp` pushes live annotations to Grafana Cloud:

```
▶ task: Read src/utils.py, then save a new file config_demo.yaml with a stub, then verify it exists.
  ∘ plan [linus]: ['read_file', 'write_file', 'bash']
    ↳ tool read_file {"path": "src/utils.py"}
      ✓ def helper():     return 42
    ↳ tool write_file {"path": "config_demo.yaml", "content": "# demo stub config\nmode: default\n"}
      ✓ wrote 33 bytes -> config_demo.yaml
    ↳ tool bash {"command": "ls config_demo.yaml"}
      ✓ config_demo.yaml exists
● result: Done: wrote config_demo.yaml.
```

### Grafana Cloud live setup (one time)

1. Create a free account at [grafana.com](https://grafana.com/cloud/).
2. **Administration → Service accounts** → add a token (`glsa_…`) with
   `dashboards:write` (annotations).
3. Run with the env vars above; the harness starts `mcp-grafana` (via `uvx`)
   automatically and calls `create_annotation` for each event.

---

## Repository layout

```
bridge/            plan bridge: prompt, parser, tool schemas, versions
linus_plan_local.py  local inference (plan NL → tool names)
linus_auto_model.py  model architecture (324M)
linus_gpt.py         transformer core (RoPE, RMSNorm)
linus_agent.py       ReAct executor loop (fills args, verifies, executes)
linus_verify.py      guardrails: normalize + 7 predicates + transformations
linus_grafana.py     Grafana Cloud telemetry sink (mock / mcp / off)
linus_mcp_client.py  multi-server MCP registry (namespacing, pinning)
demo_agentic_cinema.py  self-contained demo: task → plan → tools → Grafana
tests/             910 passing tests (pytest)
```

### Guardrails (why 99% is real)

`linus_verify.py` normalizes the raw plan: it fixes the systematic failure
classes the model was trained against (superfluous `grep` before `read`,
`bash`-as-write, missing final `write`) and validates the result. The guardrail
never *replaces* the executor — it makes the suggestion robust.

---

## Checkpoints

The model weights are **not** committed to git (too large). Obtain
`checkpoints/checkpoint_sft_plan_v5.pt` from the release assets (or your own
SFT) and point `LINUS_PLAN_CKPT` at it:

```bash
export LINUS_PLAN_CKPT=checkpoints/checkpoint_sft_plan_v5.pt
# or: $env:LINUS_PLAN_CKPT = "checkpoints\checkpoint_sft_plan_v5.pt"
```

---

## Training & method (summary)

Nodus v5 was fine-tuned from v2b on 20k planning examples (60% "hard" steps),
scheduled on a rented RTX 5090 for ~3.5 GPU-minutes. It was promoted to
production after a **fresh 120-task holdout** (no entity overlap with any
training or validation corpus) showed 99% plan accuracy with zero guardrail
regressions — a decisive improvement over the previous planner (91%).

---

## Tests

```bash
python -m pytest tests/        # 910 passed
```

---

## License

Copyright © 2024 Temple IAM — All Rights Reserved.
See individual file headers. Contact the maintainers before commercial use.

---

*Prepared for the Agentic Cinema hackathon (Google Cloud + partners). Partner
service activated: Grafana Cloud MCP (`mcp-grafana`).*
