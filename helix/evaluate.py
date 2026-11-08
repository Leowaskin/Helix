"""Broader synthetic evaluation. Raw trial outcomes retained; no biological claims."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import random
import time
import tracemalloc
from .storage import Config, compile_bytes, recover
from .channel import Channel, damage
from .benchmark import wilson


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--trials',type=int,default=50)
    p.add_argument('--output',type=Path,default=Path('results/evaluation.json'))
    args=p.parse_args()
    if args.trials<1: p.error('trials must be positive')
    rows=[]
    profiles=[('naive',{}),('run3',dict(mode='constrained')),('gc40-60',dict(mode='gc')),
              ('gc50',dict(mode='gc',gc_min=50,gc_max=50))]
    for size in (64,512):
        for pattern in ('zeros','text','random'):
            data=(b'\0'*size if pattern=='zeros' else
                  (b'Helix stores bytes in constrained DNA. '*size)[:size] if pattern=='text' else
                  random.Random(20261105+size).randbytes(size))
            for profile,kw in profiles:
                for parity in (2,4):
                    config=Config(**({'mode':'naive'} if profile=='naive' else kw),parity_shards=parity)
                    tracemalloc.start(); start=time.perf_counter()
                    manifest,strands=compile_bytes(data,config)
                    encode_seconds=time.perf_counter()-start
                    encode_peak=tracemalloc.get_traced_memory()[1]; tracemalloc.stop()
                    for name,channel in [('clean',Channel()),('drop10',Channel(dropout=.1)),
                                         ('mixed',Channel(dropout=.25,substitution=.001))]:
                        outcomes=[]
                        for seed in range(args.trials):
                            reads=damage(strands,channel,seed)
                            # Only trial zero is traced, so ordinary timings are not distorted.
                            if seed==0: tracemalloc.start()
                            start=time.perf_counter(); error=None
                            try: success=recover(manifest,reads)==data
                            except ValueError as exc: success,error=False,str(exc)
                            seconds=time.perf_counter()-start
                            peak=tracemalloc.get_traced_memory()[1] if seed==0 else None
                            if seed==0: tracemalloc.stop()
                            outcomes.append(dict(seed=seed,success=success,error=error,seconds=seconds,
                                                 peak_python_bytes=peak))
                        successes=sum(t['success'] for t in outcomes)
                        nt=sum(map(len,strands))
                        rows.append(dict(payload_bytes=size,pattern=pattern,profile=profile,
                            payload_sha256=hashlib.sha256(data).hexdigest(),config=asdict(config),
                            channel_name=name,channel=asdict(channel),trials=outcomes,
                            successes=successes,recovery_probability=successes/args.trials,
                            wilson95=wilson(successes,args.trials),total_nt=nt,
                            net_bits_per_nt=8*size/nt,overhead_vs_ideal=nt/(4*size)-1,
                            manifest_bytes=len(json.dumps(manifest,indent=2).encode())+1,
                            encode_seconds=encode_seconds,encode_peak_python_bytes=encode_peak))
    report=dict(format=1,python=platform.python_version(),platform=platform.platform(),
                reedsolo='1.7.0',payload_seed_rule='20261105 + payload_bytes',
                channel_seeds=list(range(args.trials)),sync_enabled=False,rows=rows)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(f'{len(rows)} scenarios, {len(rows)*args.trials} file recovery trials: {args.output}')


if __name__=='__main__': main()
