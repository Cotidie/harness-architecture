# Iteration 8 (Framework-aware architecture model) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (or subagent-driven-development). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Stop the harness from baking one project's ontology. The DDD vocabulary ("contract class", "domain class", "adapters") becomes ONE profile among many: a `profile.yaml` records the project's framework, layer roles, vocabulary, and signature idiom; the agents read vocabulary from it; only framework-agnostic principles stay in prose. The same agents then fit a non-DDD repo, not only this Python/DDD self-host.

**Architecture:** One new curated artifact (`.architecture/profile.yaml`), one new committed detection tool (`scripts/detect_profile.py`) with unit tests, de-hardcoding edits to two agent defs (`architect.md`, `surveyor.md`), and a layout-only non-DDD fixture (`examples/flask-mini/`) with a test proving detection is not DDD-baked. No change to the linter's behavior or the iter-7 diff. Enforcement on non-Python repos stays OUT (iteration 9).

**Tech stack:** YAML artifact; Python stdlib (`os`, `json`, `tomllib` if needed) + `unittest` (mirrors `scripts/drift_scan.py`, `scripts/intended_diff.py`); Markdown agent defs.

## Locked decisions (from planning forks, 2026-06-25)

- **Dogfood = add a small non-DDD sample in-tree.** A layout-only Flask-ish fixture proves the detected profile + vocabulary name THAT framework's modules, not `domain/contracts/adapters`. (Profiling the self-host as `python-ddd` is also done, but the fixture is what proves generalization.)
- **Detect-then-confirm.** A committed `detect_profile` script proposes a seed (language, manifests, candidate layers, framework guess); the Surveyor writes it into `profile.yaml` and the human confirms/edits. Never impose, never silent-auto.
- **Fixture is layout-only.** Directory skeleton + manifest + stub files, enough to exercise `detect_profile` deterministically. Not a working app (no CodeGraph index needed for it this slice).
- **`framework_guess` from manifest libraries only.** The script maps known dependency names (flask, django, react, express, spring) to a framework label. It does NOT guess layer ROLES from directory names: a built-in role heuristic would just be a smaller baked ontology, the exact thing this iteration removes. Layer names stay candidates for the human to map.
- **Signature idiom is recorded now, normalized in iter 9.** `profile.yaml` captures the idiom as data; the semantic type-normalizer (Tuple == tuple) is built with the polyglot CodeGraph-index extractor in iter 9.

## Global Constraints

- Do not change the linter's behavior or the iter-7 `intended_diff` semantics. This is ontology-generalization + detection work.
- Separate **universal principles** (framework-agnostic, stay in prose) from **profile vocabulary** (the nouns, read from `profile.yaml`). Do not delete the principles; re-express their NOUNS as profile lookups.
- `boundaries.yaml` stays the per-module dependency rules. `profile.yaml` is the ontology meta on top (framework, role mapping, vocabulary, idiom). No duplication of dependency rules.
- The detection script is humble: it detects language reliably, proposes candidate layers, and marks the framework "confirm". It never asserts a role mapping.
- Never use em-dash in authored content.

## File structure

- Create `.architecture/profile.yaml` : the self-host's convention profile (`python-ddd`) (Task 1).
- Create `scripts/detect_profile.py` : the committed detection/seed tool (Task 2).
- Create `tests/test_detect_profile.py` : its unit tests (Task 2).
- Modify `.claude/agents/architect.md` : de-hardcode DDD nouns to profile lookups; fix stale pointers (Task 3).
- Modify `.claude/agents/surveyor.md` : run detect_profile as seed, write+confirm profile.yaml, use profile vocabulary (Task 3).
- Create `examples/flask-mini/` : layout-only non-DDD fixture (manifest + blueprints/services/models stubs) (Task 4).
- Create `tests/test_profile_fixture.py` (or extend `test_detect_profile.py`) : assert detection on the fixture names flask layers, not DDD (Task 4).
- Save `docs/iteration/09-iteration-8-framework-aware-plan.md` (this file) + a results note (Task 5).

---

### Task 1: Define the profile schema and author the self-host profile

**Files:** Create `.architecture/profile.yaml`

- [ ] **Step 1: Define the schema.** Top-level keys: `framework` (label, e.g. `python-ddd`), `language`, `detected_from` (list of evidence), `roles` (mapping of abstract harness role -> this project's layer name: `behavior_layer`, `boundary_shape_layer`, `entrypoint_layer`, `io_layer`), `vocabulary` (mapping: `boundary_shape` noun, `behavior_unit` noun), `signature_idiom` (mapping: `contract` example, `method` example). Document each key in a header comment.
- [ ] **Step 2: Author the self-host profile.** `framework: python-ddd`, `language: python`, roles mapping `behavior_layer: domain`, `boundary_shape_layer: contracts`, `entrypoint_layer: application`, `io_layer: adapters`; vocabulary `boundary_shape: "contract class (frozen dataclass under src/contracts/)"`, `behavior_unit: "domain class or method under src/domain/"`; signature_idiom `contract: "ClassName(field: Type, ...)"`, `method: "Class.method(param: Type, ...) -> Return"`.
- [ ] **Step 3: Verify** it parses (`python -c "import yaml; yaml.safe_load(open('.architecture/profile.yaml'))"`); the role values match the module names in `boundaries.yaml`; no em-dash.
- [ ] **Step 4: Commit.** `git add .architecture/profile.yaml && git commit -m "feat(iter-8): convention profile schema + self-host python-ddd profile"`

### Task 2: Build the committed detect_profile seed tool (TDD)

**Files:** Create `scripts/detect_profile.py`, `tests/test_detect_profile.py`

Mirror the committed-script pattern: a `compute_profile_seed(target_dir, source_dir)` returning a frozen dataclass, a `format_seed`, and `main(argv)`.

- [ ] **Step 1 (test first):** write `tests/test_detect_profile.py` with temp-tree cases (RED): (a) a flask-ish tree (`requirements.txt` with `flask`, dirs `blueprints/ services/ models/` holding `.py`) -> `language == "python"`, `framework_guess == "python/flask"`, `candidate_layers == ("blueprints", "models", "services")`; (b) a self-host-ish tree (`requirements.txt` with `pyyaml`, `src/` with `domain adapters ...`) -> `framework_guess == "python/unknown"` (no web lib), candidate_layers = those dirs; (c) `package.json` with `react` -> `framework_guess == "js/react"`; (d) no manifest -> `language` inferred from file extensions or `"unknown"`; (e) `__pycache__` / non-code dirs excluded from candidate_layers.
- [ ] **Step 2: Manifest parsing.** Read root manifests if present: `requirements.txt` (one lib per line, strip versions), `pyproject.toml`, `package.json` (`dependencies` keys), `pom.xml` / `build.gradle` (best-effort lib names). Collect `manifests_found` and `libs`.
- [ ] **Step 3: Language + framework guess.** `language` from the manifest kind + dominant source file extension. `framework_guess` from a small known-lib map (`flask -> python/flask`, `django -> python/django`, `fastapi -> python/fastapi`, `react -> js/react`, `express -> js/express`, `spring-boot|spring -> java/spring`); if no known lib matches, `"<language>/unknown"`. This map names frameworks only; it does NOT map directory names to roles.
- [ ] **Step 4: Candidate layers.** Immediate child dirs of `source_dir` that contain at least one code file (`.py/.js/.ts/.java`), sorted. Exclude `__pycache__`, hidden dirs, and dirs with no code.
- [ ] **Step 5: Seed dataclass + output.** `ProfileSeed(language, manifests_found, libs, framework_guess, candidate_layers)`. `format_seed` prints a YAML-ish seed a human can paste/edit into `profile.yaml`, with `roles` left as a `# confirm: map each role to a candidate layer` block (NOT auto-filled). `main(argv)`: usage `python -m scripts.detect_profile <target_dir> [source_dir]`; print the seed; return 0 (advisory tool, no drift exit code).
- [ ] **Step 6: GREEN.** `python -m unittest tests.test_detect_profile` passes; `python -m scripts.detect_profile . src` on the real repo prints `python/unknown` + the src layers; full suite green; no em-dash.
- [ ] **Step 7: Commit.** `git add scripts/detect_profile.py tests/test_detect_profile.py && git commit -m "feat(iter-8): committed detect_profile seed tool (language + manifest framework guess + candidate layers), unit-tested"`

### Task 3: De-hardcode the agent prompts onto the profile

**Files:** Modify `.claude/agents/architect.md`, `.claude/agents/surveyor.md`

- [ ] **Step 1: Architect hard rules -> universal principle + profile noun.** Rewrite the two DDD-baked rules. "No raw dict/list across a boundary" stays as the universal principle; append "new boundary data uses the profile's `vocabulary.boundary_shape` in `roles.boundary_shape_layer`". "No module-level business functions" stays universal ("new business behavior is a named, testable unit in the behavior layer, not a loose function"); append "use the profile's `vocabulary.behavior_unit` in `roles.behavior_layer`". The DDD specifics now come from `profile.yaml`, not the prose.
- [ ] **Step 2: Architect reads the profile + the iter-7 YAMLs (fix stale pointers).** In "Read first", add `.architecture/profile.yaml`, and add `.architecture/contracts.yaml` + `.architecture/domain-model.yaml` (the iter-7 definition layer; the `.md` files are now rules-only). Update line ~68: the idiom pointer says "iteration 7 will generalize"; change to "rendered in the profile's `signature_idiom` (iteration 8); semantic normalization is iteration 9".
- [ ] **Step 3: Surveyor detect-then-confirm + profile output.** Add a step: run `python -m scripts.detect_profile <repo> <source_dir>` to get the seed, write `.architecture/profile.yaml` from it (mapping each role to a candidate layer), and present the role mapping for human confirmation (never impose). Add `profile.yaml` to the Surveyor's outputs list (now ten). Replace the "intended-layout placeholder = design's generic DDD map" input with "the detect_profile seed + the confirmed profile"; the DDD layer set is now just the self-host's profile, not a template to copy onto every repo.
- [ ] **Step 4: Verify** both defs reference `profile.yaml` and read vocabulary from it; the universal principles are preserved (not deleted); no stale "iteration 7 will generalize" line remains; no em-dash. `grep -n "profile.yaml\|contract class\|domain class" .claude/agents/architect.md` shows the nouns framed as profile lookups, not law.
- [ ] **Step 5: Commit.** `git add .claude/agents/architect.md .claude/agents/surveyor.md && git commit -m "feat(iter-8): de-hardcode DDD ontology to profile.yaml; agents read vocabulary from the profile; fix stale iter-7 pointers"`

### Task 4: Non-DDD fixture proving detection is not DDD-baked

**Files:** Create `examples/flask-mini/` (layout-only), `tests/test_profile_fixture.py`

- [ ] **Step 1: Build the fixture.** `examples/flask-mini/requirements.txt` (contains `flask`), and stub package dirs `blueprints/`, `services/`, `models/`, each with a trivial `.py` (e.g. an empty `__init__.py` + one stub module). A `README.md` noting it is a layout-only detection fixture, not a runnable app, and not part of the harness's own architecture.
- [ ] **Step 2: Test.** `tests/test_profile_fixture.py`: run `compute_profile_seed("examples/flask-mini", "examples/flask-mini")` and assert `framework_guess == "python/flask"` and `candidate_layers == ("blueprints", "models", "services")` and that it does NOT contain `domain`/`contracts`/`adapters`. This is the headline proof: the ontology comes from the repo, not from baked prose.
- [ ] **Step 3: Keep the fixture out of the linter/diff targets.** Confirm `examples/` is not scanned by the boundaries linter, drift_scan, or intended_diff (all target `src`), so the committed fixture cannot create false drift. No tool should walk `examples/` by default.
- [ ] **Step 4: Verify** `python -m unittest tests.test_profile_fixture` passes; full suite green; no em-dash.
- [ ] **Step 5: Commit.** `git add examples/flask-mini tests/test_profile_fixture.py && git commit -m "feat(iter-8): layout-only flask-mini fixture + test proving detection names framework layers, not DDD"`

### Task 5: Dogfood and record results

- [ ] **Step 1: Real-repo detection.** Run `python -m scripts.detect_profile . src`; confirm it reports `python/unknown` (no web framework lib) and the four src layers, honestly leaving the role mapping to confirm. Record the output.
- [ ] **Step 2: Profile-swap proof.** Demonstrate the de-hardcoding: show that the Architect's boundary/behavior nouns now resolve from `profile.yaml` (e.g. point out that swapping `vocabulary.behavior_unit` would change the agent's instruction, where before it was baked prose). Record this as the mechanism proof.
- [ ] **Step 3: Adversarial / cli-user-test pass** on `detect_profile` (use `cotidie:cli-user-test`): empty dir, dir with no manifest, manifest with no known lib, a source_dir that does not exist, a tree with only non-code dirs. Record behavior.
- [ ] **Step 4: Write the results note** (what worked, findings, gaps). Note honestly that without a CodeGraph-indexed second app, the Surveyor's full survey of a non-DDD repo is proven only at the detection layer (the fixture), not end-to-end; end-to-end on a real other-framework repo is a packaging-time (iter 10) or follow-up validation.
- [ ] **Step 5: Commit** the results note.

## Testable conditions (iteration acceptance)

- `.architecture/profile.yaml` exists, parses, and its roles match the self-host layers.
- `python -m scripts.detect_profile . src` reports python + the src layers + `python/unknown`, leaving roles to confirm.
- `detect_profile` on the flask-mini fixture reports `python/flask` and names `blueprints/models/services`, NOT `domain/contracts/adapters`.
- `architect.md` and `surveyor.md` read the boundary/behavior NOUNS from `profile.yaml`; the universal principles remain; no stale iter-7 idiom pointer.
- Full test suite passes; the fixture creates no false drift in the existing scans.

## Deferred (explicitly NOT in iteration 8)

- **Running the linter / enforcement on non-Python repos:** iteration 9.
- **Semantic signature normalization** (Tuple == tuple, typing aliases): iteration 9, with the polyglot CodeGraph-index extractor.
- **End-to-end Surveyor survey of a real other-framework app** (CodeGraph-indexed): packaging (iter 10) or a follow-up; this slice proves the detection layer only.
- **Architect rendering full idiomatic signatures per profile beyond recording the idiom:** the cross-language signature CHECK is iter 9.

## Risks / open decisions

- **Detection is necessarily shallow.** `detect_profile` guesses framework from libs and proposes layer names; it cannot know role mappings. That is by design (detect-then-confirm), but it means a wrong human confirmation still shapes everything. The profile is a reviewable artifact precisely so that mistake is visible in a PR.
- **`python-ddd` is still the only fully-exercised profile.** The fixture proves detection generalizes; the agents reading the profile is proven by inspection + the profile-swap argument, not by a second end-to-end loop. Honest gap, recorded.
- **Universal-vs-profile split is a judgment call.** Some rules (no raw payload across a boundary) are clearly universal; others may be more DDD-shaped than they look. If a principle turns out framework-specific when a real second framework lands, move its noun into the profile then.

---

## Results (executed 2026-06-25)

Built Tasks 1-5: `.architecture/profile.yaml` (self-host `python-ddd`), the committed `scripts/detect_profile.py` (+ 6 unit tests), de-hardcoded `architect.md` + `surveyor.md`, and the layout-only `examples/flask-mini/` fixture (+ proof test). 98 tests OK (was 91, +7).

**Outcome: iteration shipped.**

- **Detection generalizes (headline proof).** `detect_profile` on `examples/flask-mini/` reports `framework_guess == "python/flask"` and `candidate_layers == (blueprints, models, services)`, and explicitly NOT `domain/contracts/adapters`. The ontology now comes from the repo, not from baked prose.
- **Honest on the self-host.** `python -m scripts.detect_profile . src` reports `python/unknown` (no web-framework lib in `requirements.txt`) and the four `src/` layers, leaving the role mapping blank for the human. Detect-then-confirm, not silent-auto.
- **Ontology de-hardcoded.** `architect.md` now states the universal principles (no raw payload across a boundary; behavior is a named unit) and reads the NOUNS (`vocabulary.boundary_shape`, `vocabulary.behavior_unit`) and layers (`roles.*`) from `profile.yaml`. The DDD specifics are the `python-ddd` profile's values, not law. `surveyor.md` runs `detect_profile` as a seed, writes/confirms `profile.yaml` (now its first of ten outputs), and uses the profile's vocabulary. Two stale iter-7 pointers fixed (read the YAML definition layer; idiom pointer now points at iter 8/9).

### Adversarial pass (cli-user-test style on detect_profile)

- no args -> usage on stderr, exit 2;
- empty dir -> `unknown`/`unknown`, exit 0 (advisory tool, no drift exit code);
- nonexistent `source_dir` -> framework still guessed from the manifest, candidate layers empty, no crash;
- manifest with no known lib -> `python/unknown`;
- only non-code dirs -> `unknown`, `(none detected)` layers.

### Findings / remaining gaps

1. **`python-ddd` is still the only fully-exercised profile.** The fixture proves the DETECTION layer generalizes and the prompts now read the profile (verified by inspection: the nouns resolve from `profile.yaml`). What is NOT proven this slice is an end-to-end Surveyor->Architect->Builder loop on a real other-framework repo, because that needs a CodeGraph-indexed second app. Recorded as a packaging-time (iter 10) / follow-up validation, consistent with the plan.
2. **Detection is intentionally shallow on roles.** `detect_profile` names the framework from manifest libs and lists candidate layers but never maps layers to roles, by design (a built-in role heuristic would re-bake an ontology). The role mapping is a human confirm, so a wrong confirmation still shapes downstream work; the profile is a reviewable PR artifact precisely to surface that.
3. **Signature idiom recorded, not yet normalized.** `profile.yaml.signature_idiom` captures the Python form; the iter-7 literal-type-string brittleness (`Tuple` vs `tuple`) is unchanged and still deferred to iteration 9's semantic comparison.
