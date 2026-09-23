# backend/functions/summary/

Lambda source for the summary tool's AWS-side pipeline, orchestrated by a Step Functions state
machine defined in `../../templates/summary.yaml` (not yet written). See
`../../../docs/AWS_BACKEND_DESIGN.md` §5 for the full pipeline mapping and resource inventory.

| Directory | Purpose | AI call? |
|---|---|---|
| `jobs_receive/` | `POST /jobs` handler — validates + persists incoming job (DynamoDB), starts the Step Functions execution, returns the `202 Accepted` ACK | No |
| `extract/` | Call 1 — raw field extraction, run per document in the set | Yes (Bedrock) |
| `verify/` | `verify_and_expand()`-equivalent — exact/fuzzy/anchor matching against the tokenized source text, run per document | No |
| `merge_fields/` | `merge_fields()`-equivalent — per-field "latest document wins" merge across the document set, with origin/termination/effective-date pinning | No |
| `interpret/` | Call 2 — interpretation, batched via a Step Functions `Map` state, runs on the merged current-value view | Yes (Bedrock) |
| `completeness_check/` | Structural check for missing/suspect fields, decides whether a retry is needed | No |
| `retry_extract/` | Call 1 retry variant, only triggered conditionally by the completeness check | Yes (Bedrock) |
| `finalize_callback/` | Builds the final tokenized JSON payload and POSTs it to SJ's `callback_url`, with retry/dead-letter handling | No |

**Explicitly not here**: QA feedback (Call 4) — deferred out of V1's per-job pipeline entirely; see
design doc §5.1's correction note and §7 item 10. Output generation (DOCX/XML/JSON) — that is SJ's
responsibility after detokenization, per §4.1.

Not yet implemented — these are placeholder directories until real handler code is written.
