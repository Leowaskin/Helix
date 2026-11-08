"""Paired recovery trials: identical read pools, synchronization off versus on."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import random
import time
import tracemalloc
from .benchmark import wilson
from .channel import Channel, damage
from .storage import Config, compile_bytes, recover
from .sync import SyncOptions


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--trials', type=int, default=10)
    p.add_argument('--output', type=Path, default=Path('results/indel-benchmark.json'))
    a = p.parse_args()
    if a.trials < 1:
        p.error('trials must be positive')
    data = random.Random(20261105).randbytes(32)
    rows = []
    for mode in ('naive', 'constrained', 'gc'):
        c = Config(mode=mode, data_shards=2, parity_shards=1)
        m, strands = compile_bytes(data, c)
        for rate in (0, .001, .005):
            channel = Channel(insertion=rate, deletion=rate)
            trials = []
            for seed in range(a.trials):
                reads = damage(strands, channel, seed)
                outcomes = []
                for enabled in (False, True):
                    stats = {}
                    tracemalloc.start()
                    start = time.perf_counter()
                    error = None
                    try:
                        success = recover(m, reads, SyncOptions(enabled), stats) == data
                    except ValueError as exc:
                        success, error = False, str(exc)
                    seconds = time.perf_counter()-start
                    peak = tracemalloc.get_traced_memory()[1]
                    tracemalloc.stop()
                    outcomes.append(dict(enabled=enabled, success=success, error=error,
                                         seconds=seconds, peak_python_bytes=peak, diagnostics=stats))
                trials.append(dict(seed=seed, reads_sha256=hashlib.sha256('\n'.join(reads).encode()).hexdigest(), outcomes=outcomes))
            summaries = []
            for index in (0,1):
                successes = sum(t['outcomes'][index]['success'] for t in trials)
                summaries.append(dict(enabled=bool(index), successes=successes,
                                      recovery_probability=successes/a.trials, wilson95=wilson(successes,a.trials)))
            nt = sum(map(len,strands))
            rows.append(dict(config=asdict(c), channel=asdict(channel), total_nt=nt,
                             net_bits_per_nt=8*len(data)/nt, overhead_vs_ideal=nt/(4*len(data))-1,
                             manifest_bytes=len(json.dumps(m,indent=2).encode())+1,
                             summaries=summaries, trials=trials))
    report = dict(format=1, python=platform.python_version(), platform=platform.platform(),
                  reedsolo='1.7.0', data_seed=20261105, payload_bytes=len(data),
                  payload_sha256=hashlib.sha256(data).hexdigest(), max_candidates=8192, rows=rows)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(f'{len(rows)} paired scenarios written to {a.output}')


if __name__ == '__main__':
    main()
