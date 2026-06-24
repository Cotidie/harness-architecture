---
type: plan
status: draft
created: 2026-06-25
source_plan: "[[01-harness-mvp-plan]]"
---

# Iteration Roadmap — Living Architecture Harness MVP

## Context

This roadmap slices the locked design in [`01-harness-mvp-plan.md`](../01-harness-mvp-plan.md)
into vertical, runnable iterations. The design is already decided (CodeGraph =
observed truth, architecture docs = intended truth, reconcile-before-coding loop), so we
re-slice it directly rather than re-deciding anything.

**Headline value:** every feature passes through reconcile → patch → scoped code → validate,
so dependency structure, domain model, and data contracts evolve on purpose, never silently.

**Confirmed sequencing decisions (from forks):**
- **Invocation surface = Claude Code subagents + one orchestrator skill.** Each agent is a
  `.claude/agents/<name>.md` custom subagent (dispatched by name, with `codegraph_explore`).
  **Revised (iter 1-2 feedback):** the original "no slash-command UX" decision is reversed in
  part. The loop has no user-facing trigger when the main agent hand-dispatches each subagent,
  so iteration 5 adds a single orchestrator skill `/harness-feature "<request>"` that chains
  survey -> architect -> [approve] -> builder -> inspector. No per-agent skills (kept minimal).
- **Newly added agents are not dispatchable by name until `/reload-plugins`.** During the
  session that creates an agent def, dispatch its prompt inline via a generic subagent; the
  named type works after a reload. The iteration 7 install flow includes this reload step.
- **Single source per agent = `.claude/agents/<name>.md`.** The separate `/agent-prompts`
  folder from the design is dropped: each agent def is self-contained (frontmatter + prompt
  body in one file), so there is no duplicate prompt copy to drift. Tool portability is not an
  MVP requirement, and iteration 7 ships a Claude Code plugin anyway.
- **The four agents = Surveyor, Architect, Builder, Inspector** (was Snapshot, Patch, Scoped
  Coding, Validation). Output nouns keep their names (the "patch" file, the validation report).
- **Dogfood feature = a `boundaries.yaml` linter** — a tool that reads `boundaries.yaml` and
  reports any import violating a `must_not_depend_on` rule. Self-referential: it exercises the
  harness's own architecture rules. This is the feature driven through iterations 2–3.
- **Test target = this repo (self-host).** `harness-architecture` already has `.codegraph/`
  indexed, so every iteration is dogfooded here against real feature requests.
- **Output = `docs/iteration/`** (this file).

**Why this order, not the design's section order:** the design lists artifacts and agents
top-down (docs → patch → code → validate). That is architecture order, not risk order. The
riskiest claim is *"a narrow CodeGraph query + intended docs yields a correct reconciliation
+ useful patch without repo-wide exploration."* We validate the doc-generation feasibility
first (cheapest, it gates everything), then the reconciliation core, then scoped coding, and
only then wire the full automated loop. Each slice is something you run by hand and judge.

**The loop:** after each iteration you run it yourself on this repo and give feedback. That
feedback revises the iterations not yet detailed below — do **not** treat iterations 4+ as
final. When we return to detail iteration N+1, we fold in what iteration N taught us.

## Overview

| # | Iteration | User-facing slice |
|---|-----------|-------------------|
| 1 | Surveyor bootstrap | Run one subagent → get compact intended-architecture docs (`architecture.md`, `boundaries.yaml`, `domain-model.md`, `data-contracts.md`, `current.mmd`) generated from this repo via CodeGraph. |
| 2 | Reconcile + patch | Hand it a real feature request → subagent does 1 targeted CodeGraph query, classifies drift, writes an approvable architecture patch. |
| 3 | Scoped coding | Approve a patch → subagent implements *only* it, touching only allowed files, no hidden architecture changes. |
| 4 | Validation gate (light) | After coding, subagent re-checks changed symbols vs the patch and emits ACCEPT / REJECT decision. |
| 5 | Orchestrator skill + state (light) | `/harness-feature "<request>"` chains the agents with a conditional Surveyor step-0, the approval gate, and partial-entry args; `state.yaml` + docs update on accept; code + artifacts commit together. |
| 6 | Budget hardening (light) | Token-budget enforcement + forbidden-behavior guards (cadence triggers moved into iter5). |
| 7 | Packaging & install (light) | `/plugin install` the harness into any repo, then one `harness-init` + survey to bootstrap. |

---

## Iteration 1 — Surveyor bootstrap

- **Goal:** Prove a subagent + CodeGraph can produce *compact, useful* intended-architecture
  docs for this repo within budget — without dumping the whole repo. This gates every later
  slice (reconciliation needs intended docs to compare against).
- **User-facing value:** You run one subagent and get a populated `/.architecture` folder that
  describes this repo's module map, allowed/forbidden dependencies, domain classes, and
  contracts compactly enough to read in one sitting.
- **Features introduced:**
  - `.claude/agents/surveyor.md` (Surveyor as a first-class, self-contained custom subagent).
  - Surveyor dispatch by name: `Agent(subagent_type: 'surveyor')`, with
    `codegraph_explore` available; budget = 1–2 targeted queries.
  - `/.architecture/` artifacts seeded from real CodeGraph output.
- **Deliverables:**
  - `.claude/agents/surveyor.md`
  - `.architecture/.architecture.md`, `.architecture/boundaries.yaml`,
    `.architecture/domain-model.md`, `.architecture/data-contracts.md`,
    `.architecture/graph-notes.md`, `.architecture/diagrams/current.mmd`
  - `.architecture/state.yaml` initialized (`last_codegraph_query_scope`, commit sha).
- **Testable conditions:**
  - All six artifacts exist and are non-empty.
  - `boundaries.yaml` names this repo's actual modules (not the design's generic
    domain/contracts/adapters template copied verbatim).
  - Survey run used ≤ 2 CodeGraph queries (check the subagent's reported calls).
  - No artifact contains pasted long source bodies or a full file-by-file index.
  - `current.mmd` is high-level (boundaries), not one node per symbol.
- **User test flow:**
  1. Dispatch the Surveyor (`Agent(subagent_type: 'surveyor')`) against this repo.
  2. Read the generated `architecture.md` + `boundaries.yaml`.
  3. Judge: do these match how *you* think the repo is intended to be structured? Are they
     compact? Did it avoid repo-wide reads?
- **Feedback to collect:**
  - Are the docs accurate, or did CodeGraph-derived structure miss/invent boundaries?
  - Right altitude — too coarse, too detailed?
  - Did 1–2 queries suffice, or did the agent want more (signals budget is too tight)?
  - Does the generic `boundaries.yaml` template fit this repo, or does the module taxonomy
    need to change? (This directly shapes iteration 2's reconciliation.)
- **Risks / open decisions:**
  - Packaging decided: first-class `.claude/agents/*.md` custom subagents (dispatch by name).
  - **OPEN:** does the Surveyor definition's tool allowlist need `codegraph_explore`
    explicitly granted, vs inherited? Resolve on first dispatch.

---

## Iteration 2 — Reconcile + patch

- **Goal:** Validate the core, riskiest claim: a single targeted CodeGraph query plus the
  intended docs lets the agent classify drift correctly and write an architecture patch worth
  approving — before any code is written.
- **User-facing value:** You give a one-line feature request; you get back a reconciliation
  decision (ALIGNED / DOC_DRIFT_ACCEPTED / CODE_DRIFT_HARMFUL / UNCLEAR_DRIFT) and a compact,
  reviewable patch file scoping exactly what may change.
- **Features introduced:**
  - `.claude/agents/architect.md` (Architect agent def) implementing the design's
    11-section patch + the reconciliation gate.
  - Patch artifacts written to `.architecture/patches/YYYY-MM-DD-<feature>.md` using the
    design's §8 template, including the approval checkbox.
  - The "Relevant Architecture Context" compact summary format (design §3) as the agent's
    output context, not raw CodeGraph dumps.
- **Deliverables:**
  - `.claude/agents/architect.md`
  - At least one real patch, e.g. `.architecture/patches/2026-06-25-boundaries-linter.md`,
    produced from a genuine feature request against this repo.
- **Testable conditions:**
  - Patch contains all 11 design sections (observed, intended, reconciliation decision,
    affected modules, dependency changes, domain changes, contract changes, allowed files,
    tests required, risks, approval checkbox).
  - Reconciliation decision is one of the four labels and is *justified* by the observed-vs-
    intended comparison, not asserted.
  - Patch used exactly 1 targeted CodeGraph query (design budget) and named a narrow scope.
  - New boundary data proposes a contract class; new business behavior proposes a domain
    class/method (not a module-level function).
  - "Files allowed to edit" is a concrete, bounded list.
- **User test flow:**
  1. Pick a real small feature for this repo (e.g. "add a linter that checks code against
     `boundaries.yaml`").
  2. Dispatch the patch subagent with the request + the iteration-1 docs.
  3. Read the patch: is the drift call right? Is the scope correct and minimal? Would you
     approve it as-is, edit it, or reject it?
- **Feedback to collect:**
  - Patch quality: is it specific enough to constrain coding, or hand-wavy?
  - Did the drift classification match your own judgment on a case where code already drifted?
  - Was one query enough to reconcile, or did it guess? (Tightens iteration-3 trust.)
  - Template friction: which of the 11 sections are noise for small changes vs essential?
    (May justify a "small change" lite patch later.)
- **Applied (iter 1-2 feedback), now baked into `architect.md`:**
  - **Drift-scoping rule:** the Architect classifies drift *for the feature's affected area
    only*, and notes unrelated observed drift separately without letting it change the
    feature's label. (Observed working in iter 2; codified so it stays.)
  - **Lite-patch path:** for small changes the Architect may collapse the 11-section template
    (skip empty Module/Contract/Domain sections) while always keeping reconciliation decision,
    files-allowed, tests-required, and the approval checkbox.
- **Risks / open decisions:**
  - **OPEN:** how human approval is recorded (checkbox edit in-file vs a separate gate). MVP =
    you edit the checkbox. Revisit when iteration 5 adds the orchestrator skill.

---

## Iteration 3 — Scoped coding

- **Goal:** Prove an approved patch actually *constrains* implementation — the coding subagent
  edits only allowed files, adds the required tests, and makes no hidden architecture changes.
- **User-facing value:** You approve a patch and get a working code change that stays inside
  the patch's declared scope, with a summary of exactly what it touched.
- **Features introduced:**
  - `.claude/agents/builder.md` (Builder agent def) with the design's hard
    rules: edit only approved files, no raw dict/list across boundaries, no duplicate
    contracts, no module-level business functions, no CodeGraph call unless patch is ambiguous.
  - Coding-agent output summary (files changed, domain/contract changes, deps, tests,
    assumptions).
  - The "stop and request patch revision" path when the patch is insufficient.
- **Deliverables:**
  - `.claude/agents/builder.md`
  - The implemented feature from iteration 2's patch (code + tests) on this repo.
  - A coding summary block recorded with the patch.
- **Testable conditions:**
  - `git diff` touches only files listed in the patch's "Files allowed to edit".
  - Required tests from the patch exist and pass.
  - No new boundary-crossing raw dict/list; new behavior lives in a domain class/method.
  - If the patch was ambiguous, the agent stopped and asked rather than improvising.
- **User test flow:**
  1. Approve the iteration-2 patch (tick the checkbox).
  2. Dispatch the coding subagent with the approved patch + compact context.
  3. Run the tests; inspect `git diff` against the allowed-files list.
  4. Judge: did it stay in scope? Any sneaky out-of-patch edits?
- **Feedback to collect:**
  - Scope discipline: did it color inside the lines, or drift?
  - Were patch instructions sufficient to code from, or did it need to re-query / guess?
  - Quality of the change vs a normal un-harnessed implementation — worth the overhead?
- **Risks / open decisions:**
  - **OPEN:** enforcement vs trust — is "edit only allowed files" a prompt instruction only,
    or do we add a mechanical guard (e.g. a diff check)? MVP relies on the prompt + your diff
    inspection; iteration 4's validation gate is where mechanical checks land.

---

## Iteration 4 — Validation gate *(light — re-planned from feedback)*

- **Goal:** Close the loop's back end: after coding, mechanically check the diff against the
  patch and intended architecture.
- **User-facing value:** You get an ACCEPT / NEEDS REVISION / REJECT decision (with reason)
  on a change before you trust it — catching forbidden edges, new cycles, raw boundary
  payloads, or out-of-patch interface drift.
- **Mechanical gate (decided from iter 2):** the Inspector reuses the Builder's self-check, run
  the boundaries-linter on `src/` against `.architecture/boundaries.yaml` and require zero
  violations. The iteration-2 patch already invented this check; promote it to the standing
  validation gate so "no forbidden edge" is verified by tooling, not just by reading the diff.
- **Prompt caveat (from iter 1-2):** the Inspector (and Surveyor) must treat CodeGraph's
  `tests:` field as *callers*, not test coverage; do not report coverage from it.
- Detail otherwise deferred. Will fold in iteration 3's findings on whether prompt-only scope
  discipline held or needs more mechanical guards.

## Iteration 5 — Orchestrator skill + state *(light — re-planned from feedback)*

- **Goal:** Give the harness a single user-facing trigger. A `/harness-feature "<request>"`
  skill chains survey -> architect -> [human approval] -> builder -> inspector, updating
  `state.yaml` and docs on accept and committing code + artifacts together.
- **User-facing value:** You run one command with a feature request and the harness drives the
  whole loop, pausing only at the approval gate. The loop no longer depends on the main agent
  hand-dispatching each subagent.
- **Why now in scope (reversal):** iterations 1-2 showed the agents work but the loop has no
  trigger surface. A single orchestrator skill is the minimal fix; per-agent skills are
  intentionally NOT added (kept minimal).
- **Likely shape:**
  ```
  /harness-feature "<request>"
    step 0 (conditional): if docs are stale by rule -> Surveyor first, log the reason
    step 1: Architect -> patch
    step 2: human approval gate
    step 3: Builder
    step 4: Inspector (self-check)
    on accept: update state.yaml + docs, commit code + artifacts together
  ```
- **Conditional Surveyor (step 0).** The Surveyor is not a fixed first step; the orchestrator
  decides whether to re-survey by a **concrete, logged rule**, not model intuition:
  - re-survey if commits since `state.yaml.last_reconciled_commit` exceed a threshold (design
    §7 cadence, around 5 to 10), or if the Architect signals broad `UNCLEAR_DRIFT` beyond the
    feature's area, or if `--resurvey` is passed;
  - default is to **skip** (re-surveying every feature blows the token budget and contradicts §7);
  - when it does run, announce it and record why in `state.yaml` (for example "re-surveyed: 12
    commits since last"). A re-survey rewrites the whole intended docs, so treat it as a
    reviewable doc change, not a silent refresh.
- **Partial entry via args (not per-agent skills):** `--patch-only` (stop after the Architect),
  `--from-patch <file>` (skip to Builder for an already-approved patch), `--inspect-only`,
  `--resurvey` / `--no-survey`. This covers the non-linear cases with one skill.
- **Per-agent skills (`/architect`, `/build`, `/inspect`) = future work, decided at iteration 7.**
  For self-host the agents are dispatched as named subagents; whether external users need typed
  per-agent commands is a packaging-time UX call, gated on feedback. Not built in the MVP loop.
- Detail deferred. Depends on how much hand-holding iterations 2-4 needed between steps.

## Iteration 6 — Budget hardening *(light — re-planned from feedback)*

- **Goal:** Enforce the token budget (design §3) across the loop and tighten the
  forbidden-behavior guards (no whole-repo dumps, no re-querying, no raw payloads).
- **User-facing value:** The harness stays cheap over many features instead of degrading into
  repo-wide exploration.
- **Note:** survey-on-cadence and drift-trend re-survey triggers moved into iteration 5 (the
  orchestrator's conditional step-0 staleness rule), so they are not separate work here.
- Detail deferred. Sequenced before packaging because the loop must be proven cheap before
  it is worth shipping to others.

## Iteration 7 — Packaging & install (Claude Code plugin) *(light — re-planned from feedback)*

- **Goal:** Turn the proven, repo-local harness into something a user installs into any repo,
  not files they hand-copy.
- **User-facing value:** A user runs `/plugin install <harness>`, then a one-shot
  `harness-init`, and their repo has the four agents wired and intended-architecture docs
  bootstrapped, ready for the feature loop.
- **Packaging decision (locked): Claude Code plugin.** The system is entirely Claude Code
  artifacts (self-contained agent defs + a setup skill + the `/.architecture` scaffold), so it
  ships as a plugin in a marketplace rather than a binary or template repo.
- **Likely shape (re-planned from what iters 1–5 prove must ship):**
  - Plugin bundles `.claude/agents/*` (surveyor, architect, builder, inspector), the
    `/harness-feature` orchestrator skill (iter 5), and a `harness-init` setup skill.
  - `harness-init` scaffolds `/.architecture` into the target repo, checks CodeGraph is present
    (hard prereq, installed separately), and runs `surveyor` once to seed intended docs +
    `state.yaml`.
  - Target install flow: `codegraph init` → `/plugin install` → **reload so the agents register
    by name** → `harness-init` → run surveyor once → feature loop ready.
- **Open / depends-on:** which files actually need to ship (decided by iters 1–5), and whether
  CodeGraph install can be checked/guided by the setup skill or stays fully manual.
- Detail deferred. Sequenced last: packaging is only worth doing once the loop is proven cheap
  and useful (iters 1–6).
