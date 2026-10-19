"""Plain-text design report written next to the drawing."""

from .render import check_rows, schedule_rows


def design_report(d, p):
    pr = p["project"]
    out = [f"# Design report - {pr.get('drawing_no', '')} Rev {pr.get('revision', '')}",
           "", f"- Account holder: {pr.get('account_holder', '')}",
           f"- Address: {pr.get('address', '')}", f"- Supply: {d['supply_label']}",
           f"- Array: {d['array']['p_dc_kwp']:.2f} kWp ({d['array']['n_modules']} modules), "
           f"inverter {d['ac']['p_ac_kw']:.2f} kWac, DC/AC {d['array']['dc_ac_ratio']:.2f}", ""]
    errors = [i for i in d["issues"] if i["level"] == "error"]
    out.append(f"## Status: {'FAILED - ' + str(len(errors)) + ' error(s)' if errors else 'PASSED'}")
    out.append("")
    for level in ("error", "warning", "info"):
        items = [i for i in d["issues"] if i["level"] == level]
        if items:
            out.append(f"### {level.upper()}S")
            out += [f"- [{i['code']}] {i['msg']}" for i in items]
            out.append("")
    out += ["## Checks", "", "| Check | Result | Limit | |", "|---|---|---|---|"]
    out += [f"| {a} | {b} | {c} | {'OK' if ok else 'FAIL'} |" for a, b, c, ok in check_rows(d)]
    out += ["", "## MPPT / string data", "", "| MPPT | Strings | Series x Parallel | Voc STC | Voc max | "
            "Vmp STC | Vmp min | Isc | Fuse |", "|---|---|---|---|---|---|---|---|---|"]
    for g in d["mppts"]:
        out.append(f"| {g['mppt']} | {', '.join(g['strings'])} | {g['n_series']} x {g['n_parallel']} | "
                   f"{g['voc_stc']:.1f} V | {g['voc_max']:.1f} V | {g['vmp_stc']:.1f} V | {g['vmp_min']:.1f} V | "
                   f"{g['isc_total']:.2f} A | {g['fuse_a'] or '-'} |")
    out += ["", "## Equipment schedule", "", "| Tag | Item | Specification | Sizing basis |", "|---|---|---|---|"]
    out += [f"| {t} | {n} | {s} | {b} |" for t, n, s, b in schedule_rows(d, p)]
    return "\n".join(out) + "\n"
