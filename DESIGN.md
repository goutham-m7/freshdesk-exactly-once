# Design and interview notes

## Problem and scope

A receiver can commit a replacement order and lose its acknowledgement. A webhook
retry is then indistinguishable from a first delivery without durable identity.
The [2021 solved Freshworks thread](https://community.freshworks.com/ticketing-agent-productivity-11362/webhook-called-twice-5min-apart-21958)
records a 504 followed by a five-minute retry. It does not establish a present bug.
This is an original standalone replay experiment; no employer code, customer data,
or Freddy internals are used. No real refunds, orders or replies are sent.

## Three hard decisions

1. **Logical action identity, not ticket identity.** Key synthetic actions by tenant,
   ticket ID, conversation ID, source revision and action kind. Canonical JSON plus
   SHA-256 removes delimiter ambiguity. Changed payload under an existing identity
   is a conflict. Rejected: ticket-only keys (drop legitimate updates), delivery
   UUIDs (change on retry), full-body identity hashes (changed payload executes twice).
   Revision is caller-supplied immutable identity, NOT an asserted Freshdesk webhook
   field. Production needs a business authorization ID if multiple revisions can
   authorize the same operation. This demo treats revisions as distinct actions.
2. **Transactional intake/outbox plus downstream idempotency.** One SQLite transaction
   records receipt and work before acceptance. The order simulator has its OWN DB
   and atomically commits key plus order. Rejected: local dedupe alone (crash gap),
   imaginary cross-system transactions. Exactly one SIDE EFFECT requires downstream
   cooperation. Delivery remains at least once. Without durable downstream keys,
   reconcile ambiguous outcomes; do not blindly retry. Both comparison paths use
   real SQLite inserts; the naive one intentionally omits downstream keys.
3. **Leased, fenced claims.** BEGIN IMMEDIATE serializes claims. Claim tokens fence
   late acknowledgements; expired work is reclaimed. Remote work happens outside
   transactions. Rejected: holding locks across network calls, volatile queues,
   marking done before sending. A child process really exits after remote commit.
   Short leases make the demo quick; they do not model Freshdesk's retry schedule.

## Interfaces and data flow

TicketAction -> Store.accept -> durable pending -> Worker.run_once ->
OrderSystem.execute(key, payload) -> Store.finish(token). Acknowledgement timeouts
leave pending work; crashes leave leased work until expiry. Action choice is a
synthetic deterministic replacement request; there is no LLM dependency.

## Failure and security boundaries

Malformed/unknown fields fail before writes. Conflicting keys fail closed. Only
acknowledgement timeouts auto-retry; other failures propagate, leaving expiring
leases. SQLite lock waits are bounded. State is synthetic and local. The optional
loopback UI is not a webhook ingestion service: no authentication, secrets, API
client, PII or arbitrary filesystem routes. It serves fixed assets and bounded
scenarios, rejecting foreign origins/hosts. Never expose it publicly. Retain keys
beyond the entire replay horizon; the lab retains them for each temporary run.

## At 100x scale

Use PostgreSQL unique keys and SKIP LOCKED claims; retain transactional intake.
Partition by tenant; add quotas, bounded backoff, dead-letter review, versioned
schemas and policies, reconciliation export and durable key retention. Downstream
key TTL and payload conflict behavior must be documented. A distributed lock is
not a replacement for downstream atomic idempotency. The lab has one action per
event, no per-ticket ordering, retry budget or global exactly-once delivery claim.
Ephemeral demo databases need no migration; deployed persistent databases would.

## Verification contract

| ID | Observable assertion | Proof |
|---|---|---|
| EC-1 | 100 redeliveries: naive 100 extra orders; safe zero | CLI capture + SQLite tests |
| EC-2 | Two distinct updates produce two additional orders | SQLite tests + demo |
| EC-3 | Restart after committed order and process death does not duplicate | Real subprocess test + demo |
| EC-4 | Changed payload under same identity is rejected | SQLite tests |
| EC-5 | Parallel intake/claims and stale completion cannot duplicate | SQLite tests |
| EC-6 | Drag timeout or keyboard button to run timeline | Browser capture + HTTP tests |

## Execution and test strategy

Build identity, transactional intake, downstream contract, worker/restart, CLI,
then timeline. Write pytest behavior tests before each module. Use real temporary
SQLite files, real subprocess crashes and real loopback HTTP tests. Inject clocks
only for exact lease-boundary tests. Do not mock databases or internal functions.
Live Freshdesk compatibility, API permissions, real money and Freddy quality are
not tested: no account is assumed and those integrations are not built.

## Reuse decision

The spec names replaylab/agentprobe concepts but supplies no licensed public code
location; none exists in this empty repo. No code is copied or claimed integrated.
This original fault runner implements only commit/acknowledgement replay. Public
[REST docs](https://developers.freshdesk.com/api/) inform identifiers; optional
GET /api/v2/tickets/{id} and /api/v2/tickets/{id}/conversations are not implemented.
