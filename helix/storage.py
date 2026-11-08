import hashlib
import struct
import zlib
from dataclasses import asdict, dataclass
from .limits import Limits
from .sync import SyncOptions, SearchLimit, candidates
from reedsolo import RSCodec, ReedSolomonError
from .codec import encode, decode, valid, width, gc_width, gc_encode, gc_decode


@dataclass(frozen=True)
class Config:
    mode: str = 'constrained'
    max_run: int = 3
    chunk_bytes: int = 16
    data_shards: int = 8
    parity_shards: int = 4
    inner_parity: int = 12
    gc_min: int = 40
    gc_max: int = 60

    def __post_init__(self):
        if any(type(getattr(self, name)) is not int for name in ('max_run', 'chunk_bytes', 'data_shards', 'parity_shards', 'inner_parity')):
            raise ValueError('numeric configuration fields must be integers')
        if self.mode not in ('naive', 'constrained', 'gc') or self.max_run not in (1,2,3):
            raise ValueError('unsupported codec or max_run')
        if not (1 <= self.data_shards <= 254 and 1 <= self.parity_shards and
                self.data_shards + self.parity_shards <= 255):
            raise ValueError('outer RS requires 1 <= k < n <= 255')
        if not (1 <= self.inner_parity <= 128 and 1 <= self.chunk_bytes and
                16 + self.chunk_bytes + self.inner_parity <= 255):
            raise ValueError('inner RS frame exceeds 255 symbols')
        gc_width(self.max_run, self.gc_min, self.gc_max)


def compile_bytes(data, config=Config(), limits=Limits()):
    if not isinstance(data, bytes):
        raise ValueError('input must be bytes')
    if len(data) > limits.max_output_bytes:
        raise ValueError('input exceeds output byte limit')
    c = config
    digest = hashlib.sha256(data).hexdigest()
    file_id = bytes.fromhex(digest)[:8]
    groups = max(1, (len(data)+c.chunk_bytes*c.data_shards-1)//(c.chunk_bytes*c.data_shards))
    if groups * (c.data_shards+c.parity_shards) > 2**32:
        raise ValueError('index space exhausted')
    strand_count = groups*(c.data_shards+c.parity_shards)
    block_width = 4 if c.mode == 'naive' else gc_width(c.max_run, c.gc_min, c.gc_max) if c.mode == 'gc' else width(c.max_run)
    if strand_count > limits.max_reads or strand_count*(16+c.chunk_bytes+c.inner_parity)*block_width > limits.max_total_nt:
        raise ValueError('compiled pool exceeds resource limit')
    outer, inner = RSCodec(c.parity_shards), RSCodec(c.inner_parity)
    strands = []
    for group in range(groups):
        start = group*c.chunk_bytes*c.data_shards
        block = data[start:start+c.chunk_bytes*c.data_shards].ljust(c.chunk_bytes*c.data_shards, b'\0')
        columns = [outer.encode(block[j::c.chunk_bytes]) for j in range(c.chunk_bytes)]
        for shard in range(c.data_shards+c.parity_shards):
            payload = bytes(col[shard] for col in columns)
            index = group*(c.data_shards+c.parity_shards)+shard
            frame = file_id + struct.pack('>I', index) + payload
            frame += struct.pack('>I', zlib.crc32(frame))
            dna = (gc_encode(inner.encode(frame), c.max_run, c.gc_min, c.gc_max)
                   if c.mode == 'gc' else encode(inner.encode(frame), c.mode, c.max_run))
            if c.mode in ('constrained', 'gc') and not valid(dna, c.max_run):
                raise AssertionError('compiler violated strand constraint')
            if c.mode == 'gc' and not (c.gc_min*len(dna) <=
                    100*sum(b in 'GC' for b in dna) <= c.gc_max*len(dna)):
                raise AssertionError('compiler violated full-strand GC constraint')
            strands.append(dna)
    return {'version': 2 if c.mode == 'gc' else 1, 'config': asdict(c), 'size': len(data), 'sha256': digest,
            'groups': groups, 'strand_length': len(strands[0]), 'primers': []}, strands


def recover(manifest, reads, sync=SyncOptions(), diagnostics=None, limits=Limits()):
    fields = {'version', 'config', 'size', 'sha256', 'groups', 'strand_length', 'primers'}
    if not isinstance(manifest, dict) or set(manifest) != fields:
        raise ValueError('manifest fields are missing or unknown')
    if type(manifest['version']) is not int or manifest['version'] not in (1, 2) or manifest['primers'] != []:
        raise ValueError('unsupported format')
    if not isinstance(manifest['config'], dict):
        raise ValueError('manifest config must be an object')
    required_config = {'mode', 'max_run', 'chunk_bytes', 'data_shards', 'parity_shards', 'inner_parity'}
    if not required_config <= set(manifest['config']):
        raise ValueError('required configuration fields are missing')
    try:
        c = Config(**manifest['config'])
    except TypeError as error:
        raise ValueError('unknown configuration field') from error
    if (manifest['version'] == 2) != (c.mode == 'gc'):
        raise ValueError('codec and format version disagree')
    if any(type(manifest[k]) is not int for k in ('size', 'groups', 'strand_length')):
        raise ValueError('manifest counts must be integers')
    size = manifest['size']
    group_bytes = c.chunk_bytes*c.data_shards
    groups = max(1, (size+group_bytes-1)//group_bytes)
    if not 0 <= size <= limits.max_output_bytes:
        raise ValueError('manifest size exceeds output byte limit')
    if manifest['groups'] != groups or groups*(c.data_shards+c.parity_shards) > 2**32:
        raise ValueError('inconsistent manifest group count')
    digest = manifest['sha256']
    if not isinstance(digest, str) or len(digest) != 64 or any(ch not in '0123456789abcdef' for ch in digest):
        raise ValueError('manifest SHA-256 must be 64 lowercase hex characters')
    expected = (16+c.chunk_bytes+c.inner_parity)*(4 if c.mode == 'naive' else gc_width(c.max_run, c.gc_min, c.gc_max) if c.mode == 'gc' else width(c.max_run))
    if manifest['strand_length'] != expected:
        raise ValueError('inconsistent strand length')
    fid = bytes.fromhex(manifest['sha256'])[:8]
    n = c.data_shards+c.parity_shards
    found, conflicts = {}, set()
    inner, outer = RSCodec(c.inner_parity), RSCodec(c.parity_shards)
    stats = dict(reads=0, accepted_reads=0, repaired_reads=0, rejected_reads=0,
                 ambiguous_reads=0, budget_rejections=0, candidates_tested=0)
    if diagnostics is not None:
        diagnostics.clear()
        diagnostics.update(stats)
        stats = diagnostics
    input_bases = 0
    for read in reads:
        if stats['reads'] >= limits.max_reads:
            raise ValueError('read count exceeds resource limit')
        stats['reads'] += 1
        input_bases += len(read) if isinstance(read, str) else 0
        if input_bases > limits.max_total_nt:
            raise ValueError('read pool exceeds nucleotide resource limit')
        if not isinstance(read, str) or abs(len(read)-expected) > 1:
            stats['rejected_reads'] += 1
            continue
        frames = set()
        try:
            neighborhood = candidates(read, expected, sync)
        except SearchLimit:
            stats['budget_rejections'] += 1
            stats['rejected_reads'] += 1
            continue
        for candidate in neighborhood:
            if stats['candidates_tested'] >= limits.max_total_candidates:
                raise ValueError('total candidate count exceeds resource limit')
            stats['candidates_tested'] += 1
            try:
                raw = (gc_decode(candidate, c.max_run, c.gc_min, c.gc_max) if c.mode == 'gc'
                       else decode(candidate, c.mode, c.max_run))
                frame = bytes(inner.decode(raw)[0])
                if len(frame) != 16+c.chunk_bytes or frame[:8] != fid:
                    continue
                if zlib.crc32(frame[:-4]) != struct.unpack('>I', frame[-4:])[0]:
                    continue
                index = struct.unpack('>I', frame[8:12])[0]
                if index >= manifest['groups']*n:
                    continue
                frames.add(frame)
            except (ValueError, ReedSolomonError, IndexError):
                continue
        # Multiple candidate strings may legitimately recover the same frame.
        if len(frames) != 1:
            stats['ambiguous_reads'] += int(len(frames) > 1)
            stats['rejected_reads'] += 1
            continue
        frame = frames.pop()
        stats['accepted_reads'] += 1
        stats['repaired_reads'] += int(len(read) != expected)
        index = struct.unpack('>I', frame[8:12])[0]
        payload = frame[12:-4]
        if index in found and found[index] != payload:
            conflicts.add(index)
        found[index] = payload
    output = bytearray()
    for group in range(manifest['groups']):
        missing = [s for s in range(n) if group*n+s not in found or group*n+s in conflicts]
        if len(missing) > c.parity_shards:
            raise ValueError(f'group {group}: {len(missing)} erasures exceed {c.parity_shards}')
        rows = [bytearray() for _ in range(c.data_shards)]
        for j in range(c.chunk_bytes):
            column = bytes(found[group*n+s][j] if s not in missing else 0 for s in range(n))
            decoded = outer.decode(column, erase_pos=missing)[0]
            for s in range(c.data_shards):
                rows[s].append(decoded[s])
        output.extend(b''.join(rows))
    result = bytes(output[:manifest['size']])
    if hashlib.sha256(result).hexdigest() != manifest['sha256']:
        raise ValueError('file SHA-256 mismatch')
    return result
