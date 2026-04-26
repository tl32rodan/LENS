# CLAUDE.md — LENS Agent Execution Contract

**Document Type**: Agent harness / execution contract
**Audience**: AI agents (primary), human developers (secondary)
**Pairs With**: `LENS_CHARTER.md` (mandatory) and `LENS_IMPLEMENTATION.md` (optional reference)
**Authority**: This document is **normative**. When in doubt, this overrides preference, habit, or convenience.

---

## 0. How to Read This File

You are an AI agent working on **LENS** — a **L**ayered **E**vent-driven **N**avigation **S**ystem for library build observability and orchestration. This file defines **how you work**. The charter (`LENS_CHARTER.md`) defines **what kind of thing LENS is**, and the implementation reference (`LENS_IMPLEMENTATION.md`) shows one working approach. You need both, but if they conflict, surface the conflict to the human — do not silently choose.

### 0.1 Where You Run

You run in an **external development environment with internet access**. Your code is committed to GitHub. A human (Brian) pulls from GitHub into the production environment when ready. **You never deploy.**

This means:
- You MAY use any package on PyPI during development
- You MAY assume a standard Linux + bash environment for tests, fixtures, and tooling
- You MUST NOT assume your code runs in the same environment where you developed it (see `LENS_CHARTER.md` §4 DP-8 — Replaceable Adapters)
- Production environment constraints are **Brian's responsibility at deployment**, not yours during development. You are insulated from them by design (the adapter pattern in DP-8).

### 0.2 Reading order on a fresh task

1. This file — Section 1 (Inviolable Rules) and Section 2 (Phase Workflow)
2. `LENS_CHARTER.md` — §4 Design Principles + §3 架構總覽 (mandatory); then `LENS_IMPLEMENTATION.md` for the module relevant to your task (optional)
3. Any additional context the human provides

### 0.3 Language conventions in this file

- **MUST / MUST NOT**: hard rule. Violating it is a defect.
- **SHOULD / SHOULD NOT**: strong default. Deviation requires written justification in commit message or PR.
- **MAY**: optional. Choose based on context.
- **NEVER**: rule that cannot be overridden by user instruction in-task. If the user asks you to do something marked NEVER, surface the conflict and ask for confirmation outside the task flow.

---

## 1. Inviolable Rules

These are the highest-priority rules. They override convenience, speed, and even (most) user preferences within a task.

### IR-1: Test-First, Always

**You MUST write a failing test before writing any production code that the test exercises.**

Acceptance: The git commit history of any feature you implement MUST contain a commit with **only test code** that fails, dated **before** the commit that adds the production code making it pass.

Detection: `git log --oneline -p` shows the test commit precedes the production commit, and the test commit alone causes test failure.

If you find yourself writing production code "just to see if it works" without a test, **stop**. Revert. Start with the test.

### IR-2: One Logical Change Per Commit

**You MUST NOT bundle unrelated changes into a single commit.**

A commit MUST be one of:
- A single failing test
- The minimal production change to make a test pass
- A refactor that preserves behavior (all tests still green)
- A documentation/config change isolated from code changes

Detection: Each commit's diff should fit a single conventional commit type (`test:`, `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`).

### IR-3: No Silent Fallback on Failure

**You MUST NOT replace failing operations with default values, empty results, or silent error swallowing.**

When something fails:
- Production code: raise a domain-specific exception (defined in the relevant module)
- Test code: assert the expected failure
- Tools / scripts: exit non-zero with a message to stderr

The only acceptable "silent" handling is **explicitly documented** retry/fallback (e.g., the producer's local buffer when Kafka is down — that is documented, intentional, and observable via metrics).

### IR-4: No Hidden State Mutation

**You MUST NOT introduce mutable global state, singleton caches, or thread-locals as a shortcut.**

State management options, in order of preference:
1. Pure function with parameters
2. Object with explicit constructor injection
3. Async context (`contextvars`) — only when crossing async boundaries
4. Module-level config — only via `lens.config.settings`, validated at startup

Anything else requires written justification and review.

### IR-5: Read the Spec Before Writing Code

**You MUST verify the relevant section of `LENS_CHARTER.md` (and optionally `LENS_IMPLEMENTATION.md`) covers your task before producing code.**

If the spec does not cover your task, you have one of three situations:
- The task is configuration / scaffolding outside spec scope → proceed
- The task requires a spec extension → stop and propose the extension first
- You missed the relevant section → re-read

Detection: When asked, you can quote the exact spec section governing your work.

### IR-6: Surface Conflicts, Don't Silently Choose

**You MUST stop and ask when:**
- Spec contradicts itself
- Spec contradicts CLAUDE.md
- User instruction in this task contradicts a rule marked NEVER or MUST in CLAUDE.md
- Two reasonable design choices have non-trivial tradeoffs not covered in spec

You MUST NOT make these choices unilaterally and bury them in code.

### IR-7: Coverage and Type Safety Are Gates, Not Goals

**Before declaring a unit of work complete:**
- All new public functions/methods MUST have type hints (mypy strict pass)
- New code MUST have ≥ 90% line coverage by tests
- All tests MUST pass (no `@pytest.skip`, no `xfail` without explicit issue link)
- Lint and format MUST pass (`ruff check`, `ruff format --check`)

These are **entry gates** for the Verify phase, not aspirational goals.

---

## 2. Phase Workflow (OpenSpec-inspired)

Every unit of work flows through three phases. **You MUST explicitly enter and exit each phase**. The transition between phases has gates that MUST pass.

```
┌──────────┐  entry-gate-A  ┌─────────────┐  entry-gate-B  ┌──────────┐
│   PLAN   │ ─────────────▶ │  IMPLEMENT  │ ─────────────▶ │  VERIFY  │
└──────────┘                └─────────────┘                └──────────┘
   produces:                  produces:                       produces:
   - test list                - failing tests                 - PR with all gates green
   - design notes             - production code               - integration evidence
   - clarification Qs         - passing tests                 - human review marker
```

### 2.1 Phase: PLAN

**Purpose**: Convert the requirement into an explicit, reviewable plan **before** any code is written.

**Entry Trigger**: A new task is assigned (e.g., "implement `lens.events.schema`").

**You MUST produce, in order**:

1. **Restatement**: One paragraph: what this task delivers, what it does NOT deliver, who depends on it.
2. **Spec Reference**: Cite the section(s) of `LENS_CHARTER.md` (mandatory) or `LENS_IMPLEMENTATION.md` (reference) governing this task.
3. **Test List**: A numbered list of test cases you will write, each as a one-line description (matches the style in spec's "Test List" subsections). The list MUST cover:
   - Happy path
   - Boundary / edge cases
   - Failure modes (raised exceptions, error returns)
   - Idempotency / retry behavior (where applicable)
4. **Design Notes**: 1–3 paragraphs on non-obvious decisions you'll make during implementation. State alternatives considered.
5. **Clarification Questions**: Any genuinely ambiguous points needing human input. If you have none, say so explicitly: "No clarifications needed."

**Exit Gate (Plan → Implement)**:

Before leaving PLAN, **you MUST**:
- [ ] Have human acknowledgement on the test list (a thumbs-up or written approval)
- [ ] Have answers to all clarification questions
- [ ] Have the test list in a form that can be ticked off (markdown checklist, GitHub issue, or commit message)

**You MUST NOT** proceed to IMPLEMENT without explicit approval. Asking "should I start?" and getting silence is **not** approval.

### 2.2 Phase: IMPLEMENT

**Purpose**: Turn the plan into working code, one test at a time.

**Inner Loop** (per test on the test list):

```
1. Read the next unchecked test from the test list.
2. Write the test. Run it. Confirm it fails for the expected reason.
3. Commit:    test: add test for <subject>
4. Write the minimal production code to pass this test.
5. Run the full test suite. Confirm only the new test changes status.
6. Commit:    feat: implement <subject> to pass <test name>
7. Refactor if needed. Run tests. Commit (if changed):
              refactor: <description>
8. Tick off the test in the test list.
9. Loop.
```

**Within IMPLEMENT, you MUST**:
- Follow the inner loop verbatim. No shortcuts.
- Run the full test suite (not just the new test) at step 5 to detect regressions.
- Keep production code minimal — write only what the current test demands. Speculative code is forbidden.
- If a test reveals a flaw in the plan, **stop the inner loop**. Re-enter PLAN, update test list, get re-approval.

**Within IMPLEMENT, you MUST NOT**:
- Skip ahead in the test list ("I know what test 5 needs, let me write that production code now")
- Write multiple tests before any production code (tests are written one at a time)
- Combine refactor with feature change in one commit
- Disable, skip, or `xfail` a previously-green test without justification in commit message
- Add new test cases not in the approved list without re-entering PLAN
  - **Exception**: if the new case is a bug discovered during implementation (e.g., an off-by-one in your code triggers a case the list missed), add it AND record it in commit message: `test: add test for off-by-one discovered while implementing X`. This is plan-extension via discovery, which is acceptable.

**Exit Gate (Implement → Verify)**:

Before leaving IMPLEMENT, **you MUST**:
- [ ] All tests on the original test list have a passing test in the suite
- [ ] No tests are skipped, xfailed, or disabled
- [ ] All commits follow the pattern in IR-2
- [ ] Lint, format, typecheck all pass locally
- [ ] You have not introduced any TODO comments (TODO is a `chore:` commit, not a deliverable)

### 2.3 Phase: VERIFY

**Purpose**: Demonstrate the work meets all gates and is ready for human review or merge.

**You MUST produce a Verification Report** as part of the PR or task completion message:

```markdown
## Verification Report

### Test list completion
- [x] Test 1: <name> — commit abc1234
- [x] Test 2: <name> — commit def5678
... (all items from PLAN's test list)

### Coverage
- New code lines: NNN
- Covered lines: NNN
- Coverage: 9X.X% (≥ 90% required)

### Quality gates
- [x] mypy --strict pass
- [x] ruff check pass
- [x] ruff format --check pass
- [x] pytest -q pass (XX passed, 0 failed, 0 skipped)
- [x] pytest tests/integration pass (if cross-module)

### Spec adherence
Cite the spec section(s) governing this work:
- §X.Y of LENS_CHARTER.md / LENS_IMPLEMENTATION.md

State any deviation from spec and the justification:
- (none) OR (deviation + justification)

### Open questions for review
- (any) OR (none)
```

**Exit Gate (Verify → Done)**:
- [ ] Verification Report present and complete
- [ ] Human review completed (or explicitly waived for trivial work)
- [ ] All CI checks green

After Done, the task is closed. You MUST NOT continue adding to it; new requirements are new PLAN cycles.

---

## 3. TDD Protocol (Detailed)

This section expands IR-1 and §2.2's inner loop into operational detail. When in doubt about TDD specifics, this is the reference.

### 3.1 Red-Green-Refactor Mechanics

**RED**: Write a test that fails for the right reason.

A "right reason" failure:
- Test fails because the function doesn't exist yet, OR
- Test fails because the function returns the wrong value/raises the wrong exception, OR
- Test fails because the assertion correctly identifies missing behavior

A "wrong reason" failure (and how to detect):
- Test fails due to import error in test file → fix test file structure first
- Test fails due to fixture error → fix fixture first
- Test "fails" but actually was never executed → check pytest output for collection errors

**Verify the right reason**: When a test first fails, read the failure message. Confirm it's the expected failure, not an accident.

**GREEN**: Write the smallest code that makes the test pass.

"Smallest" is literal:
- If the test asserts `f(1) == 1`, it is acceptable to implement `def f(x): return 1` and add the next test in the list to drive generalization.
- This is sometimes called "**fake it till you make it**" — and it is a feature, not a bug. It forces you to write tests that actually constrain behavior.

**REFACTOR**: Improve structure without changing behavior.

Refactor opportunities:
- Extract repeated code into helper
- Rename for clarity
- Remove dead code introduced by earlier "fake it" steps
- Improve type hints

You MUST run all tests after each refactor commit. If anything goes red, you broke something — revert and try smaller.

### 3.2 Commit Pattern (Strict)

```
test: add test for NodeStarted rejects invalid level
feat: implement NodeStarted level validation
test: add test for NodeStarted rejects empty entity_id
feat: implement NodeStarted entity_id validation
refactor: extract validator into _validate_required_fields
test: add test for NodeCompleted requires exit_code
feat: implement NodeCompleted exit_code validation
```

Notice:
- Each test commit alone fails. Each feat commit alone makes the corresponding test pass.
- Refactor commits never appear without preceding green state.
- Commit messages name the *behavior*, not the function (`add test for X behavior`, not `add test_function_name`).

### 3.3 What "Test" Means

A test is **a runnable assertion of behavior**. It is NOT:
- A docstring example
- A type hint
- A schema declaration
- A `print(result)` statement

A test MUST:
- Live in `tests/` directory
- Be discoverable by `pytest`
- Make at least one explicit `assert`
- Have a name starting with `test_`
- Pass deterministically (no flakes; if needed, mark `@pytest.mark.flaky` with comment)

### 3.4 Boundary Cases You MUST NOT Skip

For every public function, the test list MUST include cases for:
- **Empty input** (empty string, empty list, empty dict, None where allowed)
- **Boundary values** (zero, negative, maxint, max-length)
- **Wrong type** (where the function's contract states what's accepted, test rejection of what's not)
- **Idempotency** (where applicable: calling twice gives same result)
- **Error path** (every documented exception MUST have a test that triggers it)

If the test list lacks one of these for a public function, the PLAN phase is incomplete.

---

## 4. Code Quality Gates

These are objective, automated checks. CI MUST run all of them. Local pre-commit SHOULD run them.

| Gate | Tool | Threshold | Override Mechanism |
|---|---|---|---|
| Format | `ruff format --check` | Zero diffs | None — must format |
| Lint | `ruff check` | Zero violations | `# noqa: <rule>` with comment why |
| Type | `mypy --strict` | Zero errors | `# type: ignore[<rule>]` with comment why |
| Test pass | `pytest` | All pass, none skipped | None |
| Coverage | `pytest-cov` | New code ≥ 90% | None — write more tests |
| Integration | `pytest tests/integration` | All pass | None for cross-module changes |

**Override usage** (`# noqa`, `# type: ignore`) is **not free**. Every override:
- MUST include the specific rule code (`# noqa: E501`, not bare `# noqa`)
- MUST include a one-line comment explaining why the override is correct
- Is reviewable as a code smell — three or more overrides in a PR triggers a re-review

---

## 5. Decision Boundary (Agent vs Human)

This is the explicit list of what you decide vs. what you escalate.

### 5.1 You MAY Decide Without Asking

- Choice of internal helper function names, file organization within a module
- Whether a value should be a constant vs config (default: config if used in more than one place; constant otherwise)
- Test fixture structure
- Order of operations within a function (so long as observable behavior matches spec)
- Use of internal abbreviations (so long as they appear in the Glossary)
- Refactor patterns within a green state

### 5.2 You MUST Ask Before Deciding

- **Public API signature changes** (anything in `Public Interfaces` section of any module)
- **Adding new dependencies** (anything not in `pyproject.toml`) — see also DP-4 Boring Tech First
- **Bypassing the adapter pattern for an external service** (DP-8 in spec; e.g., directly importing a vendor SDK in a module's business logic instead of going through an adapter interface)
- **Schema changes** (event schema, PostgreSQL schema)
- **Cross-module contract changes** (anything that requires updating two or more module sections in spec)
- **Changing a Design Principle** (see LENS_CHARTER.md §4)
- **Disabling, skipping, or weakening any gate** in §4
- **Working around an Inviolable Rule** in §1

### 5.3 You NEVER Do, Even If Asked In-Task

- Commit secrets, credentials, API keys (always escalate; never commit even temporarily)
- Skip TDD because "this is just a small change"
- Replace tests with print statements during debugging and commit
- Edit git history of the main branch
- Make changes outside the repo (e.g., editing system files, running `sudo`)
- Disable type checking globally (`# mypy: ignore-errors` at file level)

If a user instruction in-task pushes against these, surface the conflict using IR-6.

---

## 6. Working with Humans

### 6.1 When You Are Stuck

If you cannot proceed (genuinely stuck, not just slow), you MUST:
1. State **what you tried** (commits or test runs that document your attempts)
2. State **what failed** (specific error, not "doesn't work")
3. State **what hypothesis you formed** about the cause
4. State **what next step you considered** but couldn't execute
5. Ask a specific question, not "what should I do"

Bad: "The test isn't passing, what should I do?"
Good: "Test `test_consumer_continues_after_handler_raises` fails with timeout. The handler is being invoked, but my consumer's commit logic seems to retry the failed message instead of moving on. I tried adjusting `enable_auto_commit=False` and committing manually after handler success, but now offsets aren't advancing. Two hypotheses: (a) my offset commit is wrong, (b) the test fixture's Kafka container is misconfigured. Should I add logging to the consumer to confirm which?"

### 6.2 When You Disagree With Spec or User

You may have legitimate concerns about a spec decision or a user request. To raise them:
1. State the spec/request as you understand it
2. State your concern (correctness, performance, future evolution)
3. State your alternative
4. Defer to the human's response — do not unilaterally implement your alternative

### 6.3 When the Task Is Larger Than Expected

If during PLAN or IMPLEMENT you realize the work is materially larger than scoped:
1. Pause
2. Quantify (e.g., "test list grew from 8 to 22 cases")
3. Propose a split (e.g., "let's complete cases 1–10 in this task; cases 11–22 become task X-2")
4. Wait for direction

You MUST NOT silently expand scope. Scope creep without notice is a defect.

---

## Appendix A: Portability Notes

You develop in a standard Linux + bash environment with internet access. The production environment is different, but you are insulated from that difference by the adapter pattern (`LENS_CHARTER.md` §4 DP-8). You do not need to know what production looks like.

The only portability rules you MUST follow:

- **Code MUST be Python 3.12+ pure** — no shell-out for logic that could be Python
- **Any shell script (Makefile target, Docker entrypoint, CI script) MUST be POSIX `sh`-compatible** — start with `#!/bin/sh`, no bash-isms (`[[`, array syntax, etc.). Verify with `shellcheck -s sh`.
- **No hardcoded URLs, hostnames, or credentials** — everything comes from `lens.config.settings` (see spec §10)
- **No assumption about which adapter is wired in production** — code targets the interface, not a specific implementation

If you find yourself writing code that depends on production specifics, you are violating DP-8. Refactor through an adapter.

---

## Appendix B: Common Failure Modes

These are patterns you might fall into. They are flagged here so you can self-detect.

### B.1 The "I'll add tests later" Slide

**Symptom**: You start with intention to TDD, then "just sketch" a function, then realize the test is hard to write because the function isn't designed for testing, then write a weak integration-style test that doesn't really verify the behavior.

**Detection**: Your latest commit is `feat:` and there's no preceding `test:` for that behavior.

**Recovery**: Revert the production code. Start over with the test.

### B.2 The "Mock Everything" Trap

**Symptom**: Your unit tests use mocks for everything (HTTP clients, databases, even pure functions). The tests pass but they're testing your mocks, not real behavior.

**Detection**: Test file imports `unittest.mock.patch` more than three times in a file.

**Recovery**: Replace mocks with fakes (in-memory implementations of the same interface) where possible. Reserve mocks for genuine boundaries (network, time, randomness).

### B.3 The "Test Mirrors Implementation" Anti-pattern

**Symptom**: Your test asserts the implementation, not the behavior. E.g., `assert producer._buffer.size() == 1` instead of `assert (await fake_kafka.received_messages()) == [event]`.

**Detection**: Tests reference private attributes (leading underscore) of the unit under test.

**Recovery**: Rewrite the assertion against observable behavior. If you cannot, the unit's interface is wrong — refactor.

### B.4 The "Big Bang Commit"

**Symptom**: You worked for an hour, made many changes, and now have a commit with 500+ lines spanning multiple files and concerns.

**Detection**: `git diff --stat HEAD~1` shows more than ~50 lines or more than 3 files (excluding generated/lock files).

**Recovery**: Use `git reset HEAD~1` and re-stage incrementally. Or, if too late, the next PR review should reject this and you redo.

### B.5 The "Spec? What Spec?" Drift

**Symptom**: Halfway through implementation you've stopped consulting the spec; you're "in flow" and just writing.

**Detection**: When asked, you cannot point to the spec section governing the code you just wrote.

**Recovery**: Stop. Re-read the relevant spec section. Audit your code against it. Common discoveries: missing error case, wrong interface signature, wrong module location.

### B.6 The "Single Test File Megaclass"

**Symptom**: You're adding tests to a `TestEventProducer` class that now has 30+ test methods.

**Detection**: One test file > 500 lines.

**Recovery**: Split by behavior cluster (e.g., `test_producer_sending.py`, `test_producer_buffer.py`, `test_producer_lifecycle.py`).

---

## Appendix C: Quick Reference Card

```
╔═══════════════════════════════════════════════════════════════╗
║                  AGENT EXECUTION QUICK REF                    ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  PHASE TRANSITIONS:                                           ║
║    PLAN → IMPLEMENT  needs:  approved test list               ║
║    IMPLEMENT → VERIFY needs: all tests pass + clean gates     ║
║    VERIFY → DONE     needs:  Verification Report + review     ║
║                                                               ║
║  TDD INNER LOOP:                                              ║
║    1. Read next test from list                                ║
║    2. Write test, run, confirm right-reason failure           ║
║    3. Commit (test: ...)                                      ║
║    4. Write minimal production code                           ║
║    5. Run full suite                                          ║
║    6. Commit (feat: ...)                                      ║
║    7. Refactor if needed, run, commit (refactor: ...)         ║
║    8. Tick the test, repeat                                   ║
║                                                               ║
║  STOP IMMEDIATELY IF:                                         ║
║    □ Spec contradicts itself or this file                     ║
║    □ A green test goes red unexpectedly during refactor       ║
║    □ Scope grew materially beyond original plan               ║
║    □ User asks something marked NEVER in §5.3                 ║
║                                                               ║
║  HARD GATES (no override):                                    ║
║    □ Test before code (IR-1)                                  ║
║    □ One change per commit (IR-2)                             ║
║    □ ≥90% coverage on new code                                ║
║    □ mypy strict pass                                         ║
║    □ All tests pass, none skipped                             ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

---

## Document Metadata

- **Version**: 1.3
- **Last Updated**: [date]
- **Authority**: Brian (lead) + AI agents collaborating
- **Pairs With**: `LENS_CHARTER.md` v1.0+ (mandatory) and `LENS_IMPLEMENTATION.md` v1.0+ (reference)
- **Conflict Resolution**: This file overrides convenience. Charter overrides this file on platform principles. Implementation Reference is optional — agent may deviate with reasoned justification. Human overrides everything in conscious decisions.

### Changelog

- **v1.0**: initial agent harness (OpenSpec-inspired phase workflow + TDD inner loop + 7 inviolable rules)
- **v1.1**: clarified development context (external + GitHub workflow); removed Appendix A subsections about air-gapped / tcsh / internal LLM endpoints — these are now handled by DP-8 (Replaceable Adapters); replaced with a short Portability Notes appendix; added explicit DP-8 reference in §5.2.
- **v1.2**: platform formally named **LENS**; renamed all `ngap` references to `lens` (package, CLI, Kafka topic, env prefix); aligned with spec §2 Naming Convention and DP-9.
- **v1.3**: implementation_spec.md split into three files — `LENS_CHARTER.md` (mandatory: principles, architecture, naming, why), `LENS_IMPLEMENTATION.md` (optional: one working approach), `LENS_TEST_REFERENCE.md` (optional: test list starting points). All references in this file updated to point to the appropriate target. Agent's reading order updated: Charter first, Implementation as reference when needed.

---

*— End of CLAUDE.md (LENS v1.3) —*
