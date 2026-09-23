# local-component/

The code shipped to SeedJura (SJ) as a versioned zip, installed and run on their Windows Server.
Never deployed to AWS — this directory does not participate in `sam deploy`. See
`docs/AWS_BACKEND_DESIGN.md` §3 and §6.3 for the full design and CI rationale (SAST/DAST-gated
release workflow, kept in this same mono-repo for shared versioning with the AWS-side contract).

**Shape (per §3.3's decision — Option B):** a minimal FastAPI/uvicorn local HTTP service SJ's own
.NET application calls over localhost (e.g. `POST /extract-and-tokenize`). Not a copy of the
existing standalone `seedjura_psa_standalone_*` zip's full app — that zip's UI/API-server scope is
being deliberately narrowed down to just the extraction/redaction/tokenization responsibility SJ
doesn't own.

**What it must do**, per §3.1:
1. Ingest (PDF/DOCX extraction, OCR fallback)
2. Document-set ordering (oldest/newest resolution)
3. Duplicate detection
4. Party-identity resolution (recital + signature-block cross-check, assignment/successor check)
5. Gap handling (inherit / escalate / OCR-retry-then-flag)
6. Full tokenization of in-scope identifying data (§1 of the design doc: the two legal parties +
   guarantors — names, addresses, SSNs, EINs, phone numbers, emails, account numbers)
7. Build and hold the token↔real-value mapping table locally — **never transmitted to AWS**
8. Call AWS (`POST /jobs`, per §4)
9. Receive AWS's tokenized results and reconstruct real values locally before generating final
   output (DOCX/XML/JSON)

Not yet implemented — this is a placeholder directory until that code is written.
