"""Engineering calculations and compliance checks (spec §3, §4, §6)."""

import math
from collections import OrderedDict

from . import rules as R


def next_size(value, sizes):
    for s in sizes:
        if s >= value - 1e-9:
            return s
    return None


class Issues(list):
    def add(self, level, code, msg):
        self.append({"level": level, "code": code, "msg": msg})

    def error(self, code, msg):
        self.add("error", code, msg)

    def warn(self, code, msg):
        self.add("warning", code, msg)

    def info(self, code, msg):
        self.add("info", code, msg)

    @property
    def errors(self):
        return [i for i in self if i["level"] == "error"]


def _override(p, key, computed, issues, label, minimum=None):
    """Use an override when given, warning if it is below the computed minimum."""
    value = p["overrides"].get(key)
    if value is None:
        return computed
    if minimum is not None and value < minimum:
        issues.error(f"override.{key}", f"{label} override {value} is below the required minimum {minimum:g}")
    else:
        issues.info(f"override.{key}", f"{label} set by override to {value} (calculated {computed})")
    return value


def design(p):
    issues = Issues()
    phase = p["supply"]["phase"]
    mod, inv = p["pv_module"], p["inverter"]
    t_min = p["site"].get("t_min_cell_c", R.T_MIN_CELL_C)
    t_max = p["site"].get("t_max_cell_c", R.T_MAX_CELL_C)
    beta = mod.get("temp_coeff_voc_pct", R.DEFAULT_TEMP_COEFF_VOC)
    if "temp_coeff_voc_pct" not in mod:
        issues.warn("module.temp_coeff", f"Module Voc temperature coefficient missing, assumed {beta} %/degC")
    gamma = mod.get("temp_coeff_pmax_pct", beta)
    voc_k_cold = 1 + beta / 100 * (t_min - 25)
    vmp_k_cold = 1 + gamma / 100 * (t_min - 25)
    vmp_k_hot = 1 + gamma / 100 * (t_max - 25)

    if inv["phase"] != phase:
        issues.error("inverter.phase", f"Inverter is {inv['phase']}-phase but supply is {phase}-phase")

    # --- Strings and MPPTs (§3.1) ---------------------------------------------------
    strings = p["strings"]
    groups = OrderedDict()
    for s in sorted(strings, key=lambda s: s["mppt"]):
        groups.setdefault(s["mppt"], []).append(s)
    mppts = []
    for m, ss in groups.items():
        if not 1 <= m <= inv["mppt_count"]:
            issues.error("mppt.index", f"String(s) {', '.join(s['id'] for s in ss)} assigned to MPPT {m}, "
                         f"but the inverter has {inv['mppt_count']} MPPT(s)")
        lengths = {s["modules"] for s in ss}
        if len(lengths) > 1:
            issues.error("mppt.mismatch", f"MPPT {m} has parallel strings of different lengths {sorted(lengths)}")
        n_s = max(lengths)
        n_p = len(ss)
        max_inputs = inv.get("max_strings_per_mppt")
        if max_inputs and n_p > max_inputs:
            issues.error("mppt.inputs", f"MPPT {m} has {n_p} strings but only {max_inputs} input(s) per MPPT")
        g = {
            "mppt": m, "strings": [s["id"] for s in ss], "n_series": n_s, "n_parallel": n_p,
            "power_wp": n_s * n_p * mod["wattage_wp"],
            "voc_stc": n_s * mod["voc"], "voc_max": n_s * mod["voc"] * voc_k_cold,
            "vmp_stc": n_s * mod["vmp"], "vmp_min": n_s * mod["vmp"] * vmp_k_hot,
            "vmp_cold": n_s * mod["vmp"] * vmp_k_cold,
            "isc_total": n_p * mod["isc"], "imp_total": n_p * mod["imp"],
        }
        if g["voc_max"] >= inv["max_dc_voltage_v"]:
            issues.error("dc.voc_max", f"MPPT {m}: Voc at {t_min:g} degC = {g['voc_max']:.0f} V exceeds inverter "
                         f"max DC input {inv['max_dc_voltage_v']} V - reduce modules per string")
        if g["vmp_min"] < inv["mppt_voltage_min_v"]:
            issues.warn("dc.vmp_min", f"MPPT {m}: Vmp at {t_max:g} degC = {g['vmp_min']:.0f} V is below the MPPT "
                        f"minimum {inv['mppt_voltage_min_v']} V - yield loss on hot days")
        if g["vmp_cold"] > inv["mppt_voltage_max_v"]:
            issues.warn("dc.vmp_max", f"MPPT {m}: Vmp at {t_min:g} degC = {g['vmp_cold']:.0f} V is above the MPPT "
                        f"maximum {inv['mppt_voltage_max_v']} V")
        if g["isc_total"] > inv["max_isc_per_mppt_a"]:
            issues.error("dc.isc", f"MPPT {m}: Isc {g['isc_total']:.2f} A exceeds inverter max short-circuit "
                         f"current {inv['max_isc_per_mppt_a']} A per MPPT")
        max_in = inv.get("max_input_current_per_mppt_a")
        if max_in and g["imp_total"] > max_in:
            issues.warn("dc.imp", f"MPPT {m}: Imp {g['imp_total']:.2f} A exceeds inverter max input current "
                        f"{max_in} A - inverter will current-limit (clipping)")

        # String fuses (§3.1): only where enough strings are paralleled to back-feed a faulty string.
        if n_p >= R.STRING_FUSE_MIN_PARALLEL:
            need = R.DC_CURRENT_FACTOR * mod["isc"]
            rating = next_size(need, R.DC_FUSE_SIZES_A)
            g["fuse_a"] = rating
            limit = mod.get("max_series_fuse_a")
            if limit and rating and rating > limit:
                issues.error("dc.fuse", f"MPPT {m}: string fuse {rating} A exceeds module max series fuse {limit} A")
        else:
            g["fuse_a"] = None
        mppts.append(g)

    n_modules = sum(s["modules"] for s in strings)
    p_dc_kwp = n_modules * mod["wattage_wp"] / 1000
    p_ac_kw = inv["rated_ac_kw"]
    ratio = p_dc_kwp / p_ac_kw if p_ac_kw else 0
    cap = R.CAP_KW[phase]
    if p_ac_kw > cap:
        issues.error("cap.ac", f"Inverter {p_ac_kw:g} kW exceeds the Solar ATAP {phase}-phase cap of {cap:g} kW")
    if p_dc_kwp > cap:
        issues.warn("cap.dc", f"Array {p_dc_kwp:.2f} kWp exceeds {cap:g} kWp - confirm the current SEDA "
                    f"quota rule (kWp vs kWac basis) before submission")
    if ratio > R.DC_AC_RATIO_MAX:
        issues.warn("ratio.high", f"DC/AC ratio {ratio:.2f} is above {R.DC_AC_RATIO_MAX}")
    elif ratio < R.DC_AC_RATIO_MIN:
        issues.warn("ratio.low", f"DC/AC ratio {ratio:.2f} is below {R.DC_AC_RATIO_MIN}")
    if len(groups) < inv["mppt_count"]:
        issues.info("mppt.unused", f"{inv['mppt_count'] - len(groups)} MPPT input(s) unused")

    # --- DC cable (§3.1) -------------------------------------------------------------
    dc_len = p["cables"]["dc_length_m"]
    worst = min(mppts, key=lambda g: g["vmp_stc"])
    need_iz = R.DC_CURRENT_FACTOR * mod["isc"]

    def dc_vd(a):
        return 2 * dc_len * mod["imp"] * R.RHO_CU / a / worst["vmp_stc"] * 100

    forced = p["cables"].get("dc_size_mm2")
    dc_size = forced or next((a for a in R.DC_CABLE_SIZES_MM2
                              if R.DC_CABLE_AMPACITY_A[a] * R.DC_CABLE_DERATING >= need_iz
                              and dc_vd(a) <= R.VD_DC_MAX_PCT), None)
    if dc_size is None:
        dc_size = R.DC_CABLE_SIZES_MM2[-1]
        issues.error("dc.cable", f"No DC cable up to {dc_size} mm2 meets {R.VD_DC_MAX_PCT}% drop over {dc_len} m")
    dc_iz = R.DC_CABLE_AMPACITY_A.get(dc_size, 0) * R.DC_CABLE_DERATING
    vd_dc = dc_vd(dc_size)
    if vd_dc > R.VD_DC_MAX_PCT:
        issues.error("dc.vd", f"DC voltage drop {vd_dc:.2f}% exceeds {R.VD_DC_MAX_PCT}%")
    if dc_iz < need_iz:
        issues.error("dc.iz", f"DC cable {dc_size} mm2 derated capacity {dc_iz:.0f} A < {need_iz:.1f} A")
    dc_cable = {"size_mm2": dc_size, "length_m": dc_len, "iz_a": dc_iz, "vd_pct": vd_dc,
                "spec": f"1C x {dc_size:g} mm² PV1-F XLPO Cu 1.5 kV DC (EN 50618)"}

    # --- DC isolator & SPD ----------------------------------------------------------------
    voc_max = max(g["voc_max"] for g in mppts)
    voc_stc = max(g["voc_stc"] for g in mppts)
    isc_mppt = max(g["isc_total"] for g in mppts)
    iso_a = next_size(R.DC_CURRENT_FACTOR * isc_mppt, R.DC_ISOLATOR_SIZES_A)
    iso_v = next_size(voc_max, R.DC_ISOLATOR_VOLTAGES_V)
    if iso_a is None or iso_v is None:
        issues.error("dc.isolator", "No standard DC isolator rating covers this array")
    dc_isolator = {"current_a": iso_a, "voltage_v": iso_v, "poles": 2 * len(mppts),
                   "utilisation": R.DC_ISOLATOR_UTILISATION}
    ucpv = next_size(max(R.DC_SPD_VOLTAGE_FACTOR * voc_stc, voc_max), R.DC_SPD_UCPV_V)
    if ucpv is None:
        issues.error("dc.spd", "No standard DC SPD Ucpv covers this array voltage")
    dc_spd = {"ucpv_v": ucpv, "in_ka": R.SPD_IN_KA, "imax_ka": R.SPD_IMAX_KA}

    # --- AC side (§3.2) ----------------------------------------------------------------
    p_ac_w = p_ac_kw * 1000
    i_calc = p_ac_w / R.V_PHASE if phase == 1 else p_ac_w / (math.sqrt(3) * R.V_LINE)
    i_ac = max(inv.get("max_ac_current_a") or 0, i_calc)
    mcb_min = R.AC_BREAKER_FACTOR * i_ac
    mcb = _override(p, "ac_mcb_a", next_size(mcb_min, R.MCB_SIZES_A), issues, "Solar AC MCB", mcb_min)
    rcd = _override(p, "ac_rcd_a", next_size(mcb, R.RCD_SIZES_A), issues, "Solar AC RCD", mcb)
    rcd_ma = p["overrides"].get("ac_rcd_ma", R.AC_RCD_SENSITIVITY_MA[phase])
    rcd_type = inv.get("rcd_type", R.AC_RCD_TYPE)
    iso_ac = _override(p, "ac_isolator_a", next_size(max(mcb_min, mcb), R.AC_ISOLATOR_SIZES_A),
                       issues, "AC isolator", mcb)
    ac_len = p["cables"]["ac_length_m"]

    def ac_vd(a):
        if phase == 1:
            return 2 * ac_len * i_ac * R.RHO_CU / a / R.V_PHASE * 100
        return math.sqrt(3) * ac_len * i_ac * R.RHO_CU / a / R.V_LINE * 100

    amp = R.AC_CABLE_AMPACITY_A[phase]
    forced = p["cables"].get("ac_size_mm2")
    ac_size = forced or next((a for a in R.AC_CABLE_SIZES_MM2 if amp[a] >= mcb and ac_vd(a) <= R.VD_AC_MAX_PCT), None)
    if ac_size is None:
        ac_size = R.AC_CABLE_SIZES_MM2[-1]
        issues.error("ac.cable", f"No AC cable up to {ac_size} mm2 meets {R.VD_AC_MAX_PCT}% drop over {ac_len} m")
    vd_ac = ac_vd(ac_size)
    if vd_ac > R.VD_AC_MAX_PCT:
        issues.error("ac.vd", f"AC voltage drop {vd_ac:.2f}% exceeds {R.VD_AC_MAX_PCT}%")
    if amp.get(ac_size, 0) < mcb:
        issues.error("ac.iz", f"AC cable {ac_size} mm2 capacity {amp.get(ac_size, 0)} A < MCB {mcb} A")
    pe = max(R.EARTH_CONDUCTOR_MIN_MM2, min(ac_size, 16))
    cores = "3C" if phase == 1 else "5C"
    conductors = "L+N+E" if phase == 1 else "L1+L2+L3+N+E"
    ac_cable = {"size_mm2": ac_size, "pe_mm2": pe, "length_m": ac_len, "iz_a": amp.get(ac_size), "vd_pct": vd_ac,
                "spec": f"{cores} {ac_size:g} mm² PVC/PVC Cu ({conductors})" if pe == ac_size else
                        f"{'2C' if phase == 1 else '4C'} {ac_size:g} mm² PVC/PVC Cu + 1C {pe:g} mm² E"}
    vd_total = vd_dc + vd_ac
    if vd_total > R.VD_TOTAL_MAX_PCT:
        issues.error("vd.total", f"Total voltage drop {vd_total:.2f}% exceeds {R.VD_TOTAL_MAX_PCT}%")

    poles_ac = 2 if phase == 1 else 4
    ac = {
        "p_ac_kw": p_ac_kw, "i_calc": i_calc, "i_ac": i_ac, "mcb_min": mcb_min,
        "mcb": {"a": mcb, "poles": "DP" if phase == 1 else "TP", "curve": "C", "ka": R.MCB_BREAKING_KA},
        "rcd": {"a": rcd, "ma": rcd_ma, "type": rcd_type, "poles": poles_ac},
        "isolator": {"a": iso_ac, "poles": poles_ac, "utilisation": R.AC_ISOLATOR_UTILISATION},
        "spd": {"uc_v": R.AC_SPD_UC_V[phase], "in_ka": R.SPD_IN_KA, "imax_ka": R.SPD_IMAX_KA,
                "poles": poles_ac, "backup_a": R.SPD_BACKUP_MCB_A},
        "cable": ac_cable,
    }

    # --- PCC / MDB / TNB intake (§4, §7) -----------------------------------------------------
    pcc = p["pcc"]
    default_circuits = [{"name": "LIGHTING", "rating_a": 10}, {"name": "SOCKET OUTLETS", "rating_a": 20},
                        {"name": "AIR-CONDITIONER", "rating_a": 20}]
    mdb = {
        "main_switch_a": pcc.get("main_switch_a", R.MDB_MAIN_SWITCH_A),
        "main_switch_poles": "DP" if phase == 1 else "4P",
        "main_rcd_a": pcc.get("main_rcd_a", R.MDB_MAIN_RCD_A),
        "main_rcd_ma": pcc.get("main_rcd_ma", R.MDB_MAIN_RCD_MA),
        "solar_way_a": mcb, "solar_way_poles": "DP" if phase == 1 else "TP",
        "circuits": pcc.get("existing_circuits", default_circuits),
        "busbar_a": pcc.get("busbar_a", 100),
    }
    if mcb > mdb["main_switch_a"]:
        issues.error("pcc.rating", f"Solar way {mcb} A exceeds MDB main switch {mdb['main_switch_a']} A")
    tnb = {
        "cutout_a": pcc.get("tnb_cutout_fuse_a", R.TNB_CUTOUT_FUSE_A[phase]),
        "service_cable": pcc.get("tnb_service_cable", R.TNB_SERVICE_CABLE[phase]),
        "meter": "1-PHASE 2-WIRE" if phase == 1 else "3-PHASE 4-WIRE",
    }

    unverified = [f"{k.replace('_', ' ')} {e['brand']} {e['model']}"
                  for k, e in (("pv_module", mod), ("inverter", inv)) if not e.get("verified")]
    for u in unverified:
        issues.warn("data.unverified", f"{u}: datasheet values not marked verified")

    return {
        "phase": phase,
        "supply_label": "SINGLE-PHASE 230 V, 50 Hz (1P 2W)" if phase == 1 else "THREE-PHASE 400/230 V, 50 Hz (3P 4W)",
        "t_min": t_min, "t_max": t_max,
        "module": mod, "inverter": inv, "strings": strings, "mppts": mppts,
        "array": {"n_modules": n_modules, "p_dc_kwp": p_dc_kwp, "dc_ac_ratio": ratio},
        "dc_cable": dc_cable, "dc_isolator": dc_isolator, "dc_spd": dc_spd,
        "ac": ac, "vd_total_pct": vd_total, "mdb": mdb, "tnb": tnb,
        "earth": {"bond_mm2": R.MODULE_BONDING_MM2, "pe_mm2": max(pe, R.EARTH_CONDUCTOR_MIN_MM2),
                  "rod": R.EARTH_ROD, "r_max": R.EARTH_RESISTANCE_MAX_OHM},
        "issues": issues, "unverified": unverified,
    }
