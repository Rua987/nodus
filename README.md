# Nodus

**Nodus** is a local, privacy-first task planner for agentic AI: a small
(324M-parameter) model that turns a natural-language task into an *ordered
sequence of tool names* (no arguments, no replanning), which an executor then
fills in and runs.

This repository contains the **harness** that runs Nodus end to end:
inference (`linus_plan_local`), verification / guardrails (`linus_verify`),
plan parsing (`bridge/`), and the agent loop (`linus_agent`).

> Full English documentation, setup guide and measured results: see
> `README_AGENT.md` (an up-to-date English README is in progress).

## Quick start

```bash
pip install -r requirements-ci.txt
python linus_plan_local.py --plan-once
```

The planner checkpoint (`checkpoint_sft_plan_v5.pt`, ~940 MB) is not stored in
git; place it in `checkpoints/` or point `LINUS_PLAN_CKPT` at it (see
`README_AGENT.md`).

## Status

- Planner v5 promoted to production 2026-08-15:
  **119/120 (99%)** exact plan match on a fresh holdout of 120 unseen tasks
  (with guardrails), vs 91% for the previous planner — **0 regressions**.
- Harness: 883 tests passing.

> This repository is a clean, self-contained snapshot of the LINUS harness
> prepared for the *Agentic Cinema* hackathon (Google Cloud + partners).
