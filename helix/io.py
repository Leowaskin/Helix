"""Bounded reads and atomic replacement for CLI artifacts."""
import os
from pathlib import Path
import tempfile


def read_bytes(path, maximum):
    with path.open('rb') as stream:
        data = stream.read(maximum+1)
    if len(data) > maximum:
        raise ValueError(f'{path}: file exceeds {maximum} byte limit')
    return data


def read_lines(path, maximum_line=4096):
    with path.open('r', encoding='ascii') as stream:
        while True:
            line = stream.readline(maximum_line+2)
            if not line:
                return
            if len(line.rstrip('\r\n')) > maximum_line:
                raise ValueError('read line exceeds resource limit')
            yield line.rstrip('\r\n')


def atomic_write(path, data):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def distinct_paths(paths):
    resolved = [p.resolve() for p in paths if p is not None]
    if len(set(resolved)) != len(resolved):
        raise ValueError('input, output and diagnostics paths must be distinct')
    existing = [p for p in paths if p is not None and p.exists()]
    if any(os.path.samefile(a, b) for i,a in enumerate(existing) for b in existing[i+1:]):
        raise ValueError('paths refer to the same file')
