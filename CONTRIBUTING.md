# Contributing

Thanks for taking a look. This document covers how to get set up, what "done"
means here, and the conventions the codebase follows.

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

- [Ways to contribute](#ways-to-contribute)
- [Getting set up](#getting-set-up)
- [Definition of done](#definition-of-done)
- [Code conventions](#code-conventions)
- [Testing expectations](#testing-expectations)
- [Frontend conventions](#frontend-conventions)
- [Documentation expectations](#documentation-expectations)
- [Commits and pull requests](#commits-and-pull-requests)
- [Scope: what this project is not](#scope-what-this-project-is-not)

---

## Ways to contribute

| Type | Start with |
|---|---|
| Bug report | An issue with reproduction steps and what you expected |
| Feature idea | An issue **before** a PR — scope is deliberately narrow (see below) |
| Documentation | Straight to a PR |
| Code | An issue first for anything non-trivial |

---

## Getting set up

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

python -m recsys_lite.generator
python -m recsys_lite.features
python -m recsys_lite.train
pytest tests -q
```

Full detail in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

---

## Definition of done

A change is ready when **all** of these hold:

- [ ] `pytest tests -q` is green
- [ ] New behaviour has a test that would fail without the change
- [ ] Touched frontend passes `node --check web/app.js`
- [ ] Frontend changes verified at **375px and 1440px**, in **both themes**,
      with **no console errors**
- [ ] Documentation updated in the same PR if behaviour changed
- [ ] No new dependency without justification in the PR description
- [ ] Claims in docs are measured, not estimated (see below)

### On claims

This project holds itself to stating only what it has verified. If you write
"meets WCAG AA", measure it. If you write "82% smaller", show both numbers. If
something is uncertain, say so — the README's *Known limitations* section
exists precisely so uncomfortable facts have a home rather than being quietly
dropped.

A PR that softens a claim because it turned out to be false is welcome. A PR
that keeps the claim and hides the failure is not.

---

## Code conventions

**Python**

- Python 3.11+, `from __future__ import annotations`, modern type hints
- 4-space indent, ~100-column soft limit
- `snake_case` functions, `PascalCase` classes, `UPPER_SNAKE` constants
- Comments explain **why**, not what. If a line needs a comment to say what it
  does, rename something instead.
- No new runtime dependency without a strong reason — the current five are
  deliberate

**Docstrings** are for modules and non-obvious functions. Say what a thing is
for and what its invariant is, not a restatement of the signature:

```python
def build_training_examples(conn, *, hard_negative_fraction: float = 0.5):
    """Emit point-in-time training rows.

    `hard_negative_fraction` controls how many negatives come from the *same
    category* as the positive — near-misses the model has to actually learn to
    tell apart. Pure uniform sampling inflates offline AUC because most
    negatives are trivially separable.
    """
```

---

## Testing expectations

Tests live in `tests/`, mirroring the module under test.

**Name the guarantee, not the number.**

```python
# yes
def test_event_batch_rejects_the_whole_order_if_any_item_is_unknown(): ...
# no
def test_batch_2(): ...
```

**Test the invariant, not the implementation.** The valuable tests here assert
things like "a training row's history never contains the event that produced
it" — those keep holding when the code is refactored.

**Use the real fixture.** `serving_env` in `tests/conftest.py` runs a genuine
generate → features → train → serve cycle. Serving tests run against a really
trained model, which is why they catch integration problems mocks would not.

```python
from fastapi.testclient import TestClient

def test_catalog_respects_the_limit(serving_env):
    with TestClient(serving_env.app) as client:
        assert len(client.get("/api/catalog?limit=3").json()) <= 3
```

---

## Frontend conventions

No build step, no dependencies, no framework. Keep it that way.

- Escape every interpolated value with `esc()`
- One icon family — add paths to `web/icons.js`, 24×24 viewBox, 1.5px stroke,
  `currentColor`, no fills. **Never an emoji as an icon.**
- Never a raw hex in a component — use a semantic token
- Reserve layout with `aspect-ratio` and correctly sized skeletons
- Capture DOM references **before** an `await`; `e.currentTarget` is null once
  dispatch ends
- Collapsing grid tracks use `minmax(0, 1fr)`, including inside media queries
- Every interactive element: ≥44px on coarse pointers, a visible focus ring,
  and a label if it is icon-only

New colours must be checked for contrast in both themes before merge; the
measured table lives in [docs/DESIGN-SYSTEM.md](docs/DESIGN-SYSTEM.md).

---

## Documentation expectations

| You changed | Update |
|---|---|
| An endpoint | [docs/API.md](docs/API.md) |
| A user-visible flow | [docs/BUSINESS-FLOW.md](docs/BUSINESS-FLOW.md) |
| Anything touching who may call what | [docs/AUTHORIZATION.md](docs/AUTHORIZATION.md) |
| A component or token | [docs/DESIGN-SYSTEM.md](docs/DESIGN-SYSTEM.md) |
| A module boundary | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| A CLI flag or env var | [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) |
| Anything about running it in anger | [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) |
| Reused outside material | [THIRD_PARTY.md](THIRD_PARTY.md) |

---

## Commits and pull requests

**Commits** — imperative mood, explain the why in the body:

```
Fix cold-start scores clustering near 1.0

features.py requires min_history=1, so no all-padding sequence ever
appears in training. The model has no signal to discriminate on and
outputs uniformly high scores. Adds a configurable share of
empty-history rows to the training set.
```

**Pull requests** should say what changed, why, how you verified it, and what
you did **not** cover. That last part is not a weakness — it is what makes a
review useful.

Small and focused beats large and sweeping. A PR that fixes one thing well is
easier to review, and easier to revert.

---

## Scope: what this project is not

recsys-lite is a **vertical slice**: it demonstrates the whole path from event
capture to serving, at a size one person can read in an afternoon. Several
things are missing **on purpose** — the substitution table in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#what-stands-in-for-what) lists
them.

Contributions that make the slice sharper are very welcome:

- Harder negative sampling, better evaluation
- Fixing a documented limitation (cold-start calibration is the standout)
- Accessibility and UX improvements
- Clearer documentation

Contributions that turn it into a platform are likely to be declined:

- Swapping SQLite for a database server
- Adding Kafka, Airflow, Kubernetes manifests, a feature-store service
- A frontend framework and build pipeline

If you want that system, this repository is a reasonable map of it — but it is
not trying to become it. Open an issue and let's talk before writing the code.

### The one exception worth naming

[docs/AUTHORIZATION.md](docs/AUTHORIZATION.md) contains a **designed but
unimplemented** role model. That document exists so the boundary has a known
shape, not as a commitment to build it — the demo deliberately ships without
auth, and the missing boundary is documented rather than hidden.

If you want to implement it, that is a genuinely welcome contribution, but
**open an issue first**: it touches every endpoint, it needs a decision about
where identity comes from, and it would change the project's "run it in thirty
seconds" character. Please follow the shape in that document rather than
inventing a parallel one.
