# AWS Serverless Backend Design — Summary Tool (V1)

This document specifies the concrete AWS backend for the summary tool, building on the pipeline
trace in `PIPELINE_FLOW_DETAILED.md` and the party-identity/tokenization design in that document's
Part 3. It is written before implementation begins, per the walkthrough sequence: scope → trust
boundary → job contract → AWS-side pipeline mapping → resource inventory → mono-repo/CI structure
→ open items.

---

## 1. V1 Scope Statement

- **Tool**: summary tool only. Redline tool's AWS migration is deferred to a later phase and is not
  addressed by this document.
- **Deployment model**: serverless backend on AWS, owned and operated by us. SeedJura hosts the
  front-end UI and a local/on-prem component that performs ingestion, PII/party-identity
  resolution, and tokenization before any network call to AWS (see Section 2).
- **Document-set scope**: a single uploaded folder is treated as one document set (one matter/one
  lease's history). General-purpose grouping of unrelated documents bulk-uploaded together is
  explicitly out of scope for V1 (per `PIPELINE_FLOW_DETAILED.md` §3.6). Early users are assumed to
  be attorneys curating a folder per matter.
- **Party-identity protection scope**: tokenization covers the two legal parties to the agreement
  (e.g. Landlord/Tenant) plus guarantors (individuals with personal obligations under the
  agreement) — i.e., all parties actually bound by/affected by the agreement. Notaries, witnesses,
  brokers, lenders, and other non-party individuals mentioned in passing are out of scope for V1
  (per `PIPELINE_FLOW_DETAILED.md` §3.2, refined in this session).
- **Identifying-data scope**: names, addresses, SSNs, EINs, phone numbers, emails, and account
  numbers belonging to the in-scope parties are tokenized. Dollar amounts, dates, and substantive
  clause language are not tokenized — they are needed for interpretation and do not identify
  anyone.
- **Model**: AWS Bedrock, model selection left flexible/swappable (per this session's decision) —
  the AWS-side pipeline must not hard-code assumptions specific to one model family.
- **No AWS-hosted general-purpose PII detection service (e.g. Amazon Comprehend) or Bedrock
  Guardrails is used as a redaction mechanism**, because both require sending content to an AWS API
  to be inspected — which would mean unredacted client content reaching AWS before redaction is
  complete, defeating the purpose. All identity resolution and tokenization happens locally, on
  SeedJura's server, using logic that makes no network call. (This corrects a mid-session proposal
  to reuse Entrephy's Comprehend/Guardrail-backstop pattern — that pattern is valid for Entrephy's
  own use case, where content originates from parties who consent to AWS processing, but is not
  portable here given the local-only constraint.)

---

## 2. Trust Boundary — What Crosses the Network, and What Never Does

This is the section the rest of the design is downstream of. Stated as plainly as possible:

**Everything below happens on SeedJura's server, before any AWS call is made:**
- Document ingestion (PDF/DOCX extraction, OCR fallback)
- Document-set ordering (oldest/newest resolution)
- Party-identity resolution (recital + signature-block cross-check against the origin document,
  assignment/successor check against the newest document)
- Gap handling (documents with no recoverable identity inherit the set's resolved identity;
  conflicting identity escalates to local human review; duplicate detection)
- Full tokenization of all in-scope identifying data, document-set-wide
- Building and holding the token↔real-value mapping table

**Only tokenized content crosses to AWS.** AWS never receives:
- The original, untokenized document text
- Real party names, addresses, SSNs, EINs, phone numbers, emails, or account numbers for any
  in-scope party
- The token↔real-value mapping table itself

**AWS performs, on tokenized content only:**
- Call 1 (extraction), Call 2 (interpretation), retry calls, Call 4 (QA feedback) — via Bedrock
- Structural verification equivalent to today's `verify_and_expand()` (exact/fuzzy/anchor matching
  against the tokenized source text) — this can run on either side, see open question in §7, but
  since it never needs real identity to function (it matches against whatever text it's given,
  tokenized or not), it is not a boundary-relevant decision on privacy grounds — only on latency/
  cost grounds.

**Only tokenized results cross back from AWS.** The callback payload contains tokens
(`LANDLORD_NAME`, `TENANT_ADDRESS`, etc.), never real values. Reconstruction happens exclusively on
SeedJura's server, using the locally-held mapping table, and only at final output-generation time
— never on any intermediate payload, matching the same discipline Entrephy's `rehydrate_tokens()`
uses ("used exclusively at final report-rendering time — never on intermediate AI-facing
payloads") even though that specific module is not being reused here.

**Consequence for AWS's data-handling posture**: because AWS never receives real identifying
information for the in-scope parties, there is no reliance on Bedrock's data retention policy for
that specific concern — the privilege-sensitive fact (who the parties are) is never present in
what AWS/Bedrock ever sees. Bedrock's own data handling still matters for other reasons (general
data governance, contract terms with AWS) but is no longer the control that this specific privilege
concern depends on.

**What this means is NOT protected by this design, stated explicitly so it isn't assumed away:**
- Substantive clause language, dollar amounts, and dates are sent to AWS/Bedrock in full — this is
  necessary for the tool to function (extraction/interpretation requires reading the actual terms)
  and is a deliberate, accepted scope boundary, not an oversight.
- Non-party individuals (notaries, lenders, notice recipients, etc.) are not tokenized in V1 and
  their names/details, if present in the document, are sent to AWS/Bedrock along with the
  substantive text (per the V1 scope decision in §1).
- If party-identity resolution fails silently (resolves confidently but wrongly, with no
  corroboration mismatch to trigger escalation), that party's real identity could reach AWS
  untokenized. This is a real residual risk inherent to any code-based resolution mechanism and is
  the reason `PIPELINE_FLOW_DETAILED.md` §3.3's confidence gate is deliberately conservative
  (requires corroboration to silently accept) and why a real test pass against a broader document
  sample (open item from this session, not yet done) matters before this runs unsupervised in
  production.


---

## 3. The Local Component — What We Give SeedJura

**Division of responsibility** (settled this session):
- **We provide**: the extraction + redaction/tokenization component — a versioned zip SeedJura
  installs and runs on their Windows Server — plus our own AWS-side APIs (Section 5+).
- **SeedJura provides**: their own API, their own database queries (e.g. the provisions/rules data
  already stubbed in `seedjura_api`), and the UI (either their own build, or improving ours).
- **This is a joint venture, not a one-time handoff** — we remain heavily involved. The zip-based
  distribution model is chosen for simplicity of installation and maintenance, not as a way to
  disengage after delivery.

**Packaging**:
- A versioned zip (continuing the existing `delivery/seedjura_psa_standalone_*.zip` pattern), sized
  to just the extraction/redaction/tokenization scope — not the full app.py web-server shape of the
  current standalone tool, since SeedJura is building/owns the UI and their own API layer. What we
  ship needs to be re-scoped from "a standalone FastAPI app with its own UI" to "a component
  SeedJura's own API calls into" — see open question in §3.3.
- Python, matching all existing tooling. No .NET port.
- Prerequisites documented explicitly for a Windows Server install: Python 3.12+, LibreOffice
  (headless, no MS Office dependency), Tesseract OCR (for scanned-PDF fallback), and the Python
  package set already in `requirements.txt` (`fastapi`/or a slimmer interface if re-scoped per
  §3.3, `python-docx`, `pymupdf`, `pytesseract`, `thefuzz`, `python-Levenshtein`, `Pillow`).
- Process supervision left to SeedJura's preference, since "simplest to maintain" was the stated
  priority and this is low-stakes — a Windows Service wrapper (e.g. via `nssm` or a minimal
  Python-as-a-service wrapper) is the most typical "make a Python process durable on Windows
  Server" pattern if they want one; a manually-started/Task-Scheduler-launched process is also
  workable for V1. Not prescribed further in this document — SeedJura's own ops preference governs.

### 3.1 What the local component must do

Per `PIPELINE_FLOW_DETAILED.md` Part 3, executed entirely locally, no network call to AWS until
the final step:

1. **Ingest**: PDF/DOCX extraction, OCR fallback for scanned pages (existing
   `lease_summary_tool.ingest_document()` logic).
2. **Document-set ordering**: resolve oldest (origin) and newest (current) document in the set
   (existing `sort_documents()` logic, reused as-is).
3. **Duplicate detection**: collapse version-hash duplicate files before ordering/resolution runs
   (new — per `PIPELINE_FLOW_DETAILED.md` §3.6).
4. **Party-identity resolution**: recital + signature-block cross-check against the origin
   document; assignment/successor check against the newest document; conservative confidence gate
   (new — per `PIPELINE_FLOW_DETAILED.md` §3.3-3.4). Scope: the two legal parties + guarantors.
5. **Gap handling**: documents with no recoverable identity inherit the set's resolved identity and
   are logged as such; conflicting identity escalates to local human review (via SeedJura's own UI,
   since we don't own that layer); documents with no extractable text are OCR-retried, then
   included with a "content not processed" flag if still empty (new — per §3.6).
6. **Full tokenization**: replace every occurrence of the resolved parties' names, addresses, SSNs,
   EINs, phone numbers, emails, and account numbers with stable tokens, document-set-wide (new —
   per §3.2).
7. **Mapping table**: build and hold the token↔real-value map locally, scoped to this document set
   only. **Never transmitted to AWS.**
8. **Call AWS** (Section 4) with the tokenized document text and job metadata.
9. **Receive AWS's tokenized results** and **reconstruct** real values into the final field
   data/output using the locally-held mapping table (existing `build_field_variants()` /
   `populate_template()` logic, operating on now-detokenized data) — this final reconstruction step
   happens locally, per the trust boundary in Section 2.

### 3.2 What already exists vs. what's new

| Capability | Status |
|---|---|
| PDF/DOCX ingestion, OCR fallback | Exists (`lease_summary_tool.py`) — reusable as-is |
| Document-set ordering (`sort_documents`) | Exists (`multi_file.py`) — reusable as-is |
| Party-identity resolution (recital/anchor/signature-block) | **New** — designed in this session, not yet implemented |
| Duplicate detection | **New** — designed in this session, not yet implemented |
| Gap handling (inherit/escalate/OCR-retry logic) | **New** — designed in this session, not yet implemented |
| Full tokenization (names/addresses/SSN/EIN/phone/email/account) | Partially exists — `redactor.py`/`redaction.py` cover the structural-regex categories; role-aware party tokenization is **new** |
| Mapping table build/hold/reconstruct | Exists in spirit (`pii_mapping` in both tools' redaction modules) — needs to be scoped to document-set (not per-single-document) and extended to cover the new tokenization categories |
| Field extraction/interpretation/QA (Calls 1/2/4) | Exists (`engine.py`) — this moves to AWS (Section 4), not part of the local component |

### 3.3 Open question: how does SeedJura's system actually invoke this component?

Not yet decided, and it changes the packaging shape materially:

- **Option A — CLI/library invocation.** The zip ships a Python package with a clear function/CLI
  entrypoint (`process_document_set(folder_path) -> TokenizedResult`). SeedJura's own API/backend
  shells out to it or imports it directly. Simplest to package, but requires SeedJura's stack to
  either run Python directly (invoking a script) or wrap it (e.g. their .NET API shells out to a
  Python process per job).
- **Option B — Local HTTP service.** The zip ships a thin local web server (much smaller than
  today's full `app.py`, since SeedJura owns the real UI/API — this would just be an internal
  endpoint like `POST /extract-and-tokenize` that SeedJura's own API calls over localhost). Keeps
  the interface language-agnostic from SeedJura's side (any stack can make an HTTP call) at the
  cost of running a persistent local process.

**Decision (this session): Option B — local HTTP service.** The zip ships a minimal FastAPI/
uvicorn app (much smaller than today's `app.py`, since SJ owns the real UI/API — this is just an
internal endpoint, e.g. `POST /extract-and-tokenize`, that SJ's .NET API calls over localhost).

Rationale, weighed against Option A (CLI/library invocation, SJ's .NET process shells out to
Python):

- **Process lifecycle**: Option A pushes subprocess spawn/monitor/timeout/crash-handling into SJ's
  own .NET code, on every request, with real per-call cold-start overhead (Python interpreter
  startup + importing `pymupdf`/`pytesseract`/etc. each time). Option B pays that cost once, at
  service startup, not per job.
- **Data handoff**: Option A's natural mechanisms (CLI args, stdin/stdout, or shared temp files)
  are awkward for a whole document set plus a growing token-mapping table. Option B uses a normal
  REST payload — the same shape SJ's .NET code already needs for calling AWS.
- **Diagnosability**: Option B's failure modes are boring and obvious (service down → connection
  refused → fix is "make sure the service auto-restarts"). Option A's failure modes are the kind
  that surface intermittently and are hard to root-cause (a subprocess spawn failing weeks later
  due to environment drift on SJ's box).
- **Health checks**: trivial in Option B (`GET /health`), awkward to construct meaningfully in
  Option A.
- **Clean separation of codebases**: Option B keeps our code and SJ's code as genuinely separate
  running processes, not just logically separate modules — neither side imports or embeds the
  other's code, and upgrades on either side don't require touching the other's build. This matters
  specifically because this is a joint venture with two parties each maintaining their own IP; a
  process-level boundary keeps that separation real, not just conventional.

Trade-off accepted: someone must keep the local service running (the process-supervision question
from §3, now a hard requirement rather than a nice-to-have) and the port/firewall implication of
"a new local service exists on SJ's server" needs to be visible to their own IT/security review —
judged worth it given the above.


---

## 4. The Async Job Contract Between SJ and AWS

Naming convention for this section and going forward: **SJ** = SeedJura's server (web app on
IIS, owns the UI, their own API, and the local extraction/redaction component we provide as a
library they invoke). **AWS** = our serverless backend.

### 4.1 High-level flow

1. User opens the web app on SJ, uploads a document or folder.
2. SJ runs the local extraction/redaction component (Section 3) — ingestion, ordering, party-
   identity resolution, tokenization. This is entirely local; no network call yet.
3. **SJ → AWS: `POST /jobs`** with the tokenized document set + job metadata. This is the only
   point at which content crosses the network in this direction.
4. **AWS → SJ: synchronous ACK** (`202 Accepted` with a job identifier) — confirms receipt only,
   no processing has happened yet.
5. AWS processes the job asynchronously (Section 5): Call 1 extraction, verification, Call 2
   interpretation, completeness/retry, Call 4 QA — all against tokenized text.
6. **AWS → SJ: `POST` to a callback URL** with the completed structured JSON field data (tokens
   still in place — AWS never resolves tokens back to real values, per the trust boundary in
   Section 2).
7. **SJ → AWS: synchronous ACK** for the callback — confirms receipt only.
8. SJ detokenizes the field data using its locally-held mapping table (plain string substitution
   on structured JSON values, not on any document/XML format), then runs the existing local
   `populate_template()` / `xml_export` logic to produce the final Word/XML/JSON deliverables and
   presents the summary to the user in its own UI.

**Decision (this session): AWS's callback payload is structured JSON field data only — not a
generated Word document, XML file, or any other rendered artifact.** SJ is responsible for
generating all final deliverables locally, after detokenization. Rationale: keeps the
trust-boundary-sensitive reconstruction step (real names replacing tokens) as plain, auditable
substitution on structured data, rather than token-replacement inside a DOCX's XML run structure —
avoiding the same class of run-splitting fragility the existing `_replace_in_paragraph()` code
already has to work around for ordinary template placeholders. This does mean SJ's local component
carries the document-generation responsibility (reusing the existing `populate_template()`/
`xml_export.py` logic), not AWS.

### 4.2 Correlation / job identity

- **SJ generates the job identifier** (a UUID) and includes it in the initial `POST /jobs` request.
  AWS's ACK echoes it back for confirmation; AWS's later callback POST includes the same identifier
  so SJ can match the callback to the pending job. SJ generating the ID (rather than AWS) means SJ
  never has to wait on AWS's ACK before it can start tracking the job locally — it can persist
  "job {id} submitted, awaiting callback" the instant it sends the request.
- This identifier is a **job ID, not a document-identifying value** — it carries no PII and is safe
  to log/trace on either side without touching the trust boundary.

### 4.3 Idempotency and retry

- **SJ → AWS submission retries**: if SJ's initial POST fails to get an ACK (timeout, network
  blip) and retries, AWS must treat a repeated `POST /jobs` with the same job ID as a no-op if that
  job ID is already known (return the existing ACK/status rather than reprocessing or double-
  billing Bedrock calls). AWS's job-state store (Section 5) is the natural place to enforce this —
  a conditional write keyed on job ID.
- **AWS → SJ callback retries**: if AWS's callback POST doesn't get an ACK from SJ (SJ briefly
  down, network blip), AWS retries with backoff up to a bounded number of attempts, then routes to
  a dead-letter path for manual/alerted follow-up rather than silently dropping a completed job's
  result. SJ's callback handler must be idempotent — if AWS retries a callback SJ actually already
  received (but failed to ACK in time), reprocessing it a second time on SJ's side must not
  duplicate the summary/output.
- **Failure visibility**: SJ needs a way to know a job has failed outright (not just "still
  processing") — e.g. AWS's callback includes a status field (`complete` | `error`), and a bounded
  overall job timeout on SJ's side (if no callback arrives within N hours, surface as
  stalled/failed to the user rather than waiting indefinitely) is a reasonable local safeguard
  independent of whatever AWS-side retry logic exists.

### 4.4 Request/response shapes (draft — to be refined against actual field lists)

**`POST /jobs` (SJ → AWS)**
```json
{
  "job_id": "uuid",
  "job_type": "summary | redline",
  "agreement_type": "lease | psa | nda | ...",
  "submitted_at": "ISO-8601 timestamp",
  "document_count": 4,
  "documents": [
    { "filename": "...", "text": "<tokenized full text>", "doc_type": "lease | amendment | ...", "execution_date": "mm/dd/yyyy | null" }
  ],
  "callback_url": "https://sj-host/api/jobs/callback"
}
```
- `documents[].text` is the tokenized text only — never raw. Tokens follow the naming convention
  from `PIPELINE_FLOW_DETAILED.md` §3 (`LANDLORD_NAME`, `TENANT_ADDRESS`, etc.) plus the general
  structural categories (`{{PII_SSN_1}}`-style, or an equivalent convention — to be finalized
  against whatever the local component actually emits).
- `documents[].doc_type` / `execution_date` are passed through from SJ's already-completed local
  ordering step (Section 3.1, step 2) — AWS does not need to re-derive document ordering, since
  that's a local, content-based operation already done before this call.
- **`job_type`** (added this session): distinguishes which pipeline/state machine this job routes
  to — `"summary"` is the only value V1 actually processes (redline is deferred per Section 1), but
  the field is captured from day one so the `Jobs` table and routing logic don't need a breaking
  schema change when redline's AWS migration begins. The `jobs-receive` Lambda uses this to decide
  which Step Functions state machine to start.
- **`agreement_type`** (already present, now explicitly noted as driving which agreement-type
  config — lease/PSA/NDA/etc. — the extraction and interpretation prompts use, mirroring the
  existing `agreement_types/{type}/config.json` plugin pattern from `PIPELINE_FLOW_DETAILED.md`
  Part 1.3).
- **`submitted_at`** and **`document_count`** (added this session): captured explicitly at the
  entry point rather than only derivable from `documents.length` and the Lambda's own invocation
  time, so they're recorded as first-class fields on the `Jobs` table (Section 5.3) for operational
  querying/reporting (e.g. "how many multi-document jobs did we process last month") without
  needing to reconstruct them from raw payload logs.

**`202 Accepted` (AWS → SJ, synchronous ACK)**
```json
{ "job_id": "uuid", "status": "received" }
```

**`POST {callback_url}` (AWS → SJ)**
```json
{
  "job_id": "uuid",
  "status": "complete | error",
  "field_data": { "Landlord_Name": "{{LANDLORD_NAME}}", "...": "..." },
  "confidence_flags": ["FieldName", "..."],
  "error": null
}
```
- `field_data` values still contain tokens — SJ detokenizes after receiving this.
- `confidence_flags` carries forward the existing low-confidence-field flagging (per the Option C
  decision from earlier in this design conversation — inline flagging, not a blocking review gate).

**SJ's ACK of the callback**: a plain `200 OK` is sufficient; no body contract needed since AWS
only needs confirmation of receipt, not any data back.

> These shapes are a starting draft to make the contract concrete enough to design the AWS-side
> resources against (Section 5). They should be revisited once the actual local-component field
> list, token-naming convention, and confidence-flag mechanics are implemented, not treated as
> final.

### 4.5 Authentication

**Decision (this session): shared API key.** This is a point-to-point integration between two known
parties (SJ and AWS), not a public multi-tenant API — a shared secret is proportionate and simple,
matching the "simplest to do, easiest to maintain" priority stated for this whole design.

- **SJ → AWS**: SJ includes the shared key in a request header (e.g. `x-api-key`) on `POST /jobs`.
  API Gateway's native API key mechanism (Section 5) is the natural fit — no custom auth Lambda
  needed for this direction.
- **AWS → SJ callback**: AWS includes the same or a separate shared key in a header on its callback
  POST to SJ's `callback_url`; SJ's endpoint validates it before accepting the payload. This
  direction is SJ's responsibility to enforce (it's their endpoint), but the key/mechanism should
  be agreed as part of the integration contract, not left implicit.
- **Key rotation**: not designed in detail here (V1 scope), but should not be an afterthought —
  at minimum, the key should live in AWS Secrets Manager on our side (not hardcoded in Lambda
  environment variables in plaintext) so rotation is possible without a code deploy.


---

## 5. AWS-Side Pipeline Mapping and Resource Inventory

### 5.1 Mapping the existing pipeline onto AWS compute

Per `PIPELINE_FLOW_DETAILED.md` Part 1, the steps that move to AWS (everything after tokenized text
arrives via `POST /jobs`) are:

| Existing step | AWS implementation |
|---|---|
| Call 1 — raw extraction | Lambda, invokes Bedrock |
| Source verification (`verify_and_expand`) | Lambda, pure code (regex/fuzzy match against the tokenized text it was given — no privacy implication either way, since it operates on whatever text it receives) |
| Human-verification-pause (handwriting) | **Removed as a blocking pause** — per the earlier design decision in this conversation, becomes inline confidence-flagging in the final callback payload (`confidence_flags`, Section 4.4) rather than a mid-pipeline stall. No AWS-side "waiting" state needed. |
| Call 2 — interpretation | Lambda, invokes Bedrock, batched/parallel (existing `ThreadPoolExecutor` batching logic ports to either parallel Lambda invocations or a Step Functions `Map` state — see 5.2) |
| Completeness check | Lambda, pure code |
| Retry (Call 1 variant) | Lambda, invokes Bedrock, only triggered conditionally |
| Call 4 — QA feedback | **Deferred out of V1's per-job pipeline** — see note below |
| Field-variant construction (`build_field_variants`) | Lambda, pure code |
| Output generation (DOCX/XML/JSON) | **Not on AWS** — per Section 4.1, this is SJ's responsibility after detokenization |

Multi-file/merge-specific steps (document-set ordering, signature gate, classification,
date-role resolution, merge) are **not** on AWS — per Section 3.1, these are already done locally
by SJ before the tokenized text is ever sent. AWS receives a document set that is already ordered
and already merged at the *identity* level; whether AWS still needs the *per-document* text merge
logic (`multi_file.merge_fields()`'s "latest wins" field-level merge across documents) is an open
question — see §5.4.

**Correction (this session) — Call 4 / QA feedback is NOT a per-job pipeline step.** The original
tools' `suggest_improvements()` was framed as "advisory, non-blocking, runs inside every job" —
that framing was carried into this design uncritically. It's wrong for what QA feedback is actually
meant to be: a **self-learning signal that accumulates across many jobs over time** — surfacing
systemic weaknesses in extraction/interpretation quality (e.g. "field X is misread across many
documents of type Y") so the *next version* of the prompts/rules/config improves, not something
that affects the current job's own output. That is a fundamentally different architectural shape
(an offline/batch analysis pipeline reading accumulated job history, not a Step Functions state
inside each job's execution) and is **out of scope for V1**, to be designed properly as its own
system once there's a real corpus of completed jobs to learn from. V1's state machine (§5.2) does
not include a QA-feedback state at all. This is tracked as a future item in §7, not built now.

### 5.2 Orchestration: Step Functions

A Standard Step Functions state machine orchestrates the per-job pipeline, mirroring the pattern
already used in Entrephy's `factory.yaml` SR pipeline (Generate → BruteForce → StoryReview → retry
loop) — same shape, different domain: Extract → Verify → Merge → Interpret → CompletenessCheck →
(retry loop, bounded) → Finalize → Callback. (QA feedback removed from this list — see the
correction above; V1 does not include it.)

Rationale for Step Functions over a single monolithic Lambda:
- Per-step retry/backoff (Bedrock throttling, transient failures) without hand-rolled retry logic
  in application code.
- The conditional retry loop (Call 1 retry, only if completeness check finds gaps) maps directly
  onto a Step Functions `Choice` state, matching the existing `ai_retry_fields()` trigger condition.
- Execution history is a durable, inspectable audit trail per job — useful for the same
  "hand a large enterprise customer's security team a clean execution history" reason flagged
  earlier in this conversation, and matches the existing tools' own audit-logging discipline
  (redline's `{job_id}_audit.json`, summary's `qa_feedback.json`/`report` dict).
- No in-memory job dict (the redline tool's current, non-durable pattern) and no
  reinventing-DynamoDB-polling-plus-threading (the summary tool's current pattern) — durable job
  state lives in the execution history plus a DynamoDB job-status table (5.3), not in a process.

Interpretation batching (existing `ThreadPoolExecutor`, 4 concurrent batches of 30 fields) maps to
a Step Functions `Map` state with a bounded `MaxConcurrency`, invoking one Lambda per batch —
directly analogous to the existing concurrency-bounded design, just expressed as state-machine
parallelism instead of a thread pool.

### 5.3 Job state: DynamoDB

A single `Jobs` table, partition key `job_id`:
- Written on receipt (`POST /jobs` handler): `job_id`, `job_type`, `agreement_type`,
  `status: "received"`, `submitted_at` (from the request payload), `received_at` (AWS's own
  timestamp), `document_count` — enough to satisfy the idempotency check in Section 4.3 (a
  conditional put on `job_id` rejects a duplicate submission) and enough to answer basic
  operational questions (volume by job type/agreement type over time) directly from the table
  without reconstructing them from logs.
- Updated at each Step Functions stage boundary (mirrors the existing `job_meta["phases"]` live
  progress map from the current tools) — useful for our own operational visibility even though SJ
  only sees the final callback, not intermediate status (SJ was not designed to poll AWS per
  Section 4 — the callback is push-based). Worth deciding whether SJ ever needs a status-poll
  fallback endpoint in case a callback is somehow missed entirely despite the retry/dead-letter
  handling in 4.3 — noted as an open item (§7).
- Final state: `status: "complete" | "error"`, timestamp, and enough detail to debug a failed job
  without re-running it.
- TTL: job records should expire after a bounded retention window (not indefinite) — this is
  structured job metadata, not the tokenized content itself, but per the "transient, not retained"
  posture from earlier in this conversation, retention should still be deliberate and short, not
  defaulted to "forever."

### 5.4 Open questions specific to this section

- **Decision (this session): AWS performs the per-field merge.** SJ sends the individual tokenized
  documents in the `documents` array (Section 4.4) — already ordered, already identity-resolved —
  and AWS's Step Functions pipeline runs `merge_fields()`-equivalent logic (latest-document-wins,
  with the existing origin/termination/effective-date pinning rules from
  `PIPELINE_FLOW_DETAILED.md` Part 1.2) as an explicit stage before Call 2 interpretation, since
  interpretation needs the merged current-value view, not per-document values. This is a new
  Lambda in the resource inventory (5.5): `merge-fields`, pure code, no Bedrock call.
- Bedrock model selection (already flagged in this conversation as "we may change the model") —
  the Lambda(s) invoking Bedrock should read the model ID from an environment variable/SSM
  parameter, not a hardcoded string, mirroring Entrephy's `MODEL_ID` pattern in `factory.yaml`'s
  `Globals.Function.Environment.Variables`.

### 5.5 Resource inventory (draft)

| Resource | Purpose |
|---|---|
| API Gateway (REST API) | `POST /jobs` endpoint, API-key-protected (Section 4.5) |
| Lambda — `jobs-receive` | Validates + persists incoming job, starts Step Functions execution, returns ACK |
| Lambda — `extract` | Call 1, invokes Bedrock, run per document in the set |
| Lambda — `verify` | `verify_and_expand`-equivalent, pure code, run per document |
| Lambda — `merge-fields` | `merge_fields()`-equivalent per-field merge across the document set, pure code |
| Lambda — `interpret` | Call 2 batch worker, invoked via Step Functions `Map`, runs on merged current values |
| Lambda — `completeness-check` | Pure code |
| Lambda — `retry-extract` | Call 1 retry variant, invokes Bedrock, conditional |
| Lambda — `finalize-callback` | Builds the final JSON payload, POSTs to SJ's `callback_url`, handles retry/dead-letter |
| Step Functions state machine | Orchestrates the above per job |
| DynamoDB — `Jobs` table | Job state (Section 5.3) |
| S3 — job working-storage bucket | Tokenized document text + large intermediate payloads, referenced by Step Functions via object key (Section 5.7). Short lifecycle policy, encrypted, no public access. |
| SQS — dead-letter queue | Failed callback deliveries (Section 4.3) land here for alerting/manual retry |
| EventBridge | Rules watching DLQ depth / Step Functions failures, routing to SNS |
| SNS | Internal ops alerting only (Section 5.6) — notifies us, not end users |
| Secrets Manager | Shared API key (Section 4.5), Bedrock-related secrets if any |
| Bedrock | Model invocation (extraction/interpretation), model ID externalized via env var/SSM |
| CloudWatch | Logs, and alarms on the dead-letter queue / Step Functions failure rate |
| X-Ray | Distributed tracing across the Lambda/Step Functions/Bedrock chain (Section 5.6) |

This inventory is deliberately serverless end-to-end (no persistent compute, no LibreOffice-on-AWS
dependency, since document generation stays on SJ per Section 4.1) — a materially simpler AWS
footprint than the redline tool would require if/when it migrates, since redline's LibreOffice/
track-changes step has no equivalent here.

### 5.6 Full infrastructure inventory, with rationale for each

Expanding 5.5 into every AWS service under consideration, decided or open, per this session's
walkthrough:

| Service | Role | Status |
|---|---|---|
| **API Gateway** | Single entry point, `POST /jobs`, API-key-protected | Decided |
| **Lambda** | All per-step compute (Section 5.5's list) | Decided |
| **Step Functions** | Per-job orchestration | Decided |
| **DynamoDB** | `Jobs` table — job state, idempotency, operational metadata | Decided |
| **Secrets Manager** | Shared API key (Section 4.5); referenced by name/ARN, never hardcoded | Decided |
| **CloudWatch Logs** | Every Lambda's logs; Step Functions execution history | Decided |
| **CloudWatch Alarms** | Dead-letter-queue depth, Step Functions failure rate | Decided |
| **SQS** | Dead-letter queue for failed callback deliveries (Section 4.3) | Decided |
| **Bedrock** | Model invocation for extraction/interpretation; model ID externalized (env var/SSM) | Decided |
| **IAM** | Per-Lambda least-privilege execution roles; GitHub Actions OIDC deploy role | Decided, not previously called out as its own line item. **Dev-time build access** (this session): a `dev_builder` IAM user in a `dev` group with the AWS-managed `PowerUserAccess` policy was created for early interactive build-out (running AWS CLI commands during this design/build phase). Recorded explicitly as a **temporary dev-convenience choice**, not the target production posture — `PowerUserAccess` is broader than the least-privilege scope this section otherwise describes (touches nearly every service, though it deliberately excludes IAM/Organizations actions). Expect to need a supplementary scoped IAM policy once `sam deploy --capabilities CAPABILITY_IAM` actually runs, since PowerUserAccess's IAM exclusion will block Lambda execution role creation. |
| **CloudTrail** | Account-level audit of management-plane API activity (who touched what in this AWS account, when) — an account/organization baseline control, not a per-job or per-stack resource. Directly answers the "can you show us who has access to this environment" question a large enterprise customer's security review will ask. | **New this session** — should be enabled as an account baseline, not scoped inside `summary.yaml` |
| **S3** | Required (see §5.7) — job-scoped working storage for tokenized document text and any large intermediate payloads, referenced from Step Functions by object key rather than passed inline, to stay under the 256KB per-state-transition limit. Short lifecycle policy, encrypted, no public access. | **Decided — required**, not optional. See §5.7 for sizing rationale. |
| **X-Ray** | Distributed tracing across the Lambda/Step Functions/Bedrock chain — the practical tool for seeing where time and failures actually occur in a multi-step job, beyond what CloudWatch Logs alone shows. | **New this session — recommended**, low cost to add, high value early on for understanding real latency/failure patterns |
| **EventBridge** | Rule(s) watching the DLQ / Step Functions failure events, routing to an actual notification target (see SNS below) rather than relying on someone manually checking CloudWatch | **New this session — recommended** as the alerting glue |
| **SNS** | **Internal ops alerting only** (DLQ depth, Step Functions failure rate, anomalies worth a human looking at) — notifies **us**, not end users. Clarified this session: end-user "your job is done" notification is NOT an AWS-side SNS topic — it's SJ's responsibility, triggered by receiving our callback (Section 4.1), using whatever notification mechanism SJ's own stack has, since SJ owns the UI/end-user relationship (Section 3). | **Decided** — scoped to internal ops alerting only |
| **Bedrock Guardrails** | Reconsidered this session: ruled out as a *redaction* mechanism (requires sending content to AWS to be inspected — conflicts with local-only tokenization), but could still legitimately sit in front of Bedrock purely as a content-safety/quality backstop on already-tokenized text (e.g. preventing a wildly inappropriate model output), since that use doesn't touch the trust boundary at all. | **Open — deliberate yes/no needed**, not decided either way yet |
| **WAF** | Basic protection (rate limiting, common attack patterns) in front of API Gateway. | **Decided — not used.** This is a point-to-point integration with exactly one known, API-key-authenticated caller, not a public-facing API with unknown/adversarial traffic — WAF's threat model doesn't match. |
| **VPC** | Deliberately **not used**. Nothing in this design (Lambda, Bedrock, DynamoDB, API Gateway) requires VPC placement — no RDS, no private-subnet dependency, no need to reach anything on SJ's private network (SJ calls us over the public API; we call SJ's public callback URL). Adding a VPC here would be pure complexity with no corresponding benefit. | **Decided — explicit no** |
| **KMS** | DynamoDB and Secrets Manager both encrypt at rest by default with AWS-owned/AWS-managed keys. Open question: is that default sufficient, or does the sensitivity of what's processed (even tokenized) warrant customer-managed KMS keys for finer-grained control/audit — this is the kind of thing a large enterprise customer's security questionnaire asks about directly. | **Open — not decided** |

**Account-level items** (CloudTrail, and arguably a baseline AWS Config setup for compliance
posture generally) are called out separately because they are not part of `summary.yaml`'s stack —
they're account/organization-wide controls that should exist regardless of which application stacks
are deployed, and typically get set up once, early, rather than per-project.

### 5.7 Why S3 is required, not optional (sizing)

Step Functions enforces a **hard 256KB limit per state-transition payload** (not a soft guideline).
Estimating against realistic documents:

- A single dense commercial lease, as plain text, runs roughly 15,000-40,000 words in the real
  examples examined earlier in this design process (the Coastland Center portfolio, existing test
  documents) — on the order of 100-250KB of raw text per document.
- A realistic document *set* (lease + several amendments) is commonly 4-8 documents. At the high
  end, 8 documents × ~250KB is on the order of 2MB combined for one job.
- Tokenization does not meaningfully shrink text size — replacement tokens (`{{LANDLORD_NAME}}`)
  are often similar length to, or longer than, the values they replace.

**Conclusion: a realistic multi-document job exceeds the 256KB limit by a wide margin.** This is
the expected case, not an edge case, given this design exists specifically to support the
multi-document/amendment-history scenario. S3 is therefore required for V1, not a sizing-dependent
maybe.

**Pattern**: the `jobs-receive` Lambda receives the full payload via API Gateway (API Gateway's own
10MB payload limit is comfortable headroom), immediately writes each document's tokenized text to
S3, and passes only S3 object keys/references into the Step Functions execution input — never the
raw text itself. Downstream Lambdas (`extract`, `verify`, `merge-fields`, `interpret`) read from S3
when they need the text, and write their own intermediate output back to S3 if that output is also
large (extracted/merged field data is likely small enough to pass inline through Step Functions,
but this should be checked against the same 256KB ceiling once real field counts/sizes are known,
rather than assumed).

**This S3 bucket is short-lived job-scoped working storage, not long-term retention** — a
lifecycle policy should expire objects after a short, deliberate window, consistent with the
"transient, not retained" posture established earlier in this design process and with the
DynamoDB TTL decision in Section 5.3. It must be encrypted (SSE-S3 or SSE-KMS — ties into the open
KMS question in 5.6) and have no public access. It should also be a **separate bucket from
whatever CloudTrail logs to** (Section 5.8) — audit logs and transient job data should not share a
bucket, both for lifecycle-policy clarity (very different retention needs) and for security
review clarity (one bucket's purpose should be obvious from its name/policy, not overloaded).

**Decision (this session): this bucket's short retention is not extended for legal-insight/trend-
analysis purposes**, despite S3 storage cost being negligible — cost was never the constraint.
Raised and considered this session: since AWS never holds the token↔real-value mapping (Section
2), tokenized job data retained here is not re-identifiable by us on its own — but V1's tokenization
scope only covers party identity (Section 1); dollar amounts, dates, full clause language, and
non-party individuals' names are sent to AWS untokenized. Retaining that content indefinitely to
mine trends is a materially different activity than "process this job and return a result" — it
is using client data to build a separate data asset, which typically needs its own explicit
consent/contract basis with SeedJura and, transitively, their end clients, rather than being an
incidental side effect of a lenient retention policy. **This capability is not rejected — it is
deliberately folded into the already-deferred self-learning/QA-feedback system (§7, item 10)**,
where it belongs: a separate, explicitly-designed, explicitly-consented-to data product built from
aggregated or de-identified job history (not verbatim retained content in this working-storage
bucket), with its own access controls and retention policy, designed once there's real job volume
and an explicit conversation with SeedJura about consent — not built now as a quiet retention-
policy extension.

### 5.8 CloudTrail configuration (account-level, not part of `summary.yaml`)

Mostly a "configure once, correctly, before any application stack exists" task rather than an
ongoing design concern, but with real decisions inside it:

- **Scope**: an account-level (or Organization-level, if this AWS account sits inside an AWS
  Organization) trail, covering all regions, logging all management events at minimum. Set up as
  one of the first things in the account, not bolted on after application stacks exist.
- **Log destination**: a dedicated S3 bucket, separate from the job-working-storage bucket (5.7).
  Locked down — no public access, versioning enabled, and ideally Object Lock/WORM configuration
  so audit logs cannot be altered or deleted even by someone holding delete permissions on the
  bucket. This specific property (tamper-evidence, not just existence of logs) is what a real
  security review checks for.
- **Data events**: an optional additional layer beyond management events — CloudTrail can log
  individual S3 object-level access and Lambda invocation-level data events. Given the job-working-
  storage bucket (5.7) holds tokenized content, there's a real argument for enabling S3 data-event
  logging on that specific bucket ("who/what read this object, when") as an extra layer, even
  though the content is already tokenized. Not yet decided — see §7.
- **Retention**: a genuinely different retention conversation than the transient job-data policy in
  5.7 — audit logs are typically retained *longer* for compliance/legal reasons (a 1-7 year range is
  common), not shorter. Needs an explicit, deliberate retention window rather than an unbounded
  default. Not yet decided — see §7.


---

## 6. Mono-Repo and CI/CD Structure

Per this session's explicit direction: mirror **Entrephy's repo layout and pipeline mechanics
only** — not their apps, their AI-service code, or their redaction module (ruled out earlier in
this session on trust-boundary grounds — see Section 1). What's being reused is the *shape*:
npm-workspace-style directories, path-filtered GitHub Actions workflows, OIDC auth, SAM-based
per-stack deploys, `{project}-dev-{stack}` naming, cross-stack references via
`describe-stacks --query Outputs`.

### 6.1 Directory structure

```
redact-platform/
├── backend/
│   ├── functions/
│   │   └── summary/
│   │       ├── jobs_receive/          Lambda: POST /jobs handler
│   │       ├── extract/               Lambda: Call 1
│   │       ├── verify/                Lambda: verify_and_expand-equivalent
│   │       ├── merge_fields/          Lambda: per-field merge (5.4)
│   │       ├── interpret/             Lambda: Call 2 batch worker
│   │       ├── completeness_check/    Lambda: completeness check
│   │       ├── retry_extract/         Lambda: Call 1 retry
│   │       ├── qa_feedback/           Lambda: Call 4
│   │       └── finalize_callback/     Lambda: builds + POSTs callback to SJ
│   ├── templates/
│   │   └── summary.yaml               SAM template: API GW, Step Functions, all Lambdas above,
│   │                                   DynamoDB Jobs table, SQS DLQ
│   └── requirements-dev.txt
├── packages/
│   └── (empty at V1 — see 6.2)
├── local-component/
│   └── (the code shipped to SJ as a zip — see 6.3, deliberately outside backend/
│        since it is never deployed to AWS)
├── infrastructure/
│   └── (cross-cutting resources, if any emerge beyond what summary.yaml owns)
├── docs/
│   ├── PIPELINE_FLOW_DETAILED.md      (moved here from repo root, or kept at root — TBD)
│   └── AWS_BACKEND_DESIGN.md          (this document)
├── .github/
│   └── workflows/
│       └── deploy-summary-dev.yml     Path-filtered on backend/functions/summary/**,
│                                       backend/templates/summary.yaml
└── package.json                        (workspace root — present even with one app, for parity
                                          with the Entrephy pattern and to leave room to grow)
```

### 6.2 On `packages/`

Left empty at V1, deliberately, rather than pre-populated — the original mono-repo motivation
(#2 from earlier in this session) was to share redaction/tokenization logic across the summary and
redline tools once both exist on this platform. Since redline's AWS migration is out of scope for
V1 (Section 1) and the party-identity tokenization logic is genuinely new work being built now
(Section 3.2), there is nothing to *extract* into a shared package yet — there's one consumer.
`packages/` is reserved in the directory layout so that when redline's migration begins, the
tokenization/ingestion logic can be lifted out of `local-component/` into a shared package without
a repo restructure — but building a shared package now, before a second consumer exists, would be
premature abstraction against a guess at what the seam should be.

### 6.3 On `local-component/` living in this same repo

Open question, not yet decided: should the code shipped to SJ as a zip (Section 3) live in this
same mono-repo (as `local-component/`, per the structure above) or in a separate repo entirely?

Arguments for keeping it in this repo: shared versioning/tagging with the AWS side (a given
release of the contract — Section 4.4's payload shape — can be tagged consistently across both
sides), shared CI (a change to the tokenized-payload shape can be checked for consistency across
both the local component and the AWS-side Lambda that consumes it, in one PR).

Arguments for a separate repo: it is never deployed via this repo's AWS-focused CI/CD pipeline at
all (it's zipped and handed off, not `sam deploy`'d) — the deploy mechanics section of this
mono-repo (6.1's `.github/workflows/`) has nothing to do with how `local-component/` ships, so
folding it in adds a directory that doesn't participate in the pattern the rest of the repo is
built around. A separate `redact-local-component` repo, with its own simple "build the zip"
release workflow, may be cleaner and avoids implying (via co-location) that it's part of the AWS
deploy pipeline when it explicitly is not.

**Decision (this session): kept in this same mono-repo.** Even though `local-component/` never
goes through `sam deploy`, it still needs its own CI treatment — specifically **SAST and DAST
scanning** — and keeping it in-repo means it's covered by the same repo-wide security tooling and
branch protections as the AWS side, rather than needing a second repo with its own security config
to maintain. Its CI workflow is a separate concern from `deploy-summary-dev.yml` (no `sam deploy`
step at all), but lives in the same `.github/workflows/` directory:

- **SAST**: static analysis (e.g. Bandit for Python, plus a secrets scanner — Entrephy's repo uses
  `.gitleaks.toml`/`.semgrepignore`/`.checkov.yaml`, suggesting Gitleaks + Semgrep + Checkov are
  the toolchain already in use elsewhere in this organization; mirroring that toolchain here rather
  than introducing a fourth is worth doing if these tools are already known/configured) run on
  every change to `local-component/**`.
- **DAST**: since §3.3 is now settled as Option B (a local HTTP service), DAST applies directly —
  the CI workflow spins up the service (locally, in the CI runner, against synthetic/non-real test
  documents) and runs a DAST scanner (e.g. OWASP ZAP) against its endpoints before the release
  artifact is built. This is a real, addressable step now that there's a listening HTTP service to
  target, not a placeholder.
- **Release artifact**: the workflow builds the versioned zip (Section 3) as a build artifact/
  GitHub Release asset, gated on the security scans passing — the zip that ultimately reaches SJ is
  never one that skipped SAST/DAST.

This replaces the earlier "leaning toward separate repo" note — §6.1's directory structure already
had `local-component/` at the repo root, so no structural change is needed, just this decision
recorded and a dedicated CI workflow to design once §3.3 is resolved.

### 6.4 CI/CD workflow (`deploy-summary-dev.yml`)

Mirrors `deploy-factory-dev.yml`'s structure exactly (Entrephy pattern):

```yaml
name: Deploy Summary Backend (Dev)
on:
  push:
    branches: [development]  # or main, depending on branching convention adopted
    paths:
      - 'backend/functions/summary/**'
      - 'backend/templates/summary.yaml'
      - '.github/workflows/deploy-summary-dev.yml'
  workflow_dispatch:
permissions:
  id-token: write
  contents: read
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: dev
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - uses: aws-actions/configure-aws-credentials@v4.2.1
        with:
          role-to-assume: arn:aws:iam::<ACCOUNT_ID>:role/GitHubOIDCDeployRole
          aws-region: us-east-1
      - uses: aws-actions/setup-sam@v2
      - run: sam build --template-file backend/templates/summary.yaml
      - run: |
          sam deploy \
            --stack-name redact-dev-summary \
            --capabilities CAPABILITY_IAM \
            --resolve-s3 \
            --no-confirm-changeset \
            --no-fail-on-empty-changeset \
            --region us-east-1 \
            --parameter-overrides Environment=dev
```

No cross-stack parameter lookups (`describe-stacks --query Outputs`) are needed yet, since V1 is a
single stack (`summary.yaml` owns everything in the resource inventory, Section 5.5) — this pattern
becomes relevant once a genuinely shared resource (e.g. a shared Lambda Layer, once `packages/`
has real content per §6.2) needs to be referenced across multiple stacks, matching how Entrephy's
`deploy-factory-dev.yml` looks up `entrephy-dev-shared-layer`'s output.

Production workflow (`deploy-summary-prod.yml`) exists as a `workflow_dispatch`-only placeholder
until explicitly greenlit, matching the Entrephy pattern exactly.


---

## 7. Consolidated Open Items

Carried forward from `PIPELINE_FLOW_DETAILED.md` and this document, not yet decided:

1. ~~**Local-component invocation shape**~~ — **Resolved**: Option B, a local HTTP service SJ's
   .NET app calls over localhost (Section 3.3). SJ's exact call code is their own implementation
   detail once the REST contract (`POST /extract-and-tokenize` or equivalent) is specified.
2. **Process supervision on SJ's Windows Server**: now a hard requirement, not just a preference,
   given the Option B decision (Section 3.3) — the local service must be kept running (Windows
   Service wrapper or equivalent). Still left to SJ's own ops choice on *how*, but "that it must run
   continuously" is no longer optional the way it might have been under Option A.
3. ~~**Where `local-component/` lives**~~ — **Resolved**: kept in this same mono-repo, with its own
   SAST/DAST-gated CI workflow (Section 6.3).
4. **SJ status-poll fallback**: whether SJ needs a `GET /jobs/{id}/status` endpoint on AWS as a
   fallback in case a callback is somehow never received despite retry/DLQ handling (Section 5.3) —
   noted but not decided. Given the callback-retry-then-DLQ design, this may be unnecessary
   (SJ would instead need an *alerting* path when a job lands in the DLQ, which is an operational
   concern for us to monitor, not necessarily something SJ needs to poll for) — worth revisiting
   once real usage volume gives a sense of how often this actually matters.
5. **Party-identity resolution mechanism accuracy** (carried from earlier in this conversation,
   `PIPELINE_FLOW_DETAILED.md` §3, item #4 from the "gaps" discussion): still not tested against a
   real, varied document corpus. This is a prerequisite for production confidence, independent of
   anything in this AWS design document — it lives in the local component (Section 3.1, step 4),
   not on AWS, but blocks the whole system's privacy guarantee if unverified.
6. **Individual/non-party names beyond guarantors** (lenders, notice recipients, notaries) — scoped
   out of V1 deliberately (Section 1), revisit if/when usage moves beyond attorney-curated
   single-matter folders.
7. **Redline tool's AWS migration** — entirely out of scope for this document; will need its own
   equivalent design pass, informed by whatever is learned building the summary tool's version
   first (notably: the LibreOffice/track-changes step has no equivalent in this design and will
   need its own resourcing decision — Fargate vs. some other approach — when that phase starts).
   **Forward-looking note captured this session** on one specific piece of that future design —
   the clause repository (today's SQLite `provisions.db` / SQL Server fallback in
   `clause_repository.py`): SJ remains the source of truth for clause data (matching the existing
   division of responsibility — SJ owns their own queries/database, per Section 3). AWS should
   **cache** a working copy in DynamoDB rather than calling SJ's clause API live on every job's hot
   path — the deciding factor is latency/resilience (decoupling every AWS job's dependency from
   SJ's API being up and fast at that exact moment), not DynamoDB cost, which is trivial regardless
   of approach. Staleness is treated as a correctness problem, not an accepted side effect of
   caching, given these are attorney-approved legal clauses: refresh should be **push-based** (SJ
   notifies AWS via a webhook — e.g. `POST /clauses/refresh`, reusing the same shared-API-key auth
   pattern from Section 4.5 — when clauses change) rather than poll-based, to minimize the staleness
   window, and every cached clause record should carry a version/last-updated timestamp so a given
   job's provenance-verification audit trail can record exactly which clause version it matched
   against. This mirrors the existing SJ-authoritative/AWS-cached-copy pattern already used
   elsewhere in this design, rather than introducing a new one.
8. **API key rotation mechanics** (Section 4.5) — noted as not designed in detail, acceptable gap
   for V1 given Secrets Manager storage is the one concrete commitment made.
9. **Confidence-flagging UX on SJ's side** — AWS's callback includes `confidence_flags` (Section
   4.4), but how SJ's UI actually surfaces "these fields are low-confidence" to the end user is
   SJ's own UI responsibility (per the division of responsibility in Section 3) and is not
   specified by this document.
10. **QA feedback / self-learning system** (this session): explicitly deferred, not designed. Needs
    its own architecture once a real corpus of completed jobs exists to learn from — an offline/
    batch analysis pipeline reading accumulated job history and producing improved prompts/rules/
    config for future job versions, not a per-job Step Functions state. See §5.1's correction note.
    **Expanded this session** to also encompass legal-insight/trend-analysis over job history
    (§5.7) — both are "learn from accumulated job data" capabilities and should be designed
    together: as an aggregated/de-identified data product, built with an explicit consent/contract
    basis agreed with SeedJura (and, transitively, their end clients) before construction, not as
    an incidental extension of transient job-storage retention.
11. ~~**S3 need/sizing**~~ — **Resolved**: required, not optional. A realistic multi-document job
    exceeds Step Functions' 256KB per-state-transition limit; S3-backed payload passing (object
    references instead of inline text) is the design. See §5.7.
12. **Bedrock Guardrails as a content-safety backstop** (this session, distinct from the earlier,
    already-decided "not for redaction" ruling): open yes/no on whether a Guardrail should sit in
    front of Bedrock purely to catch inappropriate/low-quality model output on already-tokenized
    text. See §5.6.
13. ~~**WAF in front of API Gateway**~~ — **Resolved: not used.** Point-to-point integration with
    one known, API-key-authenticated caller; WAF's threat model doesn't match. See §5.6.
14. **Customer-managed KMS keys vs. AWS-managed defaults** for DynamoDB/Secrets Manager/S3
    encryption at rest (this session): open, likely to be driven by what a large enterprise
    customer's security questionnaire actually asks for rather than decided speculatively now.
    See §5.6.
15. **CloudTrail configuration specifics** (this session): the need itself is resolved (account-
    level baseline, required), but two sub-decisions remain open — whether to enable S3 data-event
    logging on the job-working-storage bucket in addition to management events, and the exact log
    retention window (a 1-7 year range is typical for compliance but not yet chosen). See §5.8.
16. **End-user "job complete" notification**: clarified this session as SJ's responsibility
    (triggered by receiving AWS's callback), not an AWS-side SNS topic — noted here only to record
    that this was explicitly discussed and scoped, not overlooked. See §5.6.

---

## 8. Account Baseline — Resources Actually Created (Dev Account 749619031719)

The following AWS resources have been created in the dev account (`749619031719`, region
`us-east-1`, via the `dev_builder` IAM user / `redact-dev` CLI profile) as the account baseline
and initial durable-storage layer, ahead of the compute layer (Lambda/API Gateway/Step Functions/
SQS/SNS/EventBridge), which is deferred until real Lambda code exists per Section 6 and gets
deployed via SAM rather than ad hoc CLI calls.

| Resource | Name / ARN | Configuration |
|---|---|---|
| CloudTrail trail | `redact-account-trail` (`arn:aws:cloudtrail:us-east-1:749619031719:trail/redact-account-trail`) | Multi-region, log file validation enabled, logging active. Fulfills Section 5.8's account-level baseline requirement. |
| CloudTrail log bucket | `redact-cloudtrail-749619031719` | Public access blocked, versioning enabled, bucket policy scoped to `cloudtrail.amazonaws.com` only (`GetBucketAcl` + `PutObject` under `AWSLogs/749619031719/*`, `bucket-owner-full-control` ACL condition). Object Lock/WORM (mentioned as a stronger option in §5.8) was **not** configured — log-file-validation digests are the tamper-evidence mechanism in place today; Object Lock remains open if a stronger guarantee is wanted later. |
| S3 — job working storage | `redact-summary-jobs-749619031719` | Public access blocked, SSE-S3 (AES256) default encryption, lifecycle rule expiring all objects after 7 days (+ aborting incomplete multipart uploads after 1 day). Fulfills Section 5.7's "required, short-lived" bucket. Customer-managed KMS (vs. today's SSE-S3 default) remains an open item per §5.6/§7. |
| DynamoDB — `Jobs` table | `redact-summary-jobs` (`arn:aws:dynamodb:us-east-1:749619031719:table/redact-summary-jobs`) | Partition key `job_id` (String), on-demand (`PAY_PER_REQUEST`) billing, TTL enabled on a `ttl` attribute (item-level epoch timestamp — must be set by whatever Lambda writes each job record; the table itself only enforces expiry once that attribute is present). Fulfills Section 5.3. |
| Secrets Manager secret | `redact/summary/shared-api-key` | Holds a randomly-generated 46-character value under the `api_key` field, generated locally and never displayed in this session. Fulfills Section 4.5's shared-API-key requirement. **The key's actual value is not recorded anywhere in this repository or this conversation — retrieve it via `aws secretsmanager get-secret-value --secret-id redact/summary/shared-api-key` with appropriate credentials when needed** (e.g. to hand it to SJ for their side of the integration, or to configure API Gateway's key validation once that's built). |

**Explicitly not yet created** (deferred until Lambda code exists, per this session's plan):
API Gateway, Lambda functions, Step Functions state machine, SQS dead-letter queue, SNS topic,
EventBridge rules, X-Ray configuration, Bedrock Guardrail (if adopted per the open §5.6 item), and
any IAM roles beyond the pre-existing `dev_builder`/`dev` group setup. These will be created via
the `summary.yaml` SAM template (Section 6) once the corresponding Lambda source exists, rather
than via standalone CLI calls, to keep the compute layer's definition version-controlled and
reproducible from the start.

**Access note**: the `dev_builder` user (in the `dev` group, `PowerUserAccess` policy) was used to
create all of the above, consistent with the temporary dev-convenience posture recorded in Section
5.6. This user was confirmed unable to call certain IAM read APIs (e.g. `iam:ListGroupsForUser`)
during this session, consistent with `PowerUserAccess`'s documented IAM exclusion — expect the same
exclusion to block `sam deploy --capabilities CAPABILITY_IAM` later, per that section's existing
note.

---

## Document status

Sections 1-6 represent decisions made through this design conversation, current as of this
session. Section 7 is the working list of what remains open. Section 8 records what has actually
been built in the AWS account so far, as distinct from what is only designed on paper. This
document should be updated as open items are resolved and as more of the design is actually built,
rather than superseded by a new document, to keep one authoritative source for the AWS backend
design.
