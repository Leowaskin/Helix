# Demonstration results

512 seeded pseudorandom bytes; 20 trials per scenario. Full parameters, timing,
memory and Wilson intervals are in [benchmark.json](benchmark.json).

| Codec | Outer parity | Net bits/nt | Clean recovery | 25% dropout | 10% dropout + 0.1% substitutions |
|---|---:|---:|---:|---:|---:|
| naive | 2 | 0.582 | 20/20 | 2/20 | 17/20 |
| naive | 4 | 0.485 | 20/20 | 12/20 | 20/20 |
| constrained (max run 1) | 2 | 0.388 | 20/20 | 1/20 | 1/20 |
| constrained (max run 1) | 4 | 0.323 | 20/20 | 13/20 | 11/20 |
| constrained (max run 3) | 2 | 0.465 | 20/20 | 1/20 | 10/20 |
| constrained (max run 3) | 4 | 0.388 | 20/20 | 13/20 | 19/20 |

All clean scenarios recovered. More outer parity generally improves recovery at
the expense of density. The max-run-1 mapping is particularly vulnerable to
substitutions under this decoder: invalid codewords become whole-strand erasures.
This is evidence about this implementation under the specified synthetic channel,
not evidence that constrained coding worsens physical DNA storage. Channel errors
here are independent of sequence context, so biological benefits of constraints
are deliberately absent from the model. Trial counts are too small to rank close results.

Re-run: `.venv/bin/python -m helix.benchmark --trials 20`.
