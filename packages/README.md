# packages/

Deliberately empty at V1. Reserved for shared code once a second consumer exists to justify
extraction (e.g. when the redline tool's AWS migration begins and shares ingestion/tokenization
logic with the summary tool's local component). See `docs/AWS_BACKEND_DESIGN.md` §6.2 for the
rationale — building a shared package before a second consumer exists would be premature
abstraction against a guess at what the seam should be.
