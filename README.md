# redact-platform

AWS serverless backend for the SeedJura joint-venture legal-document tooling (summary tool first;
redline tool deferred). See `docs/AWS_BACKEND_DESIGN.md` for the full design — scope, trust
boundary, the SJ↔AWS job contract, AWS-side pipeline mapping, resource inventory, and open items —
and `docs/PIPELINE_FLOW_DETAILED.md` for the underlying pipeline trace and party-identity
tokenization design both documents build on.

Repo layout and CI/CD mechanics mirror an existing internal platform's mono-repo pattern
(npm-workspace-style directories, path-filtered GitHub Actions, OIDC-authenticated SAM deploys) —
**only the repo shape and deploy mechanics are mirrored, not any application code, AI-service
logic, or redaction implementation**, per an explicit decision recorded in
`docs/AWS_BACKEND_DESIGN.md` §6.

## What's inside

| Directory | Purpose |
|---|---|
| `backend/functions/summary/` | Lambda source for the summary tool's AWS-side pipeline (extraction, verification, merge, interpretation, completeness/retry, callback) |
| `backend/templates/` | SAM/CloudFormation templates — `summary.yaml` (not yet written) |
| `packages/` | Reserved for shared code once a second consumer exists (currently empty — see `packages/README.md`) |
| `local-component/` | The code shipped to SeedJura as a versioned zip — extraction, redaction/tokenization, party-identity resolution. Never deployed to AWS; has its own SAST/DAST-gated CI workflow. |
| `infrastructure/` | Reserved for cross-cutting AWS resources beyond what a single stack owns (currently empty) |
| `docs/` | Design documents |
| `.github/workflows/` | Path-filtered CI/CD — one workflow per deployable unit |

## Status

Scaffolding only as of this commit. No Lambda handlers, no SAM template, and no local-component
code have been written yet — see each subdirectory's `README.md` for what belongs there and what's
still pending. The AWS account baseline (CloudTrail, the job working-storage S3 bucket, the
`Jobs` DynamoDB table, and the shared API key in Secrets Manager) has already been created directly
in the dev account — see `docs/AWS_BACKEND_DESIGN.md` §8 for exact resource names/ARNs. The
Lambda/API Gateway/Step Functions/SQS/SNS/EventBridge compute layer is intentionally deferred until
real handler code exists, so it can be created via this repo's SAM template rather than ad hoc CLI
calls.

## License

Private — not for distribution outside the parties to the SeedJura joint venture.
