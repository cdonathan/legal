# infrastructure/

Reserved for cross-cutting AWS resources that don't belong to a single stack (`summary.yaml`,
future `redline.yaml`, etc.). Empty at V1 — everything needed for the summary tool so far fits in
one stack (`backend/templates/summary.yaml`). The account-level baseline (CloudTrail and its log
bucket) is **not** managed here either — it was created directly via CLI as a one-time account
setup step, per `docs/AWS_BACKEND_DESIGN.md` §8, and is intentionally account-scoped rather than
tied to any application stack's lifecycle.
