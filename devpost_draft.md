# Nodus — Devpost submission draft

> Copy the section bodies below into the corresponding Devpost fields.
> Metrics cited are verified (see README): **99%**, **p = 0.0139**. The
> 27/30 arithmetic probe is deliberately NOT cited.
> Gallery image READY: `gallery_timeline.png` (repo root — real live run).
> One placeholder left: the demo-video link (add after recording — script in
> `video_script_3min.md`).

---

## Title

**Nodus — a tiny local planner that makes agentic loops free (and observable)**

## Tagline

A 324M-parameter planner turns any natural-language task into an ordered list
of tool calls — runs on a laptop CPU, and streams every step to Grafana Cloud.

## Elevator pitch (≈ 200 words)

Every agentic system pays a hidden tax: before it can do anything, a frontier
model burns tokens just to plan — and for simple tasks, planning can cost more
than the work itself. Nodus replaces that planning phase with a 324M-parameter
transformer, fine-tuned on a single job: turn a natural-language task into an
ordered sequence of tool names. No arguments, no replanning. The harness fills
the details, executes, and verifies.

Because the planner is tiny and local, planning is free, private, and fast —
your code never leaves the machine. And every step of the run is streamed live
to Grafana Cloud as an annotation, so an agent session becomes something you
can replay, correlate, and audit.

The results are real: on a fresh holdout of 120 tasks the model had never seen,
Nodus plans 119 correctly (99%, zero regressions). End-to-end, the plan
significantly improves a local executor (sign test, p = 0.0139), with the
effect growing as plans get longer — exactly where agents need help most.

This hackathon entry activates **Grafana Cloud** through the official
`mcp-grafana` server as the observability layer: task, plan, every tool call,
and the final result land in a dashboard as tagged annotations in real time.

## Inspiration

Agentic loops are expensive twice over: planning burns frontier-model tokens,
and re-planning makes loops slow and hard to audit. We wondered how much of
that cost is actually necessary. A 324M model can't write code well — but
"what tools do I need, and in what order?" is a much simpler question than
"write the code." Train a small model on exactly that question, and the big
model is left with only what it's good at: executing.

## What it does

1. **Plans** — NODUS (the 324M planner) reads a task and outputs an ordered
   JSON array of tool names from a fixed 8-tool vocabulary.
2. **Executes** — the harness fills the arguments, runs each tool, and verifies
   the result against guardrails trained on the model's known failure classes.
3. **Observes** — every event (task → plan → tool_call → tool_result → result)
   is pushed to Grafana Cloud through `mcp-grafana` as a tagged annotation, so
   the whole run is replayable in a dashboard.

Try it: `python demo_agentic_cinema.py` — no checkpoint, no API key, no
container. It runs the whole pipeline deterministically and prints the
timeline.

## How we built it

- **The planner** — a 324M-parameter transformer (24 layers, 768 embed), SFT'd
  on 20k planning examples (60% "hard" multi-step), ~3.5 GPU-minutes on a
  rented RTX 5090. It outputs only tool names — a decision that keeps the model
  small and the surface simple.
- **The harness** — ReAct loop that fills arguments, dispatches the 8 native
  tools, and verifies each result. Guardrails fix the model's systematic
  failure classes (superfluous grep, bash-as-write, missing final write).
- **The observability** — Grafana Cloud MCP server (`mcp-grafana`) launched
  automatically (pip console script → `uvx` → `npx`); each normalized event
  becomes a `create_annotation` call. MCP failure is never fatal to a run
  (silent fallback + counter).
- **The validation** — 921 passing tests, plus a fresh 120-task holdout with
  zero entity overlap with any training corpus.

## Challenges we ran into

- **Generalization vs memorization** — the first holdout was saturated and
  contaminated: the model had effectively memorized it, hiding a real
  regression. Building a fresh holdout (new entities, zero collision) is what
  actually exposed the old planner's weaknesses — and validated the new one.
- **Fixed tool vocabulary** — the planner can only emit 8 native tools, so
  Grafana had to be an observability layer, not a planable tool. That turned
  out to be the right design: the dashboard is the agent's scope.
- **Windows console encoding** — the timeline glyphs (→ ✓) crashed printing on
  a cp1252 console; the demo now forces UTF-8 output with a safe fallback.

## Accomplishments that we're proud of

- **99% plan accuracy** on 120 unseen tasks (fresh holdout, 0 regressions).
- **Statistically significant e2e impact** — p = 0.0139 sign test: the plan
  helps the executor on 27 tasks, hurts on 11, and the effect grows with plan
  length.
- **A 30-second demo with zero dependencies** that nonetheless uses the real
  324M model when the checkpoint is present.
- **921 tests passing** across the harness, the planner bridge, the guardrails,
  and the Grafana sink.

## What we learned

- Raw plan accuracy is the wrong production metric — model **plus guardrails**
  is what ships. A promotion on raw score alone had to be rolled back.
- Never trust a contaminated holdout; a fresh one changed the verdict.
- Observability isn't a bolt-on — when every tool call is a tagged annotation,
  an agent becomes auditable, replayable, and debuggable like any other system.

## What's next

- **Slot-filling** — extend the planner to also emit argument targets
  (file names, patterns), moving more of the harness work into the local model.
- **Everywhere** — the 324M planner already runs on CPU; port it to edge
  targets (mobile, embedded) so planning is free everywhere.
- **Bigger executors** — pair the plan with stronger open executors and measure
  the same A/B protocol.

## Built with

Python · PyTorch · Grafana Cloud · Model Context Protocol (mcp-grafana) ·
GitHub · Ollama (optional executor)

## Try it out

- GitHub: https://github.com/Rua987/nodus
- Demo video: [PLACEHOLDER: coller le lien YouTube après enregistrement —
  script + commandes dans `video_script_3min.md`]
- Gallery image: upload `gallery_timeline.png` (racine du repo) — timeline du
  run live réel (plan 324M v5 + exécution hermes3:8b + annotations Grafana).
  Raw après push: https://raw.githubusercontent.com/Rua987/nodus/main/gallery_timeline.png

---

### Quick copy checklist

- [ ] Paste each section into its Devpost field (section headings map 1:1).
- [ ] Upload `gallery_timeline.png` as the gallery image (1/3 slots).
- [ ] Add the demo-video link after recording (script: `video_script_3min.md`).
- [ ] Confirm the pitch ≤ 500 words if the form enforces a limit (~230 here).
- [ ] Under "Built with", select the actual Grafana Cloud / MCP tags if the
      form offers them.
