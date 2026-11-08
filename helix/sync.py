"""Bounded single-indel candidate search; no reference strands or channel log."""
from dataclasses import dataclass


@dataclass(frozen=True)
class SyncOptions:
    enabled: bool = False
    max_candidates: int = 8192

    def __post_init__(self):
        if type(self.enabled) is not bool or type(self.max_candidates) is not int or self.max_candidates < 1:
            raise ValueError('invalid synchronization options')


class SearchLimit(ValueError):
    pass


def candidates(read, expected, options):
    """Enumerate the complete radius-one indel neighborhood or reject on budget.

    Positions that yield identical strings are deduplicated. Budget is checked
    before work, using a conservative count, never by truncating the search.
    """
    if any(base not in 'ACGT' for base in read):
        return ()
    difference = len(read)-expected
    if difference == 0:
        return (read,)
    if not options.enabled or abs(difference) != 1:
        return ()
    bound = len(read) if difference == 1 else 4*(len(read)+1)
    if bound > options.max_candidates:
        raise SearchLimit('complete single-indel search exceeds candidate budget')
    if difference == 1:
        return dict.fromkeys(read[:i]+read[i+1:] for i in range(len(read)))
    return dict.fromkeys(read[:i]+base+read[i:] for i in range(len(read)+1) for base in 'ACGT')
