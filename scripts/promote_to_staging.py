import sys
import os
import shutil
from nbconvert import PythonExporter
import nbformat

def generate_staging_file(notebook_path, target_dir='staging/mt5'):
    os.makedirs(target_dir, exist_ok=True)
    
    with open(notebook_path, 'r', encoding='utf-8') as f:
        nb = nbformat.read(f, as_version=4)
    
    exporter = PythonExporter()
    source, _ = exporter.from_notebook_node(nb)
    
    strategy_name = os.path.basename(os.path.dirname(notebook_path))
    output_path = os.path.join(target_dir, f"{strategy_name}.py")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('import logging\n')
        f.write('import requests\n')
        f.write('from datetime import datetime\n\n')
        f.write('# Auto-generated staging strategy with monitoring hooks\n\n')
        f.write(source)
        f.write('\n\ndef daily_report(pnl, trades, drawdown):\n')
        f.write('    webhook_url = "https://discord.com/api/webhooks/..."\n')
        f.write('    message = f"Strategy {strategy_name} staging: PnL={pnl}, Trades={trades}, DD={drawdown}"\n')
        f.write('    requests.post(webhook_url, json={"content": message})\n\n')
        f.write('if __name__ == "__main__":\n')
        f.write('    run_strategy()  # assumes strategy has run_strategy()\n')
    
    print(f"Staging file generated: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python promote_to_staging.py <notebook_folder>")
        sys.exit(1)
    generate_staging_file(sys.argv[1])