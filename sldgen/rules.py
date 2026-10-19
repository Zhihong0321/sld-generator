"""Design rules, limits and standard equipment sizes.

Every engineering constant the engine uses lives here so it can be reviewed
and adjusted in one place. Section references (§) point to the project
specification `docs/specification.md`.
"""

# --- Supply -------------------------------------------------------------------
V_PHASE = 230.0          # V, single-phase nominal (Un)
V_LINE = 400.0           # V, three-phase line-to-line
FREQUENCY_HZ = 50

# --- Solar ATAP capacity caps (§4, PV Array row) ---------------------------------
# Checked against the inverter AC rating (hard error) and the array DC rating
# (warning). Confirm the current SEDA/TNB quota rules before submission.
CAP_KW = {1: 5.0, 3: 15.0}
DC_AC_RATIO_MAX = 1.35   # warning above this
DC_AC_RATIO_MIN = 0.80   # warning below this

# --- Site temperatures for string voltage checks (§3.1) --------------------------
T_MIN_CELL_C = 15.0      # lowest cell temperature (early morning, lowlands)
T_MAX_CELL_C = 70.0      # hottest cell temperature (midday, roof-mounted)
DEFAULT_TEMP_COEFF_VOC = -0.29   # %/degC, used when the datasheet value is missing

# --- Sizing factors (§3) --------------------------------------------------------
DC_CURRENT_FACTOR = 1.25          # I_fuse / isolator >= 1.25 x Isc
AC_BREAKER_FACTOR = 1.25          # I_breaker >= 1.25 x I_ac_max
DC_SPD_VOLTAGE_FACTOR = 1.2       # Ucpv >= 1.2 x Voc_string
STRING_FUSE_MIN_PARALLEL = 3      # string fuses needed from this many parallel strings per MPPT

# --- Voltage drop (§3.1, §3.2) ---------------------------------------------------
VD_DC_MAX_PCT = 1.0
VD_AC_MAX_PCT = 1.0
VD_TOTAL_MAX_PCT = 2.0
RHO_CU = 0.0225          # ohm.mm2/m, copper at operating temperature

# --- Standard equipment ratings ----------------------------------------------------
MCB_SIZES_A = [6, 10, 16, 20, 25, 32, 40, 50, 63]
RCD_SIZES_A = [25, 40, 63, 80, 100]
AC_ISOLATOR_SIZES_A = [20, 25, 32, 40, 63, 80, 100]
DC_ISOLATOR_SIZES_A = [16, 25, 32, 40, 50, 63]
DC_ISOLATOR_VOLTAGES_V = [1000, 1200, 1500]   # practical minimum 1000 V DC
DC_FUSE_SIZES_A = [10, 12, 15, 16, 20, 25, 30, 32]
DC_SPD_UCPV_V = [500, 600, 800, 1000, 1200, 1500]
AC_SPD_UC_V = {1: 275, 3: 440}
SPD_IN_KA = 20
SPD_IMAX_KA = 40
SPD_BACKUP_MCB_A = 16
MCB_BREAKING_KA = 10
AC_RCD_SENSITIVITY_MA = {1: 30, 3: 100}
AC_RCD_TYPE = "Type A"
AC_ISOLATOR_UTILISATION = "AC-23A"
DC_ISOLATOR_UTILISATION = "DC-PV2"

# --- Cables -----------------------------------------------------------------------
DC_CABLE_SIZES_MM2 = [4, 6, 10]
# EN 50618 (PV1-F) single core, free air; derated for conduit/grouping/ambient.
DC_CABLE_AMPACITY_A = {2.5: 41, 4: 55, 6: 70, 10: 98, 16: 132}
DC_CABLE_DERATING = 0.70
AC_CABLE_SIZES_MM2 = [4, 6, 10, 16, 25]
# MS IEC 60364-5-52, PVC Cu 70 degC, installation method B (in conduit).
AC_CABLE_AMPACITY_A = {
    1: {1.5: 17.5, 2.5: 24, 4: 32, 6: 41, 10: 57, 16: 76, 25: 101},   # 2 loaded conductors
    3: {1.5: 15.5, 2.5: 21, 4: 28, 6: 36, 10: 50, 16: 68, 25: 89},    # 3 loaded conductors
}
EARTH_CONDUCTOR_MIN_MM2 = 6
MODULE_BONDING_MM2 = 6

# --- Earthing (§6) -----------------------------------------------------------------
EARTH_ROD = "16 mm DIA x 2.4 m COPPER-BONDED STEEL ROD"
EARTH_RESISTANCE_MAX_OHM = 10

# --- TNB intake defaults (§4) ------------------------------------------------------
TNB_CUTOUT_FUSE_A = {1: 60, 3: 60}
TNB_SERVICE_CABLE = {1: "16 mm² CONCENTRIC", 3: "25 mm² PVC/SWA/PVC Cu"}
MDB_MAIN_SWITCH_A = 63
MDB_MAIN_RCD_A = 63
MDB_MAIN_RCD_MA = 100

# --- TNB mandatory inverter protection settings (§5) ---------------------------------
PROTECTION_SETTINGS = [
    ("Under-Voltage (UV)", "V < 196 V (0.85 Un)", "t <= 2.0 s"),
    ("Over-Voltage 1 (OV1)", "V > 253 V (1.10 Un)", "t <= 2.0 s"),
    ("Over-Voltage 2 (OV2)", "V > 264 V (1.15 Un)", "t <= 0.1 s"),
    ("Under-Frequency (UF)", "f < 47.5 Hz", "t <= 0.5 s"),
    ("Over-Frequency (OF)", "f > 52.0 Hz", "t <= 0.5 s"),
    ("Loss of Mains (Islanding)", "Active & passive drift", "t <= 2.0 s"),
    ("Reconnection Delay", "Stable normal supply", "300 s delay"),
]

GOVERNING_STANDARDS = [
    "MS IEC 60364-7-712", "MS 1837", "MS IEC 62446", "TNB Technical Guidebook (DG)",
    "Electricity Supply Act 1990 & Electricity Regulations 1994", "IEC 60617 symbols",
]
