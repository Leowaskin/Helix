"""A deterministic encode–damage–recover portfolio demonstration."""
import argparse
import hashlib
import json
from pathlib import Path
from .storage import Config, compile_bytes, recover
from .sync import SyncOptions
from .io import atomic_write


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path('results/portfolio-demo'))
    args=parser.parse_args()
    data=b'Helix: DNA meets computer science.\n'+bytes(range(256))
    config=Config(mode='gc',gc_min=50,gc_max=50)
    manifest,strands=compile_bytes(data,config)
    # Deterministic events: one dropout per group; one insertion/deletion in each
    # remaining read. Record exact damage policy, never provide it to decoder.
    reads=[]
    for index,strand in enumerate(strands):
        if index % 12 == 0: continue
        pos=(index*17)%len(strand)
        reads.append(strand[:pos]+('A'+strand[pos:] if index%2 else strand[pos+1:]))
    reads=list(reversed(reads))+reads[:1]
    try:
        recover(manifest,reads)
        raise AssertionError('expected baseline failure')
    except ValueError:
        pass
    stats={}
    restored=recover(manifest,reads,SyncOptions(True),stats)
    assert restored==data
    args.output.mkdir(parents=True,exist_ok=True)
    for name,blob in [('original.bin',data),('restored.bin',restored),
                      ('manifest.json',(json.dumps(manifest,indent=2)+'\n').encode()),
                      ('strands.txt',('\n'.join(strands)+'\n').encode()),
                      ('reads.txt',('\n'.join(reads)+'\n').encode())]:
        atomic_write(args.output/name,blob)
    summary=dict(bytes=len(data),sha256=hashlib.sha256(restored).hexdigest(),
                 baseline='failed as expected',synchronization='byte-identical recovery',
                 damage='drop shard 0 per group; alternate one insertion/deletion; reverse and duplicate',
                 max_candidates=8192,diagnostics=stats)
    atomic_write(args.output/'summary.json',(json.dumps(summary,indent=2)+'\n').encode())
    print(json.dumps(summary,indent=2))


if __name__=='__main__': main()
