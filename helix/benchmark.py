"""Run: python -m helix.benchmark --trials 20 --output results/benchmark.json"""
import argparse
from dataclasses import asdict
import hashlib
import json
import platform
import random
import time
import tracemalloc
from pathlib import Path
from .storage import Config, compile_bytes, recover
from .channel import Channel, damage
from .codec import count, gc_count, gc_width


def wilson(success, total):
    z = 1.95996398454
    p = success/total
    denominator = 1+z*z/total
    center = (p+z*z/(2*total))/denominator
    delta = z*((p*(1-p)/total+z*z/(4*total*total))**.5)/denominator
    return [max(0, center-delta), min(1, center+delta)]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--trials', type=int, default=20)
    p.add_argument('--output', type=Path, default=Path('results/benchmark.json'))
    a = p.parse_args()
    if a.trials < 1:
        p.error('trials must be positive')
    data = random.Random(20261103).randbytes(512)
    rows = []
    for mode, limit, low, high in [('naive',3,40,60), ('constrained',1,40,60),
                                    ('constrained',3,40,60), ('gc',3,40,60), ('gc',3,50,50)]:
        for parity in (2,4):
            c = Config(mode=mode, max_run=limit, parity_shards=parity, gc_min=low, gc_max=high)
            for dropout, substitution in [(0,0), (.1,0), (.25,0), (.1,.001)]:
                channel = Channel(dropout=dropout, substitution=substitution, duplication=.1)
                count.cache_clear()
                gc_count.cache_clear()
                gc_width.cache_clear()
                tracemalloc.start()
                start = time.perf_counter()
                m, strands = compile_bytes(data, c)
                encode_seconds = time.perf_counter()-start
                encode_peak = tracemalloc.get_traced_memory()[1]
                tracemalloc.stop()
                success, elapsed, peaks = 0, [], []
                for seed in range(a.trials):
                    reads = damage(strands, channel, seed)
                    tracemalloc.start()
                    start = time.perf_counter()
                    try:
                        result = recover(m, reads)
                        success += result == data
                    except ValueError:
                        pass
                    elapsed.append(time.perf_counter()-start)
                    peaks.append(tracemalloc.get_traced_memory()[1])
                    tracemalloc.stop()
                nt = sum(map(len,strands))
                rows.append(dict(config=asdict(c), channel=asdict(channel),
                    successes=success, trials=a.trials, recovery_probability=success/a.trials,
                    wilson95=wilson(success,a.trials), total_nt=nt,
                    net_bits_per_nt=8*len(data)/nt,
                    overhead_vs_ideal=nt/(4*len(data))-1,
                    manifest_bytes=len(json.dumps(m,indent=2).encode())+1,
                    encode_seconds=encode_seconds, encode_peak_python_bytes=encode_peak,
                    mean_decode_seconds=sum(elapsed)/a.trials,
                    max_decode_peak_python_bytes=max(peaks)))
    report = dict(format=1, python=platform.python_version(), platform=platform.platform(),
                  reedsolo='1.7.0', data_seed=20261103, channel_seeds=list(range(a.trials)),
                  payload_bytes=len(data), payload_sha256=hashlib.sha256(data).hexdigest(), rows=rows)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(f'{len(rows)} scenarios written to {a.output}')


if __name__ == '__main__':
    main()
