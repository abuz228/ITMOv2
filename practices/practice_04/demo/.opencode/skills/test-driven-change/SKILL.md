---
name: test-driven-change
description: "Use when adding or changing a small Python feature in this project (for example the unsubscribe or is_subscribed subscriber features), or any similar project that has AGENTS.md, a docs/requirements.md contract, unittest tests, and a ./scripts/check.sh runner. Follows a strict TDD loop: preparation and baseline, failing tests (RED), minimal implementation (GREEN), then refactor and verification."
---

# Test-Driven Change

A procedure for implementing a small Python feature through test-driven
development. It assumes the project already has its own rules (see
`AGENTS.md`) and a contract (`docs/requirements.md`); this skill adds the TDD
*order of operations* and tool usage, not a second copy of those rules.

## Rule of precedence

`AGENTS.md` and the contract in `docs/requirements.md` are authoritative. If
anything below conflicts with them, follow `AGENTS.md` and the contract. Do
not restate their rules here.

## Preparation

1. Read `AGENTS.md` in the project root and follow it.
2. Read the contract `docs/requirements.md` and the existing tests
   (`tests/`). The contract defines the required behavior, including edge
   cases and error messages.
3. Read the implementation that the change touches (for example
   `service.py`) and note what the current behavior is.
4. Establish a clean baseline: run the runner from the project root and
   confirm it passes *before* making changes.

```sh
./scripts/check.sh
```

If the baseline is already red, stop and report it. Do not build a new feature
on top of a failing suite.

## RED — write failing tests first

1. Add tests for the new functionality before writing any implementation.
   Follow the style and layout of the existing tests.
2. Cover the required cases from the contract:
   - the normal / happy path;
   - boundary cases (for example whitespace-only input);
   - invalid input and the exact error type and message
     (`ValueError("empty name")` in this project).
3. Run the runner:

```sh
./scripts/check.sh
```

4. Confirm the new tests fail **because the functionality is missing**
   (a missing attribute, `NameError`, `AttributeError`, or an unmet
   assertion) — not for an unrelated reason.
5. If a failure is unrelated (typo, wrong import, broken fixture), fix *that*
   first, then re-run until the only failures are the intended "not
   implemented yet" ones. Never weaken or delete a test to make it pass.

Do not write implementation code yet.

## GREEN — make the tests pass

1. Implement the smallest change that satisfies the contract and turns the new
   tests green.
2. Do not change existing behavior that the task did not ask about.
3. Re-run the full runner:

```sh
./scripts/check.sh
```

4. All tests, old and new, must pass. If they do not, fix the implementation,
   not the tests.

## VERIFY — refactor and confirm

1. Refactor only if it clearly improves the code, without changing behavior.
2. Run the full suite again after any refactor:

```sh
./scripts/check.sh
```

3. Check the working tree for whitespace/conflict problems:

```sh
git diff --check
```

4. Report a short summary that records both phases explicitly:
   - **RED**: which tests were added and the observed failure reason before
     implementation.
   - **GREEN**: the implementation change and the passing runner result.

## Notes

- The runner is the single source of truth for "done": `./scripts/check.sh`.
  Run it after every step that changes tests or implementation.
- Prefer the smallest diff that satisfies the contract; change only the files
  the task requires.
- This skill is intentionally generic across features so it can drive both
  `unsubscribe(name)` (Feature A) and `is_subscribed(name)` (Feature B) with
  the same loop.
