# Format and algorithm specification: version 1

## Strand layout and manifest

No primers are appended. Every nucleotide in a line participates in the codec.
Primers would support biochemical amplification/selection; encoded identifiers
provide software identity/order. These roles are not interchangeable.

Before DNA mapping, a strand is:

| Field | Bytes | Meaning |
|---|---:|---|
| File identifier | 8 | First 8 bytes of original SHA-256 |
| Global shard index | 4 | Unsigned big endian; group*n + shard |
| Payload | chunk_bytes | One systematic or parity shard |
| CRC-32 | 4 | zlib CRC over all preceding fields, big endian |
| Inner RS parity | inner_parity | Systematic RS parity over header, payload, CRC |

Defaults: 8 data shards, 4 outer parity shards, 16 payload bytes/strand,
12 inner parity bytes. Frame length is 44 bytes, producing 176 naive bases,
220 max-run-3 bases or 264 max-run-1 bases. These lengths are software choices,
not a synthesis specification. There is no fixed oligo-length setting in v1.

Required manifest fields: version=1; config (mode, max_run, chunk_bytes,
data_shards, parity_shards, inner_parity); original byte size; full SHA-256;
number of groups; encoded strand length; primers=[] (must remain empty).
Original filename is unnecessary. Final stripe is zero padded; byte size removes
padding, including for empty files, which use one all-zero stripe. No seed,
original file, original strand list or simulator event log is needed by recovery.
The sidecar is a trusted decoder dependency and an availability limitation.

## Codes and recovery

reedsolo 1.7.0 RSCodec defaults: GF(256), primitive polynomial 0x11d,
first consecutive root 0, generator 2, maximum codeword length 255.
For each group, split bytes into k contiguous payload rows. Each byte column
becomes an RS(n,k) word: n=k+p. The first k rows are systematic; p rows parity.
Recover up to p missing rows in **each** group, independently. A global dropout
percentage alone cannot guarantee recovery. Outer decoding uses erasures only.

Inner parity q protects the whole frame, including both identifiers. Its bound
is 2e+s <= q for symbol errors e and known erasures s; v1 supplies no inner
erasure locations, so e <= floor(q/2). Constraint decoding may discard damaged
reads before RS. A DNA edit can change several byte symbols; this bound is not
a DNA edit-count guarantee. After RS: verify file ID, index range and CRC.
Identical duplicate payloads merge; conflicting valid payloads erase that index.
Outer recovery then restores data; full SHA-256 must match before output.

## Reversible mapping

Naive: each byte maps its four high-to-low bit pairs as 00=A, 01=C, 10=G, 11=T.
Rate is 2 bits/base before metadata and redundancy. It is an unconstrained baseline;
max_run is ignored for its output guarantees.

Constrained state is (last base, current run), carried across every byte, including
metadata and parity. For run cap h, an edge emitting b is permitted unless b equals
last and run=h. Let C(r,state) count allowed r-base continuations:
C(0,state)=1; otherwise sum C(r-1,next(state,b)) over allowed bases.
Choose a uniform byte-block width L with at least 256 continuations from every
possible state. Implementation uses the worst run=h state for each last base:
L=6 for h=1 and L=5 for h=2 or 3. Each byte is a lexicographic rank 0..255.
Subtract branch counts until its branch is found; emit L bases. Decoder sums
preceding branch counts to recover the rank; ranks >=256 are unused and rejected.
For h=1, byte zero encodes ACACAC from the empty state.

Each block has fixed length, preserves state deterministically, and terminates
in exactly L steps. No random search, escape symbol, or trailing marker is needed;
strand length provides framing. Rate is 8/L: 1.333 or 1.6 bits/base, before
metadata and redundancy. This conservative byte-block code does not achieve the
constraint channel's asymptotic capacity, which is log2 of the state graph's
spectral radius. Unused valid words are the cost of simple byte framing.
State resets only between strands. Full-strand validation independently checks
the final assembled output. Current guarantees concern homopolymers only; GC
balance and secondary structure are not guaranteed.

## Experiment interpretation

Net density = 8*original_bytes / sum(length of each emitted strand), including
header, padding, CRC and both parity layers. Overhead above the unconstrained
ideal = total_nt/(4*original_bytes)-1. Benchmark payloads are nonempty. Manifest
bytes are reported separately because they reside outside DNA. No rejected
candidates exist in this deterministic encoder. Physical synthesis copies,
sequencing depth, primers and sidecar DNA storage are not counted or modeled.

The simulator performs dropout first. For each original base it independently
samples an insertion before it, deletion, then substitution if not deleted.
Duplication copies the final damaged read; the pool is shuffled. Seeds are logged.
These IID rates are experimental controls, not estimates from biological data.

RS known-vector source: [reedsolo upstream README](https://github.com/tomerfiliba-org/reedsolomon/blob/master/README.rst).

# Format version 2: joint GC and homopolymer coding

Version 2 selects `mode="gc"` and adds integer `gc_min` and `gc_max`
percentages to the configuration. Other fields and the binary RS frame remain
unchanged. Version-1 manifests without these fields still decode using defaults;
version 1 cannot select gc mode and version 2 must select gc mode. Older Helix
releases will correctly reject version 2.

GC scope is **each complete encoded byte block**, including blocks encoding
identifiers, CRC and parity. Because every block has equal width, its full-strand
weighted average also lies within the specified range. This is stronger than a
full-strand-only constraint, and can cost capacity. Arbitrary sliding windows,
primers and secondary structure remain outside the guarantee.

State adds the number of GC bases still required/allowed in the current block.
For length L, integer bounds are ceil(L*gc_min/100) and floor(L*gc_max/100).
The recurrence G(r,last,run,low,high) sums permitted base branches, subtracting
one from GC budgets for C or G. It returns zero for impossible budgets, and at
r=0 returns one exactly when zero is in the budget interval. The lexicographic
rank/unrank procedure is otherwise the same as version 1. GC budgets reset each
byte; last/run do not. Decoder rejects blocks outside the GC range and unused
ranks before inner RS. Empty codec input produces empty output; storage still
creates a nonempty protected stripe for an empty file.

Width is the first L in 1..12 with at least 256 completions from every last-base
state at maximum run length. This pessimistic state ensures feasibility for
all reachable states. Configuration is rejected if the percentage interval is
invalid or no such width exists **under this byte-block design and 12-base
budget**. This is not a proof that no other DNA encoding could work.
At cap three: 40–60% GC uses L=5 (1.6 bits/base), exactly 50% uses L=6
(1.333 bits/base). An exact 51% cannot be represented by these block lengths.
Termination is exactly L bases per byte; inverse mapping is unique by branch
counting. There are no rejection attempts, random seeds or escape markers.

Defaults still select the version-1 homopolymer-only encoder. To opt in:
`--config examples/gc.toml`. Benchmark `results/gc-benchmark.json` compares
both GC settings with the previous baselines and parity budgets. Error rates
remain sequence-independent: this experiment measures costs and software
recovery, not biochemical benefits of GC balance.

# Decoder extension: bounded single-indel recovery

This opt-in decoder policy works with both existing formats and changes no DNA
or manifest fields. It is not HEDGES or a marker-based synchronization code.
Enable with `decode --single-indel`; `--max-candidates` defaults to 8192 per read.

Let expected strand length be N. For length N+1, enumerate removal of each base.
For length N-1, enumerate insertion of each A/C/G/T at every boundary, including
both ends. Identical candidate strings are deduplicated. For length N, try the
original read only; other lengths and non-ACGT input are rejected. This procedure
is exhaustive for a single insertion or deletion: the original strand is in the
neighborhood. Its bound is N+1 candidates for insertion damage and 4N for deletion
damage, before deduplication. Candidate generation stores O(N^2) characters and
runs O(N) full strand decodes, each involving mapping and an inner RS operation.

A conservative preflight bound exceeding the configured budget rejects the whole
read before searching. Search is never silently truncated. Every candidate is
checked using the existing mapper, RS, file ID, index range and CRC. Collect
**distinct complete binary frames**, not candidate DNA strings. Exactly one frame
is accepted; zero or multiple frames reject the read. Rejected reads flow into
outer erasure recovery. Final file SHA-256 remains mandatory.

The search includes the correct strand for one true indel, but acceptance is
conditional on a sufficient budget and no distinct false-positive validated frame.
CRC and SHA are probabilistic integrity checks. This is not a general edit-distance
correcting code or a guarantee against adversarial corruption. Mixed substitutions
may be corrected by inner RS after a candidate restores synchronization; no
combined DNA edit bound is claimed. Two opposite indels can preserve length and
are **not searched**. Multiple indels with net length one may coincidentally
recover through RS, but are unsupported as a synchronization guarantee.

`--diagnostics path.json` writes read, acceptance, repaired-read, rejection,
ambiguity, budget-rejection and tested-candidate counts, even if file recovery
fails. “Repaired” means an accepted read had changed length, not that the true
physical error history is known. Decoder options are execution policy, not stored
format metadata; reproducibility requires recording them with experiment results.
The paired benchmark records those options, seeds and read-pool hashes, and runs
both policies on precisely the same pool. It records time, Python allocation peak,
file successes, raw diagnostics and Wilson confidence intervals. Tracing affects
timing. There is no claim about real synthesis or sequencing performance.
