"""Byte-wise enumerative constrained coding; lexicographic A,C,G,T order."""
from functools import lru_cache
from itertools import groupby
BASES = 'ACGT'


def valid(sequence, limit):
    return all(b in BASES for b in sequence) and all(
        sum(1 for _ in run) <= limit for _, run in groupby(sequence))


def step(last, run, base):
    return base, run + 1 if base == last else 1


@lru_cache(None)
def count(length, last, run, limit):
    if not length:
        return 1
    return sum(count(length-1, *step(last, run, b), limit)
               for b in BASES if b != last or run < limit)


def width(limit):
    return next(n for n in range(1, 9)
                if min(count(n, b, limit, limit) for b in BASES) >= 256)


def encode(data, mode='constrained', limit=3):
    if mode == 'naive':
        return ''.join(BASES[(v >> shift) & 3] for v in data for shift in (6,4,2,0))
    n = width(limit)
    out, last, run = [], '', 0
    for value in data:
        for remaining in range(n-1, -1, -1):
            for b in BASES:
                if b == last and run == limit:
                    continue
                state = step(last, run, b)
                ways = count(remaining, *state, limit)
                if value < ways:
                    out.append(b)
                    last, run = state
                    break
                value -= ways
    return ''.join(out)


def decode(sequence, mode='constrained', limit=3):
    n = 4 if mode == 'naive' else width(limit)
    if len(sequence) % n or any(b not in BASES for b in sequence):
        raise ValueError('invalid encoded length or alphabet')
    if mode == 'constrained' and not valid(sequence, limit):
        raise ValueError('constraint violation')
    out, last, run = bytearray(), '', 0
    for start in range(0, len(sequence), n):
        rank = 0
        for offset, actual in enumerate(sequence[start:start+n]):
            if mode == 'naive':
                rank = rank * 4 + BASES.index(actual)
                continue
            for b in BASES:
                if b == last and run == limit:
                    continue
                if b == actual:
                    break
                rank += count(n-offset-1, *step(last, run, b), limit)
            last, run = step(last, run, actual)
        if rank > 255:
            raise ValueError('unused codeword')
        out.append(rank)
    return bytes(out)


@lru_cache(None)
def gc_count(length, last, run, limit, low, high):
    """Count completions containing between low and high additional GC bases."""
    if high < 0 or low > length:
        return 0
    if length == 0:
        return int(low <= 0 <= high)
    return sum(gc_count(length-1, *step(last, run, b), limit,
                        max(0, low-int(b in 'GC')), high-int(b in 'GC'))
               for b in BASES if b != last or run < limit)


@lru_cache(None)
def gc_width(limit, minimum=40, maximum=60):
    if not (type(minimum) is int and type(maximum) is int and
            0 <= minimum <= maximum <= 100):
        raise ValueError('GC bounds must be integer percentages in 0..100')
    for n in range(1, 13):
        low, high = (n*minimum+99)//100, n*maximum//100
        if min(gc_count(n, b, limit, limit, low, high) for b in BASES) >= 256:
            return n
    raise ValueError('GC bounds cannot represent a byte within the 12-base block limit')


def gc_encode(data, limit=3, minimum=40, maximum=60):
    n = gc_width(limit, minimum, maximum)
    out, last, run = [], '', 0
    for value in data:
        low, high = (n*minimum+99)//100, n*maximum//100
        for remaining in range(n-1, -1, -1):
            for b in BASES:
                if b == last and run == limit:
                    continue
                g = int(b in 'GC')
                state = step(last, run, b)
                ways = gc_count(remaining, *state, limit, max(0, low-g), high-g)
                if value < ways:
                    out.append(b)
                    last, run = state
                    low, high = max(0, low-g), high-g
                    break
                value -= ways
    return ''.join(out)


def gc_decode(sequence, limit=3, minimum=40, maximum=60):
    n = gc_width(limit, minimum, maximum)
    if len(sequence) % n or not valid(sequence, limit):
        raise ValueError('invalid GC-constrained sequence')
    out, last, run = bytearray(), '', 0
    for start in range(0, len(sequence), n):
        block = sequence[start:start+n]
        low, high = (n*minimum+99)//100, n*maximum//100
        if not low <= sum(b in 'GC' for b in block) <= high:
            raise ValueError('GC block constraint violation')
        rank = 0
        for offset, actual in enumerate(block):
            for b in BASES:
                if b == last and run == limit:
                    continue
                if b == actual:
                    break
                g = int(b in 'GC')
                rank += gc_count(n-offset-1, *step(last, run, b), limit,
                                 max(0, low-g), high-g)
            g = int(actual in 'GC')
            low, high = max(0, low-g), high-g
            last, run = step(last, run, actual)
        if rank >= 256:
            raise ValueError('unused GC codeword')
        out.append(rank)
    return bytes(out)
