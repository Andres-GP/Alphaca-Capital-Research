import os
import sys
import json

# Notebooks call plt.show(); without a GUI backend this must not block.
os.environ.setdefault("MPLBACKEND", "Agg")

import nbformat
from nbconvert import PythonExporter
import pandas as pd
import numpy as np

sys.path.append('research_development/utils')
from metrics import sharpe_ratio, max_drawdown


class _NoOpIPython:
    """Stand-in for get_ipython(): ignores %magics and shell escapes when running as a script."""
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


def validate_notebook(notebook_path):
    with open(notebook_path, 'r', encoding='utf-8') as f:
        nb = nbformat.read(f, as_version=4)
    
    exporter = PythonExporter()
    source, _ = exporter.from_notebook_node(nb)
    
    # `display` and `get_ipython` only exist inside Jupyter; the exported script uses them.
    local_ns = {
        "display": lambda *args, **kwargs: None,
        "get_ipython": lambda: _NoOpIPython(),
    }
    exec(source, local_ns)
    
    metrics = local_ns.get('metrics', {})
    if not metrics:
        raise ValueError("Notebook must define a 'metrics' dict with 'sharpe', 'max_drawdown', 'num_trades'")
    
    sharpe = metrics.get('sharpe', 0)
    dd = metrics.get('max_drawdown', 0)
    num_trades = metrics.get('num_trades', 0)
    
    print(f"Sharpe: {sharpe:.2f}, Max DD: {dd*100:.2f}%, Trades: {num_trades}")
    
    if sharpe < 1.0:
        print("FAIL: Sharpe ratio below 1.0")
        sys.exit(1)
    if dd < -0.15:
        print("FAIL: Max drawdown below -15%")
        sys.exit(1)
    if num_trades < 200:
        print("FAIL: Fewer than 200 trades")
        sys.exit(1)
    
    print("Validation passed")
    sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python validate_strategy.py <notebook_path>")
        sys.exit(1)
    validate_notebook(sys.argv[1])