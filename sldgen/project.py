"""Load a project file and resolve equipment references against the library."""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIBRARY_DIR = Path(os.environ.get("SLD_LIBRARY", ROOT / "library"))

REQUIRED = {
    "pv_module": ["brand", "model", "wattage_wp", "voc", "isc", "vmp", "imp"],
    "inverter": ["brand", "model", "phase", "rated_ac_kw", "max_dc_voltage_v", "mppt_count",
                 "mppt_voltage_min_v", "mppt_voltage_max_v", "max_isc_per_mppt_a"],
}
LIBRARY_FILE = {"pv_module": "modules", "inverter": "inverters"}


class ProjectError(Exception):
    def __init__(self, problems):
        self.problems = problems
        super().__init__("\n".join(problems))


def load_library(kind):
    path = LIBRARY_DIR / f"{LIBRARY_FILE[kind]}.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k.lower(): v for k, v in data.items() if not k.startswith("_")}


def resolve_equipment(kind, spec, problems):
    """Accept a library key, {"ref": key, ...overrides}, or a full inline dict."""
    if spec is None:
        problems.append(f"'{kind}' is missing")
        return {}
    if isinstance(spec, str):
        spec = {"ref": spec}
    spec = dict(spec)
    ref = spec.pop("ref", None)
    item = {}
    if ref:
        lib = load_library(kind)
        if ref.lower() not in lib:
            problems.append(f"{kind} '{ref}' not found in library/{LIBRARY_FILE[kind]}.json "
                            f"(known: {', '.join(sorted(lib)) or 'none'})")
            return {}
        item = dict(lib[ref.lower()])
        item["library_key"] = ref
    item.update(spec)
    missing = [f for f in REQUIRED[kind] if item.get(f) in (None, "")]
    if missing:
        problems.append(f"{kind} is missing: {', '.join(missing)}")
    return item


def expand_strings(array, problems):
    strings = []
    for entry in (array or {}).get("strings", []):
        for _ in range(int(entry.get("count", 1))):
            strings.append({"mppt": int(entry.get("mppt", 1)), "modules": int(entry["modules"])})
    if not strings:
        problems.append("array.strings is empty: give e.g. [{\"mppt\": 1, \"modules\": 10}]")
    for i, s in enumerate(strings, 1):
        s["id"] = f"S{i}"
    return strings


def load_project(path):
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    return prepare_project(raw)


def prepare_project(raw):
    problems = []
    p = dict(raw)
    p["project"] = dict(raw.get("project", {}))
    p["supply"] = dict(raw.get("supply", {}))
    phase = p["supply"].get("phase")
    if phase not in (1, 3):
        problems.append("supply.phase must be 1 or 3")
    p["pv_module"] = resolve_equipment("pv_module", raw.get("pv_module"), problems)
    p["inverter"] = resolve_equipment("inverter", raw.get("inverter"), problems)
    p["strings"] = expand_strings(raw.get("array"), problems)
    p["cables"] = dict(raw.get("cables", {}))
    for key in ("dc_length_m", "ac_length_m"):
        if not isinstance(p["cables"].get(key), (int, float)):
            problems.append(f"cables.{key} (one-way run length in metres) is missing")
    p["site"] = dict(raw.get("site", {}))
    p["pcc"] = dict(raw.get("pcc", {}))
    p["overrides"] = dict(raw.get("overrides", {}))
    p["people"] = dict(raw.get("people", {}))
    if problems:
        raise ProjectError(problems)
    return p
