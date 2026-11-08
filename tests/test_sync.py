import itertools
import pytest
from hypothesis import given, settings, strategies as st
from helix.sync import SyncOptions, SearchLimit, candidates
from helix.storage import Config, compile_bytes, recover


def test_exhaustive_neighborhood():
    on = SyncOptions(True)
    for length in range(1, 5):
        for word in itertools.product('ACGT', repeat=length):
            original = ''.join(word)
            for i in range(length):
                assert original in candidates(original[:i]+original[i+1:], length, on)
            for i in range(length+1):
                for base in 'ACGT':
                    assert original in candidates(original[:i]+base+original[i:], length, on)


@pytest.mark.parametrize('mode', ['naive', 'constrained', 'gc'])
def test_indel_positions_including_identifiers_and_parity(mode):
    m, strands = compile_bytes(b'X', Config(mode=mode, data_shards=1, parity_shards=1, chunk_bytes=1, inner_parity=2))
    strand = strands[0]
    for i in [0, 1, len(strand)//2, len(strand)-1]:
        for read in [strand[:i]+strand[i+1:], strand[:i]+'G'+strand[i:]]:
            stats = {}
            assert recover(m, [read], SyncOptions(True), stats) == b'X'
            assert stats['repaired_reads'] == 1
            with pytest.raises(ValueError):
                recover(m, [read])


@settings(max_examples=8, deadline=None)
@given(st.binary(min_size=1, max_size=16), st.integers(min_value=0, max_value=1000))
def test_generated_single_deletion(data, position):
    m, s = compile_bytes(data, Config(chunk_bytes=16, data_shards=1, parity_shards=1))
    pos = position % len(s[0])
    read = s[0][:pos]+s[0][pos+1:]
    assert recover(m, [read], SyncOptions(True)) == data


def test_limits_invalid_and_multiple_indels():
    m, s = compile_bytes(b'X')
    with pytest.raises(SearchLimit):
        candidates(s[0][1:], len(s[0]), SyncOptions(True, 1))
    stats = {}
    with pytest.raises(ValueError):
        recover(m, [s[0][1:]], SyncOptions(True, 1), stats)
    assert stats['budget_rejections'] == 1
    assert stats['candidates_tested'] == 0
    assert not candidates('N', 2, SyncOptions(True))
    assert not candidates('AC', 4, SyncOptions(True))
    for bad in [0, -1, 1.5, True]:
        with pytest.raises(ValueError):
            SyncOptions(True, bad)


def test_ambiguous_frames_are_rejected(monkeypatch):
    import helix.storage as storage
    m, s = compile_bytes(b'X', Config(data_shards=1, parity_shards=1))
    monkeypatch.setattr(storage, 'candidates', lambda *args: s)
    stats = {}
    with pytest.raises(ValueError):
        recover(m, [s[0]], SyncOptions(True), stats)
    assert stats['ambiguous_reads'] == 1
    assert stats['accepted_reads'] == 0


def test_duplicates_of_same_repaired_frame_are_not_ambiguous():
    m, s = compile_bytes(b'X', Config(mode='naive', data_shards=1, parity_shards=1))
    read = s[0][:1]+s[0][0]+s[0][1:]
    stats = {}
    assert recover(m, [read, read], SyncOptions(True), stats) == b'X'
    assert stats['ambiguous_reads'] == 0
