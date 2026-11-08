"""Independent per-original-base events; seeded, synthetic, no biological calibration."""
import random
from .limits import Limits
from dataclasses import dataclass


@dataclass(frozen=True)
class Channel:
    substitution: float = 0
    insertion: float = 0
    deletion: float = 0
    dropout: float = 0
    duplication: float = 0

    def __post_init__(self):
        if any(not 0 <= p <= 1 for p in vars(self).values()):
            raise ValueError('probabilities must be between zero and one')


def damage(strands, channel=Channel(), seed=0, limits=Limits()):
    rng = random.Random(seed)
    reads = []
    total_nt = 0
    for index, strand in enumerate(strands):
        if index >= limits.max_reads or len(strand) > 4096 or any(b not in 'ACGT' for b in strand):
            raise ValueError('invalid strand or channel resource limit exceeded')
        total_nt += len(strand)
        if total_nt > limits.max_total_nt:
            raise ValueError('channel pool exceeds nucleotide resource limit')
        if rng.random() < channel.dropout:
            continue
        out = []
        for base in strand:
            if rng.random() < channel.insertion:
                out.append(rng.choice('ACGT'))
            if rng.random() < channel.deletion:
                continue
            out.append(rng.choice('ACGT'.replace(base, ''))
                       if rng.random() < channel.substitution else base)
        read = ''.join(out)
        reads.append(read)
        if rng.random() < channel.duplication:
            reads.append(read)
    rng.shuffle(reads)
    return reads
