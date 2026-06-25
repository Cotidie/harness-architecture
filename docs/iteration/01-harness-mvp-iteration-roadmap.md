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
  named type works after a reload. The iteration 10 install flow includes this reload step.
- **Single source per agent = `.claude/agents/<name>.md`.** The separate `/agent-prompts`
  folder from the design is dropped: each agent def is self-contained (frontmatter + prompt
  body in one file), so there is no duplicate prompt copy to drift. Tool portability is not an
  MVP requirement, and iteration 10 ships a Claude Code plugin anyway.
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

**Generalization is deferred on purpose (added 2026-06-25 from feedback):** iterations 1-6
prove and harden the loop on this one Python repo (self-host). The harness is meant for any
stack (Flask, React, Spring), but two things are currently specialized to the dogfood project:
the agent prompts bake in this repo's `domain/contracts/application/adapters` vocabulary, and
the enforcement linter is Python-`ast`-only. The fix is layered by cost. The *intended-
architecture model* is already framework-agnostic in data (`boundaries.yaml` = named modules +
path globs + may/must_not_depend_on); only the prompt prose and the scanner are bound. So
**iteration 7** structures the intended layer (contracts and domain-model as data, so
reconciliation becomes a mechanical diff), **iteration 8** makes the model framework-aware (a
Surveyor-written convention profile replaces the hardcoded ontology; the Architect emits seam
signatures in the project's idiom), and **iteration 9** makes *enforcement* polyglot. These are
sequenced after the loop is proven and before packaging — shipping a Python-only-assuming
harness to a React or Spring repo would mislead. Iterations 1-3 are done and stay intact; this
generalization lands only in 4+ slices.

## Overview

| # | Iteration | User-facing slice |
|---|-----------|-------------------|
| 1 | Surveyor bootstrap | Run one subagent → get compact intended-architecture docs (`architecture.md`, `boundaries.yaml`, `domain-model.md`, `data-contracts.md`, `current.mmd`) generated from this repo via CodeGraph. |
| 2 | Reconcile + patch | Hand it a real feature request → subagent does 1 targeted CodeGraph query, classifies drift, writes an approvable architecture patch. |
| 3 | Scoped coding | Approve a patch → subagent implements *only* it, touching only allowed files, no hidden architecture changes. |
| 4 | Validation gate + signature gate (light) | After coding, subagent re-checks the diff vs the patch on two gates: boundary-edge linter (zero violations) AND implemented public signatures match the patch's declared seam signatures. Emits ACCEPT / NEEDS REVISION / REJECT. |
| 5 | Orchestrator skill + state (light) | `/harness-feature "<request>"` chains the agents with a conditional Surveyor step-0, the approval gate, and partial-entry args; `state.yaml` + docs update on accept; code + artifacts commit together. |
| 6 | Budget hardening (light) | Token-budget enforcement + forbidden-behavior guards (cadence triggers moved into iter5). |
| 7 | Structured intended-architecture layer (light) | Convert the intended layer from prose to structured data (`contracts.yaml`, `domain-model.yaml` alongside `boundaries.yaml`); reconciliation and gate 2 become a mechanical diff of structured-intended vs CodeGraph-observed, not prose judgment. |
| 8 | Framework-aware architecture model (light) | Surveyor detects the project's framework and writes a convention profile; agent prompts stop assuming one fixed layer ontology; Architect emits seam signatures in the project's idiom. Harness fits Flask / React / Spring, not only this Python repo. |
| 9 | Polyglot enforcement (light) | Boundary checking works across languages (TS / Java / ...) by leaning on CodeGraph edges or a multi-language scanner, so the validation gate can actually run on a non-Python repo. |
| 10 | Packaging & install (light) | `/plugin install` the harness into any repo, then one `harness-init` + survey to bootstrap. |

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

## Iteration 4 — Validation gate + signature gate *(light — re-planned from feedback)*

- **Goal:** Close the loop's back end: after coding, mechanically check the diff against the
  patch and intended architecture on **two** gates — boundary edges and seam signatures.
- **User-facing value:** You get an ACCEPT / NEEDS REVISION / REJECT decision (with reason)
  on a change before you trust it — catching forbidden edges, new cycles, raw boundary
  payloads, AND out-of-patch interface drift (a public signature that does not match what the
  patch declared).
- **Gate 1 — boundary edges (decided from iter 2):** the Inspector reuses the Builder's
  self-check, run the boundaries-linter on `src/` against `.architecture/boundaries.yaml` and
  require zero violations. The iteration-2 patch already invented this check; promote it to the
  standing validation gate so "no forbidden edge" is verified by tooling, not just by reading
  the diff.
- **Gate 2 — seam signatures (new, from 2026-06-25 feedback):** the Inspector checks that the
  implemented public signatures match the patch's declared seam signatures. This requires a
  small **prerequisite enhancement to the Architect** (built in iter 2): patch sections 7-8
  (domain / contract changes) must emit *actual signatures* — contract field names + types and
  the public method signatures of the domain/application entry points the feature touches — not
  prose. Scope is the **seam only**: new/changed contracts and public entry points, never
  private helpers or bodies (the lite-patch path stays signature-free). Signatures here are
  emitted in this repo's Python idiom; iteration 8 generalizes the idiom per framework profile.
- **Prompt caveat (from iter 1-2):** the Inspector (and Surveyor) must treat CodeGraph's
  `tests:` field as *callers*, not test coverage; do not report coverage from it.
- **Testable conditions (sketch):** a diff that adds a forbidden edge → REJECT on gate 1; a
  diff whose public signature diverges from the patch (renamed method, changed contract field
  type) → NEEDS REVISION on gate 2; an in-scope diff matching both → ACCEPT.
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
- **Per-agent skills (`/architect`, `/build`, `/inspect`) = future work, decided at iteration 10.**
  For self-host the agents are dispatched as named subagents; whether external users need typed
  per-agent commands is a packaging-time UX call, gated on feedback. Not built in the MVP loop.

- **Trust + governance requirements (from iter-4 user-test, 2026-06-25).** Iteration 4 proved
  the agents work but exposed that the *controls* are honor-system. The orchestrator is where
  they get teeth. These are requirements for this iteration, not optional polish:
  - **Approval must be unforgeable by the agent.** Today "approval" is an agent editing
    `- [ ] Approved` to `- [x]` in the patch; in iter 4 the agent ticked its own patch. For a
    "no silent architecture change" system that is the load-bearing control with no teeth. The
    orchestrator must take approval from an action the agent cannot perform: a hard pause for
    real human input, a human-signed git trailer, or a separate approval token the agent cannot
    write. The agent must never be able to self-approve a patch.
  - **The orchestrator runs the mechanical gates itself; it does not trust the agent's
    self-report.** Gate 1 (run tests, run the linter self-check, diff-vs-allowed-files scope) is
    deterministic and must be executed by the orchestrator, not reported by the Inspector. Only
    the *judgment* part (gate-2 reconciliation, drift labeling) is delegated to the Inspector
    agent. This is the "who verifies the Inspector" gap: a deterministic check should not depend
    on an LLM saying it ran.
  - **REJECT / NEEDS PATCH REVISION must define what happens next.** The Inspector report must be
    machine-actionable (which agent to re-invoke, what to change), and the orchestrator caps the
    revise loop with a **max-iteration** count so it cannot ping-pong or dead-end. Spell out the
    REJECT -> Architect re-scope -> re-approve -> Builder -> Inspector cycle and its exit.
  - **CodeGraph freshness gate before any agent query.** Each agent gets one query; the
    orchestrator must run `codegraph sync` and confirm the index reflects the latest writes
    before dispatching, so reconciliation does not read stale dependency edges (verbatim source
    is current, but edges lag ~1s).
  - **Grounded Architect signatures (gate-2 baseline).** Gate 2 only trusts the patch's declared
    seam signatures. The Architect must derive those from CodeGraph (current signatures) and diff
    against its proposal, so the declared seams are grounded, not invented. A wrong declared
    signature otherwise becomes a wrong gate-2 baseline (false ACCEPT). Mechanical/AST-based
    gate-2 extraction is deferred to iteration 9; grounding the Architect's declaration is the
    iter-5 half.
- **Slice split decided when detailing (2026-06-25), see [`06-iteration-5-orchestrator-plan.md`](06-iteration-5-orchestrator-plan.md).** The five
  requirements are real but ship in two slices to dogfood sooner. **Iter 5 builds:** unforgeable
  approval, orchestrator-runs-gate-1, grounded Architect signatures (the correctness-critical
  one, kept in because a wrong baseline is a false ACCEPT), and plain `codegraph sync`. **Iter 5b
  defers:** CodeGraph freshness *verification* (beyond plain sync) and the capped REJECT -> revise
  loop. Budget metering stays iter 6 as before.
- Detail deferred. Depends on how much hand-holding iterations 2-4 needed between steps.

## Iteration 6 — Budget hardening *(light — re-planned from feedback)*

- **Goal:** Enforce the token budget (design §3) across the loop and tighten the
  forbidden-behavior guards (no whole-repo dumps, no re-querying, no raw payloads).
- **User-facing value:** The harness stays cheap over many features instead of degrading into
  repo-wide exploration.
- **Note:** survey-on-cadence and drift-trend re-survey triggers moved into iteration 5 (the
  orchestrator's conditional step-0 staleness rule), so they are not separate work here.
- **Budget is metered, not self-reported (from iter-4 user-test).** Today each agent reports its
  own query count and the human verifies by hand. Enforcement must measure actual tool calls
  (the orchestrator or a hook counts `codegraph_explore` invocations) and fail/flag when an agent
  exceeds its budget, rather than trusting the agent's summary line.
- **Periodic full-graph drift scan (from iter-4 user-test).** The Architect classifies drift only
  for the feature's area (correct for focus), so harmful drift *outside* every feature's area
  accumulates invisibly until a Surveyor re-survey. Add a cheap, feature-independent full-graph
  drift check (run on the iter-5 cadence trigger) so accumulating off-path drift is surfaced, not
  silently carried.
- Detail deferred. Sequenced before packaging because the loop must be proven cheap before
  it is worth shipping to others.

## Iteration 7 — Structured intended-architecture layer *(light — added 2026-06-25 from feedback)*

- **Goal:** Move the intended layer from prose to structured data, so reconciliation and the
  signature gate become a mechanical diff (structured-intended vs CodeGraph-observed) instead of
  prose judgment. This is the keystone the framework-aware and deterministic-gate work sit on.
- **User-facing value:** The intended contracts and domain model live as machine-diffable data
  (`contracts.yaml`, `domain-model.yaml`) you can review in a PR; drift against the code is
  detected by a deterministic diff, not by a model reading prose.
- **Why here (before framework-aware and polyglot):** the load-bearing distinction is
  observed-vs-intended. *Observed* structure (signatures, edges) stays in CodeGraph and is
  queried per slice; there is no generated observed artifact (it would only duplicate and stale
  CodeGraph). *Intended* structure cannot come from CodeGraph (intent may deliberately differ
  from code, and that difference is the drift the harness exists to catch), so it must be a
  curated, version-controlled, structured artifact. Today it is prose (`domain-model.md`,
  `data-contracts.md`), which is why it drifts and cannot be checked mechanically. Structuring it
  is a prerequisite for iter 8 (the convention profile shapes these files) and iter 9 (the
  deterministic gate-2 diffs against them).
- **Scope guardrail (resist 1:1 generation, not a size worry):** because CodeGraph holds every
  signature, the easy path is to auto-generate these files 1:1 from the code. Do NOT. That would
  (a) balloon them (a full fine-grained map of ~1000 classes x 5 methods + edges is roughly 90k
  tokens, the cautionary ceiling, far too big to hold resident), (b) recreate the forbidden full
  code index, and (c) couple intended to observed, which destroys reconciliation since intended
  must survive code drift. Instead these files hold only the **curated seam worth preserving**
  (boundary-crossing contracts + key domain classes, seeded from CodeGraph then trimmed by a
  human), a fraction of all classes, a few k tokens, near-resident or cheaply sliced. The full
  observed map stays in CodeGraph, queried per task, never resident. By construction this is
  enough: reconciliation needs only the seam entries a feature touches (intended) diffed against
  a CodeGraph slice (observed), never the whole map at once.
- **Features introduced (sketch):**
  - `contracts.yaml` — intended data contracts as data: name, layer, fields + types, which
    boundary each crosses. Replaces the prose `data-contracts.md`.
  - `domain-model.yaml` — intended domain classes as data: name, layer, responsibility,
    invariants, public method signatures. Replaces the prose `domain-model.md`.
  - Surveyor emits these structured (seeds from CodeGraph, human curates). The Architect's patch
    sections 7-8 become structured diffs to them, and the iter-4 seam signatures become entries
    in these files rather than free text.
  - Reconciliation reads them as data: for each intended entry, compare the CodeGraph-observed
    signature and diff. This is what makes gate-2 mechanical (delivered fully in iter 9).
- **Fork resolved (2026-06-25):** observed structured map = CodeGraph itself (queried per slice,
  no generated observed artifact); intended structured layer = these new curated YAML files.
- **Testable conditions (sketch):** `contracts.yaml` + `domain-model.yaml` exist, describe this
  repo's seam, and a deterministic diff against CodeGraph shows ALIGNED for the current code; a
  planted intended-vs-code mismatch is reported as drift by the diff, not by prose reading.
- **Risks / open decisions:** how much of the domain to capture as intended (seam only, not every
  class, to stay compact); whether `architecture.md` stays prose (narrative) while contracts and
  domain-model go structured (recommended: yes, narrative stays prose, definitions go structured).

## Iteration 8 — Framework-aware architecture model *(light — added 2026-06-25 from feedback)*

- **Goal:** Stop the harness from assuming one project's ontology. Make the intended-
  architecture model derive from whatever framework the target repo actually uses, so the same
  agents work on a Flask, React, or Spring repo, not only this Python/DDD self-host.
- **User-facing value:** You run the Surveyor on a Flask (blueprints / models / services), a
  React (features / components / hooks), or a Spring (controller / service / repository) repo
  and the generated `boundaries.yaml` + docs name *that* framework's idiomatic modules, instead
  of a `domain/contracts/application/adapters` template that does not fit.
- **Why now (not earlier, not later):** the *model* is already framework-agnostic in data
  (`boundaries.yaml` = named modules + globs + dependency rules). What is bound is (a) agent
  **prompt prose** (`architect.md` mandates "domain class / no module-level business function /
  no raw dict across a boundary", `surveyor.md` seeds DDD layers) and (b) the **signature
  idiom**. Both are cheap to generalize and must precede packaging (iter 10) — you cannot ship a
  Python-DDD-assuming harness to other stacks. Enforcement stays Python-only until iter 9.
- **Features introduced (sketch):**
  - **Convention profile** — a new Surveyor-written artifact (e.g. `.architecture/profile.yaml`)
    capturing detected framework, layer vocabulary, naming rules, and signature idiom
    (Python dataclass vs TS interface vs Java interface). This single artifact is what "honors
    the existing structure": the Architect reads it instead of assuming DDD layers.
  - **Surveyor framework detection** — from CodeGraph + manifest files (`requirements.txt`,
    `package.json`, `pom.xml`/`build.gradle`), propose the idiomatic module map as the *seed*,
    user edits/confirms. Never impose; detect then confirm.
  - **De-hardcoded agent prompts** — Surveyor and Architect read the profile for vocabulary and
    rules; the `domain/contracts/application/adapters` set becomes *one example profile*, not
    the law baked into prose.
  - **Idiomatic seam signatures** — the Architect's iter-4 signature emission renders in the
    profile's language (Python sig / TS type / Java interface).
- **Testable conditions (sketch):** Surveyor on a non-DDD layout (e.g. a Flask sample) produces
  a `boundaries.yaml` naming that framework's modules and a profile recording the framework; the
  Architect's patch for a feature on that repo uses the profile's vocabulary and signature idiom,
  not the hardcoded DDD terms.
- **Risks / open decisions:** how far detection goes vs always asking the user; whether the
  profile is one file or folded into `architecture.md`. Decide when detailing, from iters 4-6
  feedback. Enforcement (running the linter) on non-Python repos is explicitly OUT — that is
  iteration 9.

## Iteration 9 — Polyglot enforcement *(light — added 2026-06-25 from feedback)*

- **Goal:** Make the *enforcement* gate language-agnostic. Iteration 8 lets the harness
  describe a non-Python repo; iteration 9 lets it actually *check* one.
- **User-facing value:** The validation gate (iter 4) runs on a TypeScript or Java repo and
  reports boundary violations there, so the whole loop — not just the docs — works off Python.
- **Why separate from iter 8:** the current scanner is Python-`ast`-only
  (`src/adapters/boundaries/python_import_scanner.py`); supporting TS/Java imports is a real
  parser/data-source lift, the most expensive piece of generalization. Sequenced after the
  cheap model generalization and validated like everything else on a real sample first.
- **Likely shape (one fork to decide when detailing):**
  - **A) Lean on CodeGraph edges** — CodeGraph already indexes multiple languages; derive
    import/dependency edges from the graph instead of parsing source, making the scanner an
    adapter over CodeGraph rather than over `ast`. Polyglot "for free", couples to CodeGraph.
  - **B) Multi-language scanner** — add per-language parsers behind the existing
    `ScanResult` contract. More work, no CodeGraph coupling at check time.
- **Deterministic gate-2 (from iter-4 user-test).** Iter-4 gate 2 (seam-signature conformance)
  is LLM-judged: the Inspector reads source and compares to the patch by judgment, so it is the
  one non-deterministic gate. Whichever signature-extraction this iteration builds per language
  (AST or CodeGraph) should also back a **mechanical** gate-2, so signature conformance becomes a
  deterministic check like gate 1 rather than a model opinion. Same extractor serves both.
- **Testable conditions (sketch):** the linter on a TS or Java sample with a planted forbidden
  edge reports it with correct file + line and exits non-zero, same contract shape as the
  Python path; a planted signature mismatch is caught mechanically.
- **Risks / open decisions:** the A-vs-B fork (CodeGraph-edge vs own parsers) is shape-changing
  — surface it to the user when detailing. Relative/aliased imports per language are an edge
  set to enumerate then.

## Iteration 10 — Packaging & install (Claude Code plugin) *(light — re-planned from feedback)*

- **Goal:** Turn the proven, repo-local harness into something a user installs into any repo,
  not files they hand-copy.
- **User-facing value:** A user runs `/plugin install <harness>`, then a one-shot
  `harness-init`, and their repo has the four agents wired and intended-architecture docs
  bootstrapped, ready for the feature loop.
- **Packaging decision (locked): Claude Code plugin.** The system is entirely Claude Code
  artifacts (self-contained agent defs + a setup skill + the `/.architecture` scaffold), so it
  ships as a plugin in a marketplace rather than a binary or template repo.
- **Likely shape (re-planned from what iters 1–9 prove must ship):**
  - Plugin bundles `.claude/agents/*` (surveyor, architect, builder, inspector), the
    `/harness-feature` orchestrator skill (iter 5), and a `harness-init` setup skill.
  - `harness-init` scaffolds `/.architecture` into the target repo, checks CodeGraph is present
    (hard prereq, installed separately), and runs `surveyor` once to seed intended docs +
    `state.yaml`.
  - Target install flow: `codegraph init` → `/plugin install` → **reload so the agents register
    by name** → `harness-init` → run surveyor once → feature loop ready.
  - **Reload is a verified gate, not a hint (from iter-4 user-test).** A newly installed agent is
    not dispatchable by name until `/reload-plugins`; before that the loop falls back to inline
    general-purpose dispatch. `harness-init` must verify the four agents resolve by name (and
    block / instruct the reload if not) so a fresh install's first loop does not silently run on
    the fallback path.
- **Open / depends-on:** which files actually need to ship (decided by iters 1–9, including the
  convention profile and any polyglot scanner), and whether CodeGraph install can be
  checked/guided by the setup skill or stays fully manual.
- Detail deferred. Sequenced last: packaging is only worth doing once the loop is proven cheap,
  useful, and framework-general (iters 1–9).
