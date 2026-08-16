# Nodus — 3-minute video narration script

**Format** : screen recording + voice-over. ~443 spoken words ≈ 3 min at
140 wpm. Timeline is a target; each segment is independent so you can trim
any segment without breaking the others.

**How to record the demo cleanly** :
```bash
# UTF-8 terminal so the timeline glyphs (→ ✓ ∘ ↳ ●) render correctly
# (Git Bash / Windows Terminal / VS Code all work; cmd.exe: chcp 65001)
python demo_agentic_cinema.py                # the "with plan" timeline
python demo_agentic_cinema.py --contrast     # plan vs no-plan side by side
python demo_agentic_cinema.py --list-tasks   # for the intro card
```
If `checkpoints/checkpoint_sft_plan_v5.pt` is present the demo uses the
**real 324M planner** (plan source: `[linus]`); otherwise the gold plan
(`[demo-gold]`) — visually identical, deterministic, safe for recording.

---

## Segment 1 — 0:00 → 0:25 · "The expensive habit"

**Visual** : a terminal scrolls random tool calls while a "$ COST" meter climbs;
the screen glitches and cuts to the title card **NODUS — a tiny local planner**.

**Narration** (≈ 70 words):
> Every agentic system pays the same hidden tax: before it can do anything, a
> frontier model burns tokens just to plan. On simple tasks, planning can cost
> more than the work itself — and every step leaves your code in someone
> else's cloud. What if planning were free? What if a model small enough to
> run on a laptop CPU could do it, instantly and privately?

---

## Segment 2 — 0:25 → 0:55 · "The idea"

**Visual** : split screen. Left — the task
`Read src/utils.py, then save a config stub, then verify.` Right — a model card
(324M params · 24 layers · 768 embed · vocab 100k) resolving to the plan
`["read_file", "write_file", "bash"]`.

**Narration** (≈ 72 words):
> This is Nodus — a 324-million-parameter transformer, trained on one single
> job: turn a natural-language task into an ordered list of tool names. No
> arguments. No replanning. The harness fills the details, executes, and
> verifies. Because the planner is small and local, planning costs nothing,
> runs on CPU, and your code never leaves the machine. The big model's only
> job is what it's actually good at: executing.

---

## Segment 3 — 0:55 → 1:45 · "The demo"

**Visual** : live record `python demo_agentic_cinema.py`. Pause ~1s per line as
the timeline appears; hover the cursor over the plan line, then the ✓ results.

**Narration** (≈ 102 words):
> Here's the whole pipeline, end to end. A task arrives. The planner answers
> in tool names: read, write, bash. The harness takes over — fills the
> arguments, runs each step, verifies the result. Read the utility file.
> Create the config stub. Verify it exists. Every one of these events streams
> to Grafana Cloud as a live annotation — the dashboard becomes the agent's
> scope. Now watch what happens without a plan: the executor ad-libs three
> bash commands and creates nothing. With a plan, the same task completes in
> three steps. That gap is the product.

---

## Segment 4 — 1:45 → 2:20 · "The evidence"

**Visual** : metric cards. "119 / 120 = 99% · 0 regressions · 120 unseen tasks"
then the sign-test table — plan better 27 · plan worse 11 · p = 0.0139.

**Narration** (≈ 84 words):
> Is this real? On a fresh holdout of one hundred and twenty tasks the model
> had never seen, Nodus plans 119 correctly — ninety-nine percent, with zero
> regressions. And the planning measurably helps: across two hundred runs, it
> improved the executor on twenty-seven tasks and hurt it on only eleven — a
> sign test with p equals zero point zero one three nine, statistically
> significant. The effect grows with plan length, exactly where agents need
> help the most.

---

## Segment 5 — 2:20 → 2:45 · "Grafana Cloud"

**Visual** : the Grafana dashboard; annotations pop in one by one, tagged
`nodus:task`, `nodus:plan`, `nodus:tool_call`, `nodus:tool_result`,
`nodus:result`.

**Narration** (≈ 62 words):
> Nodus activates Grafana Cloud through the official MCP server. Every run
> streams task, plan, tool calls, and results as tagged annotations — so you
> can replay any agent session, correlate it with system metrics, and audit
> exactly what the agent did, and why. That's the observability layer running
> live in this dashboard, powered by our Grafana Cloud integration.

---

## Segment 6 — 2:45 → 3:00 · "Close"

**Visual** : repo card `github.com/Rua987/nodus`, the README headline
("119/120 · 99%"), a test run ending `910 passed`.

**Narration** (≈ 53 words):
> Nodus is open source. Nine hundred and ten tests passing, and a checkpoint
> you can drop in and run on a laptop CPU. If you want your agent to plan for
> free — and to watch every step it takes — clone the repo, and let it think.
> Thank you.

---

## Shot list (quick reference)

| Time | Shot | Audio |
|---|---|---|
| 0:00 | agent flails + cost meter → title card | Segment 1 |
| 0:25 | split screen: task → model card → plan | Segment 2 |
| 0:55 | live `demo_agentic_cinema.py` timeline | Segment 3 |
| 1:45 | metric cards: 99% then p=0.0139 table | Segment 4 |
| 2:20 | Grafana dashboard annotations streaming | Segment 5 |
| 2:45 | repo card + `910 passed` | Segment 6 |

**Production notes**
- Record at 1080p, 30 fps; keep a 1–2 s hold on every visual before narration
  starts so cuts don't feel rushed.
- The demo glyphs need a UTF-8-capable terminal; if they ever render as `?`
  on your setup, the output is still fully readable — don't re-record for that.
- Optional cut: if the segment 3 contrast clip makes the video run long, drop
  the "no plan" part and keep only the with-plan timeline.
