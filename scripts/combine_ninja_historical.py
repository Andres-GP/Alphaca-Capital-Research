#!/usr/bin/env python3
"""
Combine NinjaTrader exports respecting original granularity.
- 6 columns -> 1-min OHLCV (saved as ..._1min.csv)
- 5 columns -> tick data (saved as ..._ticks.csv)
IS files (no 'OOS' in name) are always saved as 1-min.
OOS files are saved according to their detected columns.
For large tick files, reads in chunks with progress bar.
"""

import os
import pandas as pd
from tqdm import tqdm

def detect_columns(filepath: str) -> int:
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                return len(line.split(';'))
    return 0

def read_1min_file(filepath: str) -> pd.DataFrame:
    df = pd.read_csv(filepath, sep=';', header=None,
                     names=['DT', 'Open', 'High', 'Low', 'Close', 'Volume'])
    df['DateTime'] = pd.to_datetime(df['DT'], format='%Y%m%d %H%M%S', errors='coerce')
    df = df.dropna(subset=['DateTime'])
    df.set_index('DateTime', inplace=True)
    df.drop('DT', axis=1, inplace=True)
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    return df.dropna()

def read_ticks_file_chunked(filepath: str, chunksize=500000) -> pd.DataFrame:
    """Read a large tick file in chunks, show progress, return concatenated DataFrame."""
    # First, count total lines for progress bar
    total_lines = 0
    with open(filepath, 'r') as f:
        for _ in f:
            total_lines += 1
    print(f"    Total tick records: {total_lines:,}. Reading in chunks of {chunksize:,}...")
    
    chunks = []
    pbar = tqdm(total=total_lines, desc="    Reading ticks", unit=" lines")
    
    chunk_iter = pd.read_csv(filepath, sep=';', header=None,
                             names=['Timestamp', 'Price1', 'Price2', 'Price3', 'Volume'],
                             chunksize=chunksize, dtype={0: str, 1: float, 2: float, 3: float, 4: int})
    
    for chunk in chunk_iter:
        # Parse timestamp
        parts = chunk['Timestamp'].astype(str).str.split(n=2, expand=True)
        dt_str = parts[0] + ' ' + parts[1]
        chunk['DateTime'] = pd.to_datetime(dt_str, format='%Y%m%d %H%M%S', errors='coerce')
        chunk = chunk.dropna(subset=['DateTime'])
        chunk['Price'] = chunk['Price1']  # use first price
        chunk = chunk[['DateTime', 'Price', 'Volume']]
        chunks.append(chunk)
        pbar.update(len(chunk))
    pbar.close()
    
    if chunks:
        result = pd.concat(chunks, ignore_index=True)
        result.set_index('DateTime', inplace=True)
        return result
    else:
        return pd.DataFrame()

def combine_all(raw_dir: str, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    all_files = [f for f in os.listdir(raw_dir) if f.endswith('.txt')]

    is_files = [f for f in all_files if 'OOS' not in f]
    oos_files = [f for f in all_files if 'OOS' in f]

    def instrument_name(fname: str) -> str:
        return fname.split()[0]

    # Group IS by instrument
    instr_is = {}
    for f in is_files:
        inst = instrument_name(f)
        instr_is.setdefault(inst, []).append(f)

    # Group OOS by instrument
    instr_oos = {}
    for f in oos_files:
        inst = instrument_name(f)
        instr_oos.setdefault(inst, []).append(f)

    print("=== In‑Sample (IS) files (always 1‑min) ===")
    for inst, files in instr_is.items():
        print(f"{inst}: {files}")
    print("\n=== Out‑of‑Sample (OOS) files (mixed 1‑min or ticks) ===")
    for inst, files in instr_oos.items():
        print(f"{inst}: {files}")

    # Process IS -> always 1-min
    for inst, files in tqdm(instr_is.items(), desc="IS instruments"):
        print(f"\nProcessing {inst} IS ...")
        dfs = []
        for f in files:
            path = os.path.join(raw_dir, f)
            if not os.path.exists(path):
                print(f"  Warning: {f} not found")
                continue
            cols = detect_columns(path)
            print(f"  {f}: {cols} columns detected")
            if cols != 6:
                print(f"    Warning: IS file {f} has {cols} columns (expected 6). Skipping.")
                continue
            try:
                dfs.append(read_1min_file(path))
            except Exception as e:
                print(f"    ERROR: {e}")
        if dfs:
            combined = pd.concat(dfs).sort_index()
            combined = combined[~combined.index.duplicated(keep='first')]
            out_file = os.path.join(out_dir, f"{inst}_IS_1min.csv")
            combined.to_csv(out_file, index=True, index_label='DateTime', date_format='%Y-%m-%d %H:%M:%S')
            print(f"  Saved {out_file} – {len(combined):,} rows")
        else:
            print(f"  No valid IS data for {inst}")

    # Process OOS -> keep original granularity
    for inst, files in tqdm(instr_oos.items(), desc="OOS instruments"):
        print(f"\nProcessing {inst} OOS ...")
        # Separate files by type
        files_1min = []
        files_ticks = []
        for f in files:
            path = os.path.join(raw_dir, f)
            if not os.path.exists(path):
                print(f"  Warning: {f} not found")
                continue
            cols = detect_columns(path)
            print(f"  {f}: {cols} columns detected")
            if cols == 6:
                files_1min.append(f)
            elif cols == 5:
                files_ticks.append(f)
            else:
                print(f"    Unknown column count, skipping {f}")

        # Process 1-min OOS files
        if files_1min:
            print(f"  Processing 1‑min files for {inst} OOS ...")
            dfs = []
            for f in files_1min:
                path = os.path.join(raw_dir, f)
                try:
                    dfs.append(read_1min_file(path))
                except Exception as e:
                    print(f"    ERROR on {f}: {e}")
            if dfs:
                combined = pd.concat(dfs).sort_index()
                combined = combined[~combined.index.duplicated(keep='first')]
                out_file = os.path.join(out_dir, f"{inst}_OOS_1min.csv")
                combined.to_csv(out_file, index=True, index_label='DateTime', date_format='%Y-%m-%d %H:%M:%S')
                print(f"  Saved {out_file} – {len(combined):,} rows")

        # Process tick OOS files (keep as ticks, concatenate with chunking)
        if files_ticks:
            print(f"  Processing tick files for {inst} OOS ...")
            dfs = []
            for f in files_ticks:
                path = os.path.join(raw_dir, f)
                try:
                    print(f"    Reading {f} with chunked progress...")
                    df_ticks = read_ticks_file_chunked(path)
                    dfs.append(df_ticks)
                except Exception as e:
                    print(f"    ERROR on {f}: {e}")
            if dfs:
                combined = pd.concat(dfs).sort_index()
                combined = combined[~combined.index.duplicated(keep='first')]
                out_file = os.path.join(out_dir, f"{inst}_OOS_ticks.csv")
                combined.to_csv(out_file, index=True, index_label='DateTime', date_format='%Y-%m-%d %H:%M:%S')
                print(f"  Saved {out_file} – {len(combined):,} tick rows")

    print("\n✅ Done. Merged files saved in:", out_dir)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw_dir", required=True)
    parser.add_argument("--out_dir", required=True)
    args = parser.parse_args()
    combine_all(args.raw_dir, args.out_dir)