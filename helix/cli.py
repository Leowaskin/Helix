import argparse
import json
from pathlib import Path
import tomllib
from .io import read_bytes, read_lines, atomic_write, distinct_paths
from .limits import Limits
from .storage import Config, compile_bytes, recover
from .sync import SyncOptions
from .channel import Channel, damage


def main():
    p = argparse.ArgumentParser(description='Helix simulated DNA storage compiler')
    sub = p.add_subparsers(dest='command', required=True)
    enc = sub.add_parser('encode')
    enc.add_argument('input', type=Path)
    enc.add_argument('output', type=Path)
    enc.add_argument('--config', type=Path)
    sim = sub.add_parser('damage')
    sim.add_argument('input', type=Path)
    sim.add_argument('output', type=Path)
    sim.add_argument('--seed', type=int, default=0)
    for name in vars(Channel()):
        sim.add_argument('--'+name, type=float, default=0)
    dec = sub.add_parser('decode')
    dec.add_argument('manifest', type=Path)
    dec.add_argument('reads', type=Path)
    dec.add_argument('output', type=Path)
    dec.add_argument('--single-indel', action='store_true')
    dec.add_argument('--max-candidates', type=int, default=8192)
    dec.add_argument('--diagnostics', type=Path)
    a = p.parse_args()
    try:
        if a.command == 'encode':
            distinct_paths([a.input, a.config, a.output/'manifest.json', a.output/'strands.txt'])
            config = Config(**tomllib.loads(read_bytes(a.config, 65536).decode())) if a.config else Config()
            manifest, strands = compile_bytes(read_bytes(a.input, Limits().max_output_bytes), config)
            a.output.mkdir(parents=True, exist_ok=True)
            atomic_write(a.output/'manifest.json', (json.dumps(manifest, indent=2)+'\n').encode())
            atomic_write(a.output/'strands.txt', ('\n'.join(strands)+'\n').encode())
        elif a.command == 'damage':
            distinct_paths([a.input, a.output])
            channel = Channel(**{k: getattr(a,k) for k in vars(Channel())})
            reads = damage(read_lines(a.input), channel, a.seed)
            atomic_write(a.output, ''.join(r+'\n' for r in reads).encode())
        else:
            distinct_paths([a.manifest, a.reads, a.output, a.diagnostics])
            stats = {}
            try:
                result = recover(json.loads(read_bytes(a.manifest, 65536)), read_lines(a.reads),
                                 SyncOptions(a.single_indel, a.max_candidates), stats)
            finally:
                if a.diagnostics:
                    atomic_write(a.diagnostics, (json.dumps(stats, indent=2)+'\n').encode())
            atomic_write(a.output, result)
    except (ValueError, OSError, KeyError, TypeError, UnicodeError, RecursionError) as error:
        p.exit(1, f'helix: {error}\n')


if __name__ == '__main__':
    main()
