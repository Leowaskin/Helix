"""Generate portable benchmark figures and a report from saved raw results."""
import argparse
import json
from pathlib import Path
import statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def interval(ax, x, summary, color, label=None):
    y=summary['recovery_probability']; lo,hi=summary['wilson95']
    ax.errorbar(x,y,yerr=[[max(0,y-lo)],[max(0,hi-y)]],fmt='o',capsize=4,color=color,label=label)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--results',type=Path,default=Path('results'))
    args=parser.parse_args(); root=args.results
    broad=json.loads((root/'evaluation.json').read_text())
    indel=json.loads((root/'indel-expanded.json').read_text())
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    profiles=['naive','run3','gc40-60','gc50']; colors=['#19738c','#d57928']
    selected=[r for r in broad['rows'] if r['pattern']=='random' and r['payload_bytes']==512]
    for offset,parity in enumerate((2,4)):
        rows=[next(r for r in selected if r['profile']==p and r['config']['parity_shards']==parity and r['channel_name']=='mixed') for p in profiles]
        x=[i+(offset-.5)*.2 for i in range(4)]
        axes[0,0].plot(x,[r['net_bits_per_nt'] for r in rows],'o-',color=colors[offset],label=f'{parity} outer parity')
        for i,row in enumerate(rows): interval(axes[0,1],x[i],row,colors[offset],f'{parity} outer parity' if i==0 else None)
    for ax in axes[0]: ax.set_xticks(range(4),profiles); ax.grid(axis='y',alpha=.2); ax.legend()
    axes[0,0].set(title='Density: 512-byte random payload',ylabel='Net payload bits / nucleotide')
    axes[0,1].set(title='Recovery: 25% dropout + 0.1% substitutions',ylabel='File recovery probability',ylim=(-.05,1.05))
    modes=['naive','constrained','gc']
    rows=[next(r for r in indel['rows'] if r['config']['mode']==m and r['channel']['insertion']==.001) for m in modes]
    for i,row in enumerate(rows):
        for policy in (0,1):
            interval(axes[1,0],i+(policy-.5)*.2,row['summaries'][policy],colors[policy],('Search off','Search on')[policy] if i==0 else None)
    axes[1,0].set(xticks=range(3),xticklabels=modes,ylim=(-.05,1.05),ylabel='File recovery probability',title='Paired indel recovery: 0.1% each indel type')
    for policy in (0,1):
        means=[1000*statistics.mean(t['outcomes'][policy]['seconds'] for t in row['trials']) for row in rows]
        axes[1,1].plot(range(3),means,'o-',color=colors[policy],label=('Search off','Search on')[policy])
    axes[1,1].set(xticks=range(3),xticklabels=modes,yscale='log',ylabel='Mean decode milliseconds (log scale)',title='Paired indel runtime (includes tracing)')
    for ax in axes[1]: ax.legend(); ax.grid(axis='y',alpha=.2)
    fig.suptitle('Helix • synthetic channel evaluation\nRecovery intervals: Wilson 95%; no biological calibration',fontsize=14)
    fig.savefig(root/'evaluation.png',dpi=180)
    fig.savefig(root/'evaluation.pdf')
    plt.close(fig)
    count=sum(len(r['trials']) for r in broad['rows'])
    clean=[r for r in broad['rows'] if r['channel_name']=='clean']
    clean_success=sum(r['successes'] for r in clean); clean_n=sum(len(r['trials']) for r in clean)
    lines=['# Helix portfolio evaluation','',f'{len(broad["rows"])} broad scenarios and {count:,} file recovery trials, plus',
           f'{len(indel["rows"])} paired indel scenarios with {len(indel["rows"][0]["trials"])} seeds each.',
           '',f'Clean recovery: **{clean_success}/{clean_n}**. Payloads: 64 and 512 bytes;',
           'patterns: all zeros, repeated text and seeded random bytes. Four codec profiles,',
           'two outer-parity budgets, and clean/dropout/mixed channels are included.',
           '', '![Recovery, density and runtime](evaluation.png)', '',
           '## Paired single-indel results', '',
           '| Codec | Search off | Search on | Mean ms off/on |','|---|---:|---:|---:|']
    for row in rows:
        n=len(row['trials']); off,on=row['summaries']
        ms=[1000*statistics.mean(t['outcomes'][i]['seconds'] for t in row['trials']) for i in (0,1)]
        lines.append(f'| {row["config"]["mode"]} | {off["successes"]}/{n} | {on["successes"]}/{n} | {ms[0]:.1f} / {ms[1]:.1f} |')
    lines += ['', 'Rates in this table are 0.1% insertion and 0.1% deletion per original base.',
        'Search off/on use the same read pool within each seed. Different codecs have',
        'different strings/lengths; their damage realizations are not physically matched.',
        '', '## Interpretation and limits', '',
        'Stricter GC coding and added parity consume density. Search improves recovery',
        'for single-indel damage by spending CPU without adding bases. This simulator',
        'assigns errors independently of sequence context, so it cannot measure the',
        'biochemical benefits of constraints. Close recovery counts should be assessed',
        'using intervals rather than ranked. Repeated tests of one encoded payload',
        'estimate behavior conditional on that payload and channel, not all files.',
        '', 'These files are still small; this is a portfolio evaluation, not a production',
        'scale or wet-lab validation. SHA-256, CRC and the external manifest remain part',
        'of the assumptions. Density includes all DNA fields, padding and parity;',
        'manifest bytes are reported separately in raw data. No synthesis copies or',
        'sequencing coverage are modeled.', '',
        'Broad encode times and trial-zero decode times include tracemalloc; later',
        'broad decode trials do not. All paired indel times include tracing. Memory',
        'fields are Python allocations, not RSS. Cache state and host load affect timing.',
        '', '## Reproduce', '', '```sh',
        "python -m pip install '.[test,plot]'", 'python -m helix.evaluate --trials 50',
        'python -m helix.indel_benchmark --trials 50 --output results/indel-expanded.json',
        'python -m helix.report', '```', '',
        'Raw evidence: [broad trials](evaluation.json), [paired trials](indel-expanded.json).',
        'Payload hashes, seed rules, configuration, versions, errors and timings are retained.',
        'Original small reports remain historical snapshots; this report uses the expanded runs.']
    (root/'EVALUATION.md').write_text('\n'.join(lines)+'\n')
    print(root/'EVALUATION.md')


if __name__=='__main__': main()
