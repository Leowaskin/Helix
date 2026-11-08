import itertools
import pytest
from hypothesis import given, settings, strategies as st
from reedsolo import RSCodec
from helix.codec import encode, decode, count
from helix.storage import Config, compile_bytes, recover
from helix.channel import Channel, damage


def independent_run_check(s, cap):
    for i in range(len(s)-cap):
        assert len(set(s[i:i+cap+1])) != 1


@pytest.mark.parametrize('limit', [1,2,3])
def test_exhaustive_bytes(limit):
    for v in range(256):
        data = bytes([v])
        assert decode(encode(data, limit=limit), limit=limit) == data
    for length in range(5):
        strings = [''.join(x) for x in itertools.product('ACGT', repeat=length)]
        valid = [s for s in strings if all(len(set(s[i:i+limit+1])) > 1 for i in range(len(s)-limit))]
        assert count(length, '', 0, limit) == len(valid)


def test_known_vectors():
    assert encode(b'\x1b', 'naive') == 'ACGT'
    assert decode('ACGT', 'naive') == b'\x1b'
    assert encode(b'\0', limit=1) == 'ACACAC'
    # Published reedsolo README example, GF(256), primitive polynomial 0x11d.
    assert RSCodec(10).encode(b'hello world') == b'hello world\xed%T\xc4\xfd\xfd\x89\xf3\xa8\xaa'


@settings(max_examples=40, deadline=None)
@given(st.binary(max_size=256), st.sampled_from([1,2,3]))
def test_properties(data, limit):
    dna = encode(data, limit=limit)
    independent_run_check(dna, limit)
    assert decode(dna, limit=limit) == data
    m, s = compile_bytes(data, Config(max_run=limit))
    for strand in s:
        independent_run_check(strand, limit)
    # Remove exactly the parity budget in every stripe, shuffle and duplicate.
    kept = [read for i, read in enumerate(s) if i % 12 >= 4]
    assert recover(m, list(reversed(kept))+kept[:1]) == data


@pytest.mark.parametrize('mode', ['naive', 'constrained'])
def test_inner_correction_and_failure(mode):
    data = bytes(range(256))
    c = Config(mode=mode)
    m, strands = compile_bytes(data, c)
    damaged = []
    for strand in strands:
        frame = bytearray(decode(strand, mode))
        for j in range(c.inner_parity//2):
            frame[j] ^= 37  # includes both file identifier and chunk index
        damaged.append(encode(frame, mode))
    assert recover(m, damaged) == data
    with pytest.raises(ValueError, match='erasures'):
        recover(m, strands[5:])
    with pytest.raises(ValueError):
        recover(m, [s+'A' for s in strands])


def test_simulation():
    m, s = compile_bytes(b'Helix'*80)
    ch = Channel(dropout=.1, duplication=.3)
    assert damage(s, ch, 42) == damage(s, ch, 42)
    assert recover(m, damage(s, ch, 42)) == b'Helix'*80
    assert damage(s, Channel(dropout=1), 1) == []
    assert all(len(x) == 2*len(s[0]) for x in damage(s, Channel(insertion=1), 1))
    assert all(x == '' for x in damage(s, Channel(deletion=1), 1))


def test_integrity_and_config():
    m, s = compile_bytes(b'payload')
    m['sha256'] = '00'*32
    with pytest.raises(ValueError):
        recover(m, s)
    for kw in [{'chunk_bytes':250}, {'data_shards':255}, {'max_run':0}, {'mode':'unknown'}]:
        with pytest.raises(ValueError):
            Config(**kw)


def test_dna_substitution_and_balanced_indels():
    m, strands = compile_bytes(bytes(range(100)), Config(mode='naive'))
    mutated = [('C' if s[0] != 'C' else 'A') + s[1:] for s in strands]
    assert recover(m, mutated) == bytes(range(100))
    # Balanced insertion/deletion may evade length checks: no claim of correction.
    bad = [s[len(s)//2:] + s[:len(s)//2] for s in strands]
    with pytest.raises(ValueError):
        recover(m, bad)


def test_every_small_erasure_pattern():
    m, s = compile_bytes(b'abcdef', Config(data_shards=3, parity_shards=2, chunk_bytes=2))
    for missing in itertools.combinations(range(5), 2):
        assert recover(m, [r for i,r in enumerate(s) if i not in missing]) == b'abcdef'


@pytest.mark.parametrize('limit', [1, 2, 3])
@pytest.mark.parametrize('bounds', [(40, 60), (50, 50)])
def test_gc_exhaustive_and_counts(limit, bounds):
    from helix.codec import gc_encode, gc_decode, gc_count
    for value in range(256):
        data = bytes([value]) * 2
        dna = gc_encode(data, limit, *bounds)
        independent_run_check(dna, limit)
        assert bounds[0]*len(dna) <= 100*sum(b in 'GC' for b in dna) <= bounds[1]*len(dna)
        assert gc_decode(dna, limit, *bounds) == data
    # Independent enumeration includes a boundary in the worst possible state.
    for length in range(5):
        for low in range(length+1):
            high = min(length, low+1)
            expected = 0
            for word in itertools.product('ACGT', repeat=length):
                s = 'A'*limit + ''.join(word)
                allowed = all(len(set(s[i:i+limit+1])) > 1 for i in range(len(s)-limit))
                expected += allowed and low <= sum(b in 'GC' for b in word) <= high
            assert gc_count(length, 'A', limit, limit, low, high) == expected


@settings(max_examples=30, deadline=None)
@given(st.binary(max_size=256), st.sampled_from([1,2,3]))
def test_gc_file_recovery(data, limit):
    c = Config(mode='gc', max_run=limit, gc_min=50, gc_max=50)
    m, s = compile_bytes(data, c)
    assert m['version'] == 2
    for strand in s:
        independent_run_check(strand, limit)
        assert sum(b in 'GC' for b in strand)*2 == len(strand)
    assert recover(m, s[4:12]+s[16:24]+s[28:36]) == data


def test_gc_feasibility_and_version_compatibility():
    from helix.codec import gc_decode, gc_width
    for bounds in [(51,51), (-1,50), (70,30)]:
        with pytest.raises(ValueError):
            Config(mode='gc', gc_min=bounds[0], gc_max=bounds[1])
    with pytest.raises(ValueError):
        gc_decode('AAAAAA')
    m, s = compile_bytes(b'legacy')
    del m['config']['gc_min'], m['config']['gc_max']
    assert recover(m,s) == b'legacy'
    m['version'] = 2
    with pytest.raises(ValueError):
        recover(m,s)


@pytest.mark.parametrize('percent', [0, 100])
def test_gc_extreme_bounds_are_not_inherently_impossible(percent):
    from helix.codec import gc_encode, gc_decode
    data = bytes(range(256))
    dna = gc_encode(data, 3, percent, percent)
    assert sum(b in 'GC' for b in dna)*100 == percent*len(dna)
    independent_run_check(dna, 3)
    assert gc_decode(dna, 3, percent, percent) == data


def test_gc_known_vectors():
    from helix.codec import gc_encode, gc_decode
    assert gc_encode(b'\0') == 'AAACC'
    assert gc_encode(b'\0', 3, 50, 50) == 'AAACCC'
    assert gc_decode('AAACCC', 3, 50, 50) == b'\0'
