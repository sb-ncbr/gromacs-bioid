"""Similarity engine for the stats tooling: a re-export of
scripts/validation_similarity.py (GitHub #36).

This directory used to carry its own 2026-10-05 fork of the engine, which
never got the F-7 rule (a failed lookup must not be cached as similarity
0.0) nor the local-first resolution; `campaign_stats.py --sim` run from here
imported that fork. One engine now: the main module is loaded by path (this
file shadows its name on sys.path) and every name re-exported.
"""
import importlib.util
import os
import sys

_MAIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "validation_similarity.py")
_spec = importlib.util.spec_from_file_location("_validation_similarity_main", _MAIN)
_main = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _main
_spec.loader.exec_module(_main)
globals().update({k: v for k, v in vars(_main).items() if not k.startswith("__")})
