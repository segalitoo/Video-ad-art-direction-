"""Shared loaders for the lock, modes, platform specs and tool adapters."""

from pathlib import Path
import re
import sys

import yaml

ROOT = Path(__file__).resolve().parent.parent
MODES_DIR = ROOT / "lock" / "modes"
SPECS_FILE = ROOT / "platforms" / "specs.yml"
TOOLS_FILE = ROOT / "adapters" / "tools.yml"

TOKEN_ORDER = ["STYLE", "WORLD", "FORM", "LIGHT", "GRADE", "CAMERA", "MOTION", "TECH"]
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def fail(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(2)


def load_specs():
    return load_yaml(SPECS_FILE)


def load_tools():
    return load_yaml(TOOLS_FILE)["tools"]


def load_storyboard(path):
    path = Path(path)
    board = load_yaml(path)
    if "ad" not in board or "shots" not in board:
        fail(f"{path} needs an 'ad' block and a 'shots' list")
    lock_path = (path.parent / board["ad"]["lock"]).resolve()
    if not lock_path.exists():
        fail(f"lock file not found: {lock_path}")
    return board, load_lock(lock_path)


def load_lock(path):
    """Load a lock and merge it over its mode preset. The lock always wins."""
    lock = load_yaml(path)
    mode_name = lock.get("meta", {}).get("mode")
    mode_file = MODES_DIR / f"{mode_name}.yml"
    if not mode_file.exists():
        options = ", ".join(p.stem for p in sorted(MODES_DIR.glob("*.yml")))
        fail(f"unknown mode '{mode_name}'. Options: {options}")
    mode = load_yaml(mode_file)

    tokens = dict(mode.get("tokens", {}))
    for key, value in (lock.get("tokens") or {}).items():
        if value:
            tokens[key] = value
    lock["tokens"] = tokens
    lock["negative"] = list(mode.get("negative", [])) + list(lock.get("negative") or [])
    lock["_mode"] = mode
    lock["_path"] = Path(path)
    return lock


def parse_aspect(aspect):
    w, h = aspect.split(":")
    return int(w), int(h)


def safe_union(specs, platform_ids):
    """The strictest margin on each side across all target platforms."""
    sides = ["top", "bottom", "left", "right"]
    union = {s: 0.0 for s in sides}
    for pid in platform_ids:
        zone = specs["platforms"][pid]["safe_zone_pct"]
        for s in sides:
            union[s] = max(union[s], float(zone[s]))
    return union
