"""Finite resource policy for the in-memory prototype."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Limits:
    max_output_bytes: int = 1024 * 1024
    max_total_nt: int = 16 * 1024 * 1024
    max_reads: int = 100_000
    max_total_candidates: int = 1_000_000

    def __post_init__(self):
        if any(type(v) is not int or v < 1 for v in vars(self).values()):
            raise ValueError('resource limits must be positive integers')
