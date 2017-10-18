"""
quantgov.corpora.builtins: Functions for analyzing a single Document
"""
import sys

from pathlib import Path


def load_driver(corpus):
    corpus = Path(corpus)
    if corpus.name == 'driver.py':
        corpus = corpus.parent
    sys.path.insert(0, str(corpus))
    from driver import driver
    sys.path.pop(0)
    return driver
