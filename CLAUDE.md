# LINUS — contexte Claude Desktop

Projet agent de code : `linus_nanochat/`. Bac à sable utilisateur : `C:\Users\admin\linus_sandbox\`.

## Commande CLI (PowerShell)

### One-shot (tâche unique)

```powershell
linus "ta tache ici"
```

### Vibe coding (session Claude Code — multi-tours, outils en direct)

```powershell
linus-vibe
# ou
cd C:\Users\admin\linus_sandbox
python C:\Users\admin\.claude-worktrees\templates\hopeful-banach\linus_nanochat\linus_vibe.py
```

Ajouter au profil PowerShell (`$PROFILE`) :

```powershell
function linus-vibe {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$ExtraArgs)
    $dir = "C:\Users\admin\.claude-worktrees\templates\hopeful-banach\linus_nanochat"
    python "$dir\linus_vibe.py" --cwd "$PWD" @ExtraArgs
}
```

| Mode | Commande | Comportement |
|------|----------|--------------|
| **one-shot** | `linus "fix le test"` | 1 tâche → fin (comme aujourd'hui) |
| **vibe** | `linus-vibe` puis `linus> ...` | session interactive, stream outils, mémoire, `/exit` |

Fonction `linus` (one-shot) définie dans le profil PowerShell — pointe vers :

```
C:\Users\admin\.claude-worktrees\templates\hopeful-banach\linus_nanochat\linus_agent.py
```

Modèle par défaut : `openrouter/z-ai/glm-5.2` (GLM 5.2 Z.ai via OpenRouter, profil PowerShell).

### Plan local LINUS (économise 1 appel OpenRouter)

```powershell
linus "lis X puis edite Y ..." --plan --plan-source linus -v
# cloud = defaut ; off = pas de plan
# --no-plan-slotfill : desactive le pre-remplissage cibles par l'executeur
```

Checkpoint : `checkpoints/checkpoint_sft_plan_v5.pt` (v5 promu 2026-08-15 après preuve holdout frais ; override : `$env:LINUS_PLAN_CKPT`).
Device planificateur : `$env:LINUS_PLAN_DEVICE = "cpu"|"cuda"|"auto"` (defaut `auto` = GPU si dispo).
**Branche CPU mise de cote (2026-07-25)** : essais LINUS-CPU + Ollama ont **rame deux fois**
(9B puis 2b) — RAM (~2.5 Go fp32 LINUS) + executeur. Flux courant = comme avant (auto/GPU).
Option `cpu` reste dans le code pour plus tard, pas le defaut.
**Garde-fou Ollama (2026-07-25)** : `real_usage_p0_harness.py` appelle
`linus_ollama_guard.ensure_ollama_safe_for_harness` — refuse si `/api/ps` a un residu
(ex. abliterated:9b), unload `keep_alive=0`, plafond VRAM optionnel
(`LINUS_OLLAMA_MAX_VRAM_MIB`, defaut 1500). `_chat` honore `LINUS_OLLAMA_KEEP_ALIVE`
(harness met `0` par defaut). Ne pas relancer un harness si Desktop a un chat 9B ouvert.
Loi : `HANDOFF_PLAN_BRIDGE.md` — LINUS = noms d'outils ; slot-fill (defaut ON)
demande a l'executeur local (qwen) la cible primaire une etape a la fois ;
l'executeur remplit le reste des args.

Pour GPT-OSS gratuit :
```powershell
linus "tache" -Model "openrouter/openai/gpt-oss-120b:free"
```

### Changer de modèle

**1. Par commande (PowerShell, après maj profil 2026-06-14) :**

```powershell
linus "ma tache" -Model "openrouter/openai/gpt-oss-20b:free"
```

**2. Défaut permanent :** éditer `Microsoft.PowerShell_profile.ps1` → paramètre `$Model` dans `function linus`.

**3. Direct (sans fonction linus) :**

```powershell
python C:\Users\admin\.claude-worktrees\templates\hopeful-banach\linus_nanochat\linus_agent.py "tache" --cwd "$PWD" -m "openrouter/openai/gpt-oss-120b:free" -v
```

### Slugs OpenRouter (préfixe `openrouter/` obligatoire)

| Modèle | Slug LINUS | Usage |
|--------|------------|-------|
| GPT-OSS 120B free | `openrouter/openai/gpt-oss-120b:free` | Code / agent (défaut) |
| GPT-OSS 20B free | `openrouter/openai/gpt-oss-20b:free` | Plus rapide, fallback si 429 |
| GLM 5.2 Z.ai | `openrouter/z-ai/glm-5.2` | Payant, agentic coding, 1M ctx |
| DeepSeek v4 Pro | `openrouter/deepseek/deepseek-v4-pro` | Ancien défaut cloud |

Clé API : fichier `.openrouter_api_key` dans `linus_nanochat/` (ou variable `OPENROUTER_API_KEY`).

## Pont modèle local (A) → harnais (B)

Le cerveau **local** (~247M, seq 512) n'est **pas** branché. Loi écrite :

`c:\Users\admin\.claude-worktrees\autoresearch_linus\.claude\worktrees\hopeful-archimedes\HANDOFF_A2B_BRIDGE.md`

- **Mini-prompt** + grammaire JSON `--text-tools` déjà dans le harnais (`{"tool_call": ...}`) — **pas** special tokens
- Branchement seulement si **≥90%** exact tool-calls held-out (n≥100, greedy, single-call, **sans** voir les tool results)
- **Visu = P1** ; corpus = uniquement après **Go corpus** (loi corrigée 2026-07-21)

Recharger le profil après edit : `. $PROFILE`

## Fix Windows shell (2026-06-14) — IMPORTANT

**Problème :** les LLMs envoient `cd X && python script.py`. Sous **PowerShell 5.x** (Windows par défaut), `&&` est une **erreur de syntaxe** → exit 1, même si le Python est bon. Cela gaspillait ~64 % des rounds agent.

**Correctif (code) :** `linus_tools.py` → `_rewrite_windows_powershell()` appelé dans `tool_bash` :

| Entrée LLM (bash/CMD) | Réécriture auto |
|----------------------|-----------------|
| `cd /d C:\path && python x.py` | `Set-Location C:\path; python C:\path\x.py` |
| `cd CWD && python x.py` (cwd = tâche) | `python C:\abs\x.py` |
| `a \|\| b` | `a; if (-not $?) { b }` |

**Règles pour Claude Desktop quand tu modifies LINUS ou donnes des tâches :**

1. Ne pas réintroduire de doc qui recommande `cd && python` sur Windows.
2. Préférer : `python C:\chemin\absolu\script.py` (cwd déjà injecté via `--cwd`).
3. Shell réel = `powershell -NonInteractive -Command` (pas bash).
4. Tests : `pytest tests/test_linus_tools.py -k rewrite` après changement shell.

## Fichiers clés

| Fichier | Rôle |
|---------|------|
| `linus_agent.py` | Boucle ReAct, system prompt |
| `linus_tools.py` | Outils (bash, read, write, grep…) + rewrite Windows + verrou `mini_pytest.py` |
| `linus_policy.py` | Budget read / force-write |
| `linus_sandbox/` | Exercices agent (LRU, KV, parser, rate limiter, mini_pytest) |

## Sandbox — modules de référence

```
linus_sandbox/
  # structures de données / algo
  lru_cache.py, trie.py, expr_eval.py, json_patch.py
  # systèmes / concurrence
  scheduler.py, rate_limiter.py, kv_store.py, undo_stack.py, event_bus.py
  # utilitaires
  find_duplicates.py, primes.py, fib.py, mini_pytest.py
  # tests mini_pytest (1 fail volontaire: test_sample)
  test_json_patch.py, test_event_bus.py, test_kv_store.py, test_scheduler.py, test_trie.py, test_undo_stack.py, test_sample.py
```

Benchmark LINUS 2026-06-14 : scheduler/undo_stack en **3 rounds** ; trie **14 rounds** (1 bug DFS) ; event_bus fonctionnel mais dérive VERIFY ; json_patch en 2 phases (**4 + 15 rounds**) avec correction d'un vrai bug (`add /list/-`).

Garde-fous P0 appliqués :
- `extract_expected_files()` ignore les fichiers seulement exécutés par `python ...`.
- `run_agent()` ne recrée pas un fichier prouvé existant par `read_file`.
- `mini_pytest.py` est protégé contre `write_file/edit_file` sauf `LINUS_ALLOW_REFERENCE_OVERWRITE=1`.

Leçons agent : `.linus_lessons.md` (racine linus_nanochat).

Lancer les tests sandbox :

```powershell
python C:\Users\admin\linus_sandbox\mini_pytest.py C:\Users\admin\linus_sandbox
# attendu : N passed, 1 failed (test_sample.test_deliberate_failure)
```

## Modèles Ollama locaux (autre workspace)

Benchmark séparé sur RTX 2070 8 Go — voir `QWen3.5-abliterred-2026` :

- **Code red team :** `dolphin3-karpathy-redteam`
- **Tools + uncensored :** `qwen3.5-abliterated:9b`
- **Eviter pour code ops :** `llama3-ceh` (vocabulaire cyber OK, commandes souvent fausses)

LINUS cloud (DeepSeek v4 Pro) reste au-dessus pour tâches multi-fichiers avec boucle test/fix.
