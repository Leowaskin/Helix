# GC constraint experiment

512 pseudorandom payload bytes, 20 seeds per scenario; 40 scenarios.
See [raw results](gc-benchmark.json) for full parameters, Wilson 95% intervals,
runtime and traced Python memory. Use `python -m helix.benchmark --trials 20` to rerun.

| Codec | Outer parity | Net bits/nt | Clean | 25% dropout | 10% dropout + 0.1% substitutions |
|---|---:|---:|---:|---:|---:|
| naive | 2 | 0.582 | 20/20 | 2/20 | 17/20 |
| naive | 4 | 0.485 | 20/20 | 12/20 | 20/20 |
| constrained run≤1 | 2 | 0.388 | 20/20 | 1/20 | 1/20 |
| constrained run≤1 | 4 | 0.323 | 20/20 | 13/20 | 11/20 |
| constrained run≤3 | 2 | 0.465 | 20/20 | 1/20 | 10/20 |
| constrained run≤3 | 4 | 0.388 | 20/20 | 13/20 | 19/20 |
| gc 40–60% | 2 | 0.465 | 20/20 | 1/20 | 9/20 |
| gc 40–60% | 4 | 0.388 | 20/20 | 13/20 | 17/20 |
| gc 50–50% | 2 | 0.388 | 20/20 | 1/20 | 1/20 |
| gc 50–50% | 4 | 0.323 | 20/20 | 13/20 | 6/20 |

At cap three, the 40–60% GC code retains five bases per byte. Exact 50% GC
requires six: 20% more nucleotides and 16.7% lower density for the same frames.
Both guarantee the full-strand range by constraining every byte block.

Recovery differences reflect the particular rank mapping, read rejection, redundancy
and sequence-independent simulated noise. They do not establish a biochemical
advantage. Twenty trials leave wide uncertainty; close counts should not be ranked.
All clean scenarios must recover, while noisy trials are measurements, not acceptance
thresholds. The trusted manifest remains required and is counted separately.
