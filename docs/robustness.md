# Robustness review

## Findings addressed

- Malformed manifest types, booleans used as integer counts, short/non-hex digests,
  missing/unknown fields and inconsistent sizes now fail with ValueError.
- Unknown config fields and missing required format fields are rejected; only the
  original optional GC fields retain compatibility defaults.
- Integer ceiling division avoids float precision/overflow for malicious sizes.
- Encoding preflights pool count and total emitted bases before allocating strands.
- Recovery limits output size, read count, input bases and total candidates across
  all reads, in addition to the per-read synchronization budget.
- CLI bounds config/manifest files to 64 KiB and reads lines incrementally with a
  4096-base line limit. Non-ASCII reads and deeply nested JSON fail without tracebacks.
- CLI output replacement is atomic per file. Failed recovery preserves existing
  output bytes. Diagnostics can still be written on failure.
- Resolved paths and existing hard links are checked to prevent input/output/
  diagnostics aliasing. The channel rejects invalid alphabet and oversized pools.

## Default resource policy

`Limits` defaults: 1 MiB original/restored bytes, 100,000 input reads or emitted
strands, 16 Mi nucleotides in the pool, 1,000,000 candidate decodes in total.
Synchronization defaults to at most 8192 candidates per read. Limits are positive
integers; library callers can explicitly supply a different Limits policy. CLI
uses the defaults. Atomic replacements use a temporary file in the destination
directory. The output directory must already exist except for encode/demo.

These are finite work/allocation bounds, not hard RSS or elapsed-time limits.
Python object overhead, read deduplication sets and decoder caches consume memory
beyond byte counts. Use process isolation for hostile multi-user workloads.

## Validation evidence

Regression tests cover malformed metadata, missing fields, huge/negative counts,
wrong digest shapes, total work limits, unknown codec/config values, oversized and
non-ASCII reads, nested JSON, preservation of existing output, diagnostic alias
prevention, atomic writing, CLI round trips and the existing codec/recovery cases.
The deterministic demo exercises real encoding and single-indel recovery; CI runs
it separately from tests. Local tests were run on Python 3.14. GitHub Actions is
configured for 3.11–3.14 and has not yet been executed remotely.

## Remaining practical limits

- This is an in-memory research prototype with small-file evaluation, not a
  streaming archival service or a hard real-time decoder.
- Manifests remain a trusted external dependency. SHA/CRC are integrity checks,
  not authentication against deliberate replacement of file plus manifest.
- Encoding writes manifest and strand files atomically **individually**, not as a
  transaction spanning both. An interrupted overwrite can leave a mismatched pair;
  the decoder's checks should reject it. Use a fresh output directory for each run.
- Path alias checks do not protect against concurrent hostile filesystem changes.
- Multiple indels and general synchronization remain unsupported. No wet-lab,
  primer-interaction, secondary-structure or platform-specific error validation.
- CI configuration is delivered, but no remote run or deployment is claimed.

A local editable install did not activate its import hook in this runtime. The
documented setup therefore uses a standard wheel install; reinstall after code
changes when using the installed `helix` command outside the repository.
