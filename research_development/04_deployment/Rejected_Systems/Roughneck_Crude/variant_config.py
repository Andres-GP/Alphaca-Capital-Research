"""Minimal variant_config (fallback). If your Monday_Effect folder already has its own variant_config.py, copy THAT one
next to roughneck_engine.py instead: the notebooks only use EDGE_DIR, load_variant(name) and save_json(cfg, filename, obj)."""
import json
from pathlib import Path
import yaml

EDGE_DIR = Path(__file__).resolve().parent     # the notebooks overwrite this with find_upwards('variants')


def load_variant(name):
    """Reads variants/<name>.yaml; run_dir becomes an absolute path under EDGE_DIR."""
    p = Path(EDGE_DIR) / "variants" / (name if name.endswith(".yaml") else f"{name}.yaml")
    cfg = yaml.safe_load(p.read_text())
    cfg["run_dir"] = str(Path(EDGE_DIR) / cfg["run_dir"])
    return cfg


def save_json(cfg, filename, obj):
    out = Path(cfg["run_dir"])
    out.mkdir(parents=True, exist_ok=True)
    path = out / filename
    path.write_text(json.dumps(obj, indent=2, default=str))
    print(f"Saved: {path}")
    return path