# verification/dataset — Detailed Input/Output per Program

> Every program run saves detailed input/output per step for verification. One program at a time (sequential), never parallel bulk.

Layout per benchmark (e.g., ERQA):
```
verification/dataset/ERQA/
├── manifest.json                 # download manifest (file count, sha)
├── sample_000/
│   ├── input.json                # Step 0 input: query, doc slice, specialist, tool hits
│   ├── step_000_input.json       # Detailed input for step 0 (code to execute)
│   ├── step_000_output.json      # Detailed output for step 0 (stdout, stderr, error, time, sentinel)
│   ├── step_001_input.json
│   ├── step_001_output.json
│   ├── step_002_input.json
│   ├── step_002_output.json
│   ├── output.json               # Final aggregated output (final_answer, termination_reason, steps)
│   └── run.log                   # Full session log (jsonl)
├── sample_001/ ... same
├── sample_002/ ... same
└── summary.json                  # Across all samples: count, pass/fail, total time
```

Invariants:
- Dataset immutable after download (idempotent skip).
- 1 program at a time sequential (not speculative parallel) — operationality verified per program.
- Each step's input/output saved with checksum — traceable REQ-010 -> FILE-022 -> METHOD-020 -> VERIFY-020.
