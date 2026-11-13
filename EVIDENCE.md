# Observed verification

## Clean clone

Verified code revision `e577d44` from a fresh local `git clone --no-hardlinks` into
an independently created directory under `/tmp`. The only later change is this
evidence record. No remote push, hosted CI, package publication, company account,
company API call or real financial/customer action was performed.

Observed runtime: Python 3.15.0 on macOS arm64. The committed Linux Python
3.11/3.13 CI matrix has not been run on hosted infrastructure.

| Command, run inside the clean clone | Observed result |
|---|---|
| `python3 -m venv .venv` then install `requirements-dev.txt` | Installed all five pinned test packages |
| `.venv/bin/python -m pytest -q` | **61 passed in 7.33s** |
| `.venv/bin/python -m replay demo` | naive duplicates 100; safe duplicates 0; distinct updates 2/2; safe total orders 3 |
| same demo, recovery output | **93.43 ms**, leased → done, one downstream order |
| `.venv/bin/python -m compileall -q replay extensions` | Exit 0 |
| `node --check replay/static/app.js` | Exit 0 |
| Optional real Replaylab SDK: `python -m pytest integration -q` | **1 passed in 0.03s** |
| Optional real Replaylab SDK: `python -m extensions.replaylab_freshdesk` | 3 steps recorded, 3 replayed, 0 extra effects, 2 original orders; both runs completed |

The optional SDK commands used an explicit source path to the separate personal
Replaylab checkout at commit `45cb064407515881ccd5196f2fe056aa974ea8d5`.
No SDK source was copied. The core tests require no sibling checkout. Installing
test dependencies consulted the package cache/index; test/demo execution used
only local data, local subprocesses and loopback HTTP. No LLM was used.

The top-fold README capture is a separate observed run at **107.59 ms**, preserved
verbatim in [evidence/demo.txt](evidence/demo.txt). Timing is machine-dependent,
includes remaining lab lease, interpreter startup and reconciliation, and is not
an SLA or a cross-machine performance comparison.

## Acceptance evidence

| ID | Evidence | Observed assertion |
|---|---|---|
| EC-1 | `tests/test_scenario.py::test_comparison_counts_and_legitimate_updates`; CLI capture | 100 redeliveries create 101 naive orders, 1 safe order; extra effects 100 versus 0 |
| EC-2 | same test; `tests/test_store.py::test_distinct_updates_survive_ticket_dedupe` | Two new revisions are accepted on the same ticket; safe final total 3 |
| EC-3 | `tests/test_worker.py::test_real_process_death_after_remote_commit_recovers`; `tests/test_cli.py::test_recovery_metric_observes_a_new_process` | Child exits 75 after durable remote commit, local state remains leased; a new child finishes without a second order |
| EC-4 | `tests/test_store.py::test_changed_payload_rolls_back_receipt_and_outbox`; `tests/test_orders.py::test_downstream_refuses_changed_payload` | Both boundaries reject changed payload under an existing key |
| EC-5 | `tests/test_store.py::test_parallel_deliveries_create_one_outbox_row`; `tests/test_leases.py::test_only_one_parallel_worker_claims`; `test_expired_claim_recovered_and_old_token_fenced` | Concurrent deliveries yield one accepted action; one claim wins; stale token cannot acknowledge new claim |
| EC-6 | Browser exercise below; `tests/test_web.py` | Drag and keyboard button both run the actual runner; JSON download contains matching receipts/ledgers |

Rollback, quoted identifiers and downstream conflicts also passed in
`tests/test_fail_closed.py`, using real SQLite rather than mocked transactions.

## Browser exercise

Used a dedicated local Chrome process, not the user's signed-in session.

- Desktop at 1440 px: dragged `#fault` onto `#run`, waited for completion, observed
  `101 orders / 100 duplicates` versus `1 order / 0 duplicates`.
- Mobile at 390 px: reloaded, focused the run button and pressed Enter. Observed
  completion and document width/scroll width **390/390**, with only the ledger
  table horizontally scrollable. Browser error list was empty.
- [Desktop full-page capture](evidence/desktop.png) and
  [mobile keyboard-run capture](evidence/mobile.png) show the completed experiment.
- Repeated drag on a server started from the clean clone. Downloaded the actual
  **45,097-byte JSON** export and read it: duplicates 100/0, 103 receipts, 3 actions,
  recovery leased → done, one downstream order (that run measured 97.04 ms).
- The frontend mechanical detector returned an empty findings array.
- Stopped both local servers and released the dedicated browser after verification.

## Boundaries and review

All ticket/action content is synthetic. The order system is a deliberately mocked
external service implemented with real, independent SQLite persistence. Its
atomic idempotency promise is an explicit assumption, not a tested Freshdesk
feature. Freshdesk live reads, authentication, Freddy internals, real financial
actions, production deployment and Linux runtime behavior were not exercised.

No independent review agent was used: the assignment prohibits subagents.
In-thread review checked the uncertain-commit gap, identity scope, transaction
rollback, stale lease fencing, downstream conflict handling, fixed-file HTTP
routes, loopback Host/Origin restrictions and the stated limitations. This is not
an independent code-review approval or a production-readiness claim.

Before the final documentation commit, a repository source scan for absolute
home-directory paths, private-key headers and common API-token/secret patterns
returned no matches. This was a targeted pattern scan, not a comprehensive audit.
