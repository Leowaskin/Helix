# Bounded single-indel recovery

32 seeded payload bytes, k=2 data strands and p=1 parity strand, ten trials
per scenario. Identical read pools are used with synchronization off and on.
Raw trials, hashes, timing, memory, diagnostics and Wilson intervals:
[indel-benchmark.json](indel-benchmark.json).

| Codec | Insertion and deletion rate (each) | Off | On | Mean decode ms off/on |
|---|---:|---:|---:|---:|
| naive | 0 | 10/10 | 10/10 | 1.3 / 1.3 |
| naive | 0.001 | 8/10 | 10/10 | 1.4 / 137.0 |
| naive | 0.005 | 1/10 | 6/10 | 0.8 / 120.8 |
| constrained | 0 | 10/10 | 10/10 | 3.4 / 3.4 |
| constrained | 0.001 | 5/10 | 10/10 | 2.2 / 205.2 |
| constrained | 0.005 | 1/10 | 2/10 | 1.0 / 136.6 |
| gc | 0 | 10/10 | 10/10 | 3.5 / 3.5 |
| gc | 0.001 | 5/10 | 10/10 | 2.4 / 235.8 |
| gc | 0.005 | 1/10 | 2/10 | 1.0 / 133.5 |

No additional synthesized bases are required; density and storage overhead are
identical for off/on within each scenario. The extra cost is computation.
The search is limited to reads whose length differs by exactly one base.
At higher rates, unsupported multiple events increasingly limit recovery.

Ten trials provide demonstration evidence with wide uncertainty, not a reliability
estimate for a physical DNA system. Traced timing includes Python allocation
instrumentation and is not a production performance measurement. All clean cases
should succeed under both policies. Read-pool hashes enable paired reproduction.

Re-run: `.venv/bin/python -m helix.indel_benchmark --trials 10`.
