import copy
import json
from pathlib import Path
import subprocess
import sys
import pytest
from hypothesis import given, settings, strategies as st
from helix.limits import Limits
from helix.storage import compile_bytes, recover, Config
from helix.sync import SyncOptions
from helix.io import atomic_write


@pytest.mark.parametrize('field,value', [
    ('version', True), ('size', True), ('groups', 1.5), ('size', -1),
    ('size', 10**100), ('sha256', 'ab'), ('sha256', 'g'*64),
    ('sha256', 'A'*64), ('config', []), ('strand_length', '220')])
def test_bad_manifest(field, value):
    m,s = compile_bytes(b'x')
    m[field] = value
    with pytest.raises(ValueError):
        recover(m,s)


@given(st.one_of(st.none(), st.booleans(), st.integers(), st.text(), st.lists(st.integers())))
def test_wrong_manifest_shape(value):
    with pytest.raises(ValueError):
        recover(value, [])


def test_missing_unknown_fields_and_limits():
    m,s = compile_bytes(b'x')
    for field in m:
        bad=copy.deepcopy(m)
        del bad[field]
        with pytest.raises(ValueError): recover(bad,s)
    with pytest.raises(ValueError): recover(dict(m, extra=1),s)
    with pytest.raises(ValueError): compile_bytes(b'xx', limits=Limits(max_output_bytes=1))
    with pytest.raises(ValueError): compile_bytes(b'x', limits=Limits(max_total_nt=1))
    with pytest.raises(ValueError): recover(m,s,limits=Limits(max_reads=1))
    with pytest.raises(ValueError): recover(m,s,limits=Limits(max_total_candidates=1))
    for read in (None, 123, 'A'*10000):
        with pytest.raises(ValueError): recover(m,[read])


def cli(*args):
    return subprocess.run([sys.executable,'-m','helix.cli',*map(str,args)],capture_output=True,text=True)


def test_cli_failure_preserves_output_and_input(tmp_path):
    manifest,strands=compile_bytes(b'hello')
    m,r,o,d=[tmp_path/x for x in ('manifest.json','reads.txt','out.bin','diag.json')]
    m.write_text(json.dumps(manifest)); r.write_text(''); o.write_bytes(b'keep')
    result=cli('decode',m,r,o,'--diagnostics',d)
    assert result.returncode == 1 and 'Traceback' not in result.stderr
    assert o.read_bytes()==b'keep' and json.loads(d.read_text())['reads']==0
    result=cli('decode',m,r,o,'--diagnostics',m)
    assert result.returncode==1 and json.loads(m.read_text())==manifest
    r.write_text('A'*5000)
    assert cli('decode',m,r,o).returncode==1
    m.write_text('[]')
    assert cli('decode',m,r,o).returncode==1


def test_cli_roundtrip_and_atomic_io(tmp_path):
    source=tmp_path/'source'; source.write_bytes(bytes(range(256)))
    pool=tmp_path/'pool'; output=tmp_path/'restored'
    assert cli('encode',source,pool).returncode==0
    assert cli('decode',pool/'manifest.json',pool/'strands.txt',output).returncode==0
    assert output.read_bytes()==source.read_bytes()
    atomic_write(output,b'new'); assert output.read_bytes()==b'new'
    assert not list(tmp_path.glob('tmp*'))


def test_required_config_and_pool_budget():
    m,s=compile_bytes(b'x')
    with pytest.raises(ValueError): recover(m,s,limits=Limits(max_total_nt=1))
    m['config']={}
    with pytest.raises(ValueError): recover(m,s)


def test_deep_json_and_non_ascii_are_cli_errors(tmp_path):
    m,r,o=[tmp_path/x for x in ('manifest','reads','output')]
    m.write_text('['*10000+'0'+']'*10000); r.write_text('')
    result=cli('decode',m,r,o)
    assert result.returncode==1 and 'Traceback' not in result.stderr
    manifest,_=compile_bytes(b'x'); m.write_text(json.dumps(manifest))
    r.write_bytes(b'\xff')
    result=cli('decode',m,r,o)
    assert result.returncode==1 and 'Traceback' not in result.stderr
