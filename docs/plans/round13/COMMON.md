# Round 13 rules (on top of ../round12/COMMON.md)

1. Follow `docs/plans/round12/COMMON.md` in full, with your branch and decision block from `README.md` here. Create your branch from `origin/phase7b-stage2` (it now holds all of round 12).
2. STOP SIGNAL: before starting each item run `git ls-remote --heads origin control/stop`. If it prints anything, the owner's usage limit is near: commit and push what is finished, write and push your `docs/plans/round13/REPORT_<letter>.md`, and stop at once. Do not start another item.
3. Many items are partly done; their PLAN.md line says what is left. Build only what is left.
4. Push after every item, so nothing is lost if the session is stopped.
5. Messages need a next-step verb the checker knows: run `tests/core/test_message_next_steps.py` and `tests/ui/test_error_message_steps.py` after adding messages.
