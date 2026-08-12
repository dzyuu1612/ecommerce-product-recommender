## What this changes

<!-- One or two sentences. -->

## Why

<!-- The problem it solves. Link the issue if there is one. -->

## How it was verified

<!-- Be specific. "Ran the tests" is not enough on its own — say what you
     actually exercised, and paste output where it helps. -->

- [ ] `pytest tests -q` — result:
- [ ] New behaviour is covered by a test that fails without this change
- [ ] `node --check web/app.js` (if frontend touched)
- [ ] Checked at 375px and 1440px (if frontend touched)
- [ ] Checked in both light and dark themes (if frontend touched)
- [ ] No console errors (if frontend touched)
- [ ] Contrast measured for any new colour (if tokens touched)

## Documentation

- [ ] Updated, or not needed because:

## What this does NOT cover

<!-- Known gaps, deferred work, things you chose not to handle. This is the
     most useful section for a reviewer — an empty one is suspicious. -->

## Claims

If this PR adds a claim to the docs (a number, a compliance statement, a
performance figure), state how it was measured:

<!-- e.g. "1.49 GB measured with `docker images`, down from 8.03 GB" -->
