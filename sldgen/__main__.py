"""Command line tools. Run `sldgen --help` or see docs/TOOLS.md.

Exit codes: 0 ok / passed, 1 design check failed, 2 project file incomplete or bad
arguments, 3 environment problem (e.g. no browser for PDF export).
"""

import argparse
import datetime
import json
import platform
import sys
from pathlib import Path

from . import __version__
from .calc import design
from .export import find_browser, to_pdf, to_png, write_html
from .project import LIBRARY_DIR, ROOT, ProjectError, load_library, load_project, prepare_project
from .render import render
from .report import design_report

TEMPLATE = ROOT / "templates" / "project.json"
SCHEMA = ROOT / "schema" / "project.schema.json"


def emit(args, payload, text_lines):
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    else:
        print("\n".join(text_lines))


def summary(d):
    ac = d["ac"]
    return {
        "phase": d["phase"], "supply": d["supply_label"],
        "p_dc_kwp": round(d["array"]["p_dc_kwp"], 3), "p_ac_kw": ac["p_ac_kw"],
        "dc_ac_ratio": round(d["array"]["dc_ac_ratio"], 3),
        "strings": [{"mppt": g["mppt"], "series": g["n_series"], "parallel": g["n_parallel"],
                     "voc_max_v": round(g["voc_max"], 1), "isc_a": round(g["isc_total"], 2)} for g in d["mppts"]],
        "dc_cable_mm2": d["dc_cable"]["size_mm2"], "vd_dc_pct": round(d["dc_cable"]["vd_pct"], 3),
        "dc_isolator": f"{d['dc_isolator']['poles']}P {d['dc_isolator']['voltage_v']} V DC {d['dc_isolator']['current_a']} A",
        "dc_spd_ucpv_v": d["dc_spd"]["ucpv_v"],
        "string_fuse_a": max((g["fuse_a"] or 0) for g in d["mppts"]) or None,
        "i_ac_a": round(ac["i_ac"], 2), "ac_mcb": f"{ac['mcb']['a']} A {ac['mcb']['poles']} C {ac['mcb']['ka']} kA",
        "ac_rcd": f"{ac['rcd']['a']} A {ac['rcd']['poles']}P {ac['rcd']['ma']} mA {ac['rcd']['type']}",
        "ac_isolator": f"{ac['isolator']['a']} A {ac['isolator']['poles']}P",
        "ac_cable": ac["cable"]["spec"], "vd_ac_pct": round(ac["cable"]["vd_pct"], 3),
        "vd_total_pct": round(d["vd_total_pct"], 3), "unverified_equipment": d["unverified"],
    }


def text_summary(d):
    s = summary(d)
    lines = [f"Array {s['p_dc_kwp']:.2f} kWp / inverter {s['p_ac_kw']:.2f} kWac / {s['supply']} "
             f"(DC/AC {s['dc_ac_ratio']:.2f})",
             "Strings: " + ", ".join(f"MPPT{g['mppt']} {g['parallel']}x{g['series']}" for g in s["strings"]),
             f"DC: cable {s['dc_cable_mm2']:g} mm² (dV {s['vd_dc_pct']:.2f}%), isolator {s['dc_isolator']}, "
             f"SPD Ucpv {s['dc_spd_ucpv_v']} V" + (f", string fuses {s['string_fuse_a']} A" if s["string_fuse_a"] else ""),
             f"AC: Iac {s['i_ac_a']:.2f} A -> MCB {s['ac_mcb']}, RCD {s['ac_rcd']}, isolator {s['ac_isolator']}",
             f"    cable {s['ac_cable']} (dV {s['vd_ac_pct']:.2f}%)",
             f"Total voltage drop {s['vd_total_pct']:.2f}%"]
    lines += [f"  {i['level'].upper():8} [{i['code']}] {i['msg']}" for i in d["issues"]]
    return lines


def load_or_report(args):
    try:
        return load_project(args.project)
    except ProjectError as e:
        emit(args, {"result": "incomplete", "problems": e.problems},
             ["PROJECT FILE INCOMPLETE:", *[f"  - {m}" for m in e.problems]])
    except (OSError, json.JSONDecodeError) as e:
        emit(args, {"result": "incomplete", "problems": [str(e)]}, [f"Cannot read project file: {e}"])
    return None


def run_check(p):
    """Calculate and check a prepared project. Returns (exit code, JSON payload, design)."""
    d = design(p)
    errors = d["issues"].errors
    payload = {"result": "failed" if errors else "passed", "summary": summary(d), "issues": list(d["issues"])}
    return (1 if errors else 0), payload, d


def run_build(p, name, out=None, force=False, png=True):
    """Check, then write SVG / report / PDF / PNG. Returns (exit code, JSON payload, design)."""
    d = design(p)
    errors = d["issues"].errors
    base = {"summary": summary(d), "issues": list(d["issues"])}
    if errors and not force:
        return 1, {"result": "failed", **base, "files": {}}, d
    rev = p["project"].get("revision", "")
    out = Path(out) if out else ROOT / "output" / name
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{name}_Rev{rev}" if rev else name
    files = {"svg": out / f"{stem}.svg", "report": out / f"{stem}_design-report.md"}
    svg = render(d, p)
    files["svg"].write_text(svg, encoding="utf-8")
    files["report"].write_text(design_report(d, p), encoding="utf-8")
    html = write_html(svg, out / f"{stem}.html")
    try:
        files["pdf"] = to_pdf(html, out / f"{stem}.pdf")
        if png:
            files["png"] = to_png(html, out / f"{stem}_preview.png")
    except Exception as e:  # browser missing or failed
        return 3, {"result": "error", "error": f"PDF export failed: {e}",
                   "files": {k: str(v) for k, v in files.items()}}, d
    return (1 if errors else 0), {"result": "failed_forced" if errors else "passed", **base,
                                  "files": {k: str(v) for k, v in files.items()}}, d


def cmd_check(args):
    p = load_or_report(args)
    if p is None:
        return 2
    code, payload, d = run_check(p)
    errors = d["issues"].errors
    warnings = [i for i in d["issues"] if i["level"] == "warning"]
    emit(args, payload,
         text_summary(d) + [f"RESULT: {'FAILED (%d error(s))' % len(errors) if errors else 'PASSED'}"
                            f"{' with %d warning(s)' % len(warnings) if warnings and not errors else ''}"])
    return code


def cmd_build(args):
    p = load_or_report(args)
    if p is None:
        return 2
    name = p["project"].get("drawing_no") or Path(args.project).stem
    code, payload, d = run_build(p, name, args.out, args.force, not args.no_png)
    if payload["result"] == "failed":
        text = text_summary(d) + ["RESULT: FAILED - not building. Fix the errors, or pass --force for a "
                                  "watermarked draft."]
    elif payload["result"] == "error":
        text = [payload["error"], "Run `sldgen doctor`."]
    else:
        text = text_summary(d) + [f"RESULT: {'FORCED DRAFT (design check failed)' if code else 'PASSED'}",
                                  *[f"{k.upper():7} {v}" for k, v in payload["files"].items()]]
    emit(args, payload, text)
    return code


def cmd_init(args):
    path = Path(args.project)
    if path.exists() and not args.overwrite:
        emit(args, {"result": "error", "error": f"{path} exists (use --overwrite)"}, [f"{path} exists (use --overwrite)"])
        return 2
    p = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    p["project"]["drawing_no"] = args.drawing_no or path.stem
    p["project"]["date"] = datetime.date.today().isoformat()
    p["supply"]["phase"] = args.phase
    if args.module:
        p["pv_module"] = args.module
    if args.inverter:
        p["inverter"] = args.inverter
    if args.strings:
        p["array"]["strings"] = [{"mppt": i + 1, "modules": int(n)} for i, n in enumerate(args.strings.split(","))]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(p, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        prepare_project(p)
        problems = []
    except ProjectError as e:
        problems = e.problems
    emit(args, {"result": "created", "path": str(path), "problems": problems},
         [f"Created {path}"] + ([f"  still to fill: {m}" for m in problems] or ["  ready: run `sldgen check`"]))
    return 0


def cmd_library(args):
    kinds = [args.kind] if args.kind else ["pv_module", "inverter"]
    data = {k: load_library(k) for k in kinds}
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0
    for k in kinds:
        print(f"{'MODULES' if k == 'pv_module' else 'INVERTERS'}  ({LIBRARY_DIR / ('modules.json' if k == 'pv_module' else 'inverters.json')})")
        for key, e in sorted(data[k].items()):
            if k == "pv_module":
                spec = f"{e.get('wattage_wp')} Wp  Voc {e.get('voc')} V  Isc {e.get('isc')} A"
            else:
                spec = (f"{e.get('phase')}-ph {e.get('rated_ac_kw')} kW  {e.get('mppt_count')} MPPT x "
                        f"{e.get('max_strings_per_mppt', '?')}  Vdc max {e.get('max_dc_voltage_v')} V")
            flag = "verified" if e.get("verified") else "UNVERIFIED"
            print(f"  {key:28} {e.get('brand', '')} {e.get('model', '')}\n  {'':28} {spec}  [{flag}]")
        print()
    return 0


def cmd_schema(args):
    print(SCHEMA.read_text(encoding="utf-8"))
    return 0


def cmd_doctor(args):
    checks = []

    def add(name, ok, detail):
        checks.append({"check": name, "ok": ok, "detail": detail})

    add("python", sys.version_info >= (3, 10), platform.python_version())
    try:
        add("browser", True, find_browser())
    except RuntimeError as e:
        add("browser", False, str(e))
    for kind in ("pv_module", "inverter"):
        lib = load_library(kind)
        unverified = [k for k, v in lib.items() if not v.get("verified")]
        add(f"library.{kind}", bool(lib), f"{len(lib)} entries, {len(unverified)} unverified"
            + (f" ({', '.join(unverified)})" if unverified else ""))
    for ex in sorted((ROOT / "examples").glob("*.json")):
        try:
            d = design(load_project(ex))
            add(f"example.{ex.stem}", not d["issues"].errors, "passes check" if not d["issues"].errors else
                "; ".join(i["msg"] for i in d["issues"].errors))
        except ProjectError as e:
            add(f"example.{ex.stem}", False, "; ".join(e.problems))
    ok = all(c["ok"] for c in checks)
    emit(args, {"result": "ok" if ok else "problems", "version": __version__, "checks": checks},
         [f"sldgen {__version__}"] + [f"  [{'OK' if c['ok'] else '!!'}] {c['check']:28} {c['detail']}" for c in checks]
         + ["All good." if ok else "Fix the items marked !!"])
    return 0 if ok else 3


def cmd_mcp(args):
    from .mcp_server import serve
    return serve()


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="sldgen", description="Malaysian Solar ATAP residential SLD generator")
    ap.add_argument("--version", action="version", version=f"sldgen {__version__}")
    sub = ap.add_subparsers(dest="command", required=True)

    def common(sp):
        sp.add_argument("--json", action="store_true", help="machine-readable JSON output")
        return sp

    sp = common(sub.add_parser("check", help="run calculations and compliance checks"))
    sp.add_argument("project")
    sp.set_defaults(func=cmd_check)

    sp = common(sub.add_parser("build", help="check, then write PDF / PNG / SVG / design report"))
    sp.add_argument("project")
    sp.add_argument("--out", help="output folder (default output/<drawing_no>)")
    sp.add_argument("--force", action="store_true", help="build a watermarked draft even if checks fail")
    sp.add_argument("--no-png", action="store_true", help="skip the PNG preview")
    sp.set_defaults(func=cmd_build)

    sp = common(sub.add_parser("init", help="create a project file from the template"))
    sp.add_argument("project", help="path of the new project file, e.g. projects/ATAP-SLD-RES-003.json")
    sp.add_argument("--phase", type=int, choices=[1, 3], default=3)
    sp.add_argument("--module", help="library key of the PV module")
    sp.add_argument("--inverter", help="library key of the inverter")
    sp.add_argument("--strings", help="modules per string, one string per MPPT in order, e.g. 9,8")
    sp.add_argument("--drawing-no", help="drawing number (default: file name)")
    sp.add_argument("--overwrite", action="store_true")
    sp.set_defaults(func=cmd_init)

    sp = common(sub.add_parser("library", help="list equipment in the datasheet library"))
    sp.add_argument("kind", nargs="?", choices=["pv_module", "inverter"])
    sp.set_defaults(func=cmd_library)

    sp = sub.add_parser("schema", help="print the project file JSON Schema")
    sp.set_defaults(func=cmd_schema, json=False)

    sp = common(sub.add_parser("doctor", help="check Python, browser, library and examples"))
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("mcp", help="run the MCP server on stdio (for Claude Desktop and other chat hosts)")
    sp.set_defaults(func=cmd_mcp, json=False)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
