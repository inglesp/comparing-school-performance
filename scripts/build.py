"""Build static site from CSV data.

Reads the DfE CSV files, merges them, and writes:
  - _site/index.html + data.json  (KS2 primary schools)
  - _site/ks4/index.html + data.json  (KS4 secondary schools)
  - _site/dashboard.js
  - _site/style.css
"""

import csv
import json
import shutil
from pathlib import Path

DATA_DIR = Path("data/csp/2024-2025")
GIAS_DIR = Path("data/gias/20260312")
OFSTED_CSV = Path("data/ofsted/20260228.csv")
SITE_DIR = Path("_site")
STATIC_DIR = Path("static")

SUPPRESSED_VALUES = {"", "SUPP", "NE", "NA", "NP", "NEW", "LOW", "DNS"}


def parse_pct(val):
    if not val or val in SUPPRESSED_VALUES:
        return None
    try:
        return float(val.strip().rstrip("%"))
    except ValueError:
        return None


def parse_int(val):
    if not val or val in SUPPRESSED_VALUES:
        return None
    try:
        return int(val.strip())
    except ValueError:
        return None


def parse_float(val):
    if not val or val in SUPPRESSED_VALUES:
        return None
    try:
        return float(val.strip())
    except ValueError:
        return None


def add_nullable(a, b):
    if a is not None and b is not None:
        return a + b
    return None


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_school_info(*, phase_key, minor_groups):
    """Load school info, filtering by phase and minor group."""
    filepath = DATA_DIR / "england_school_information.csv"
    schools = {}
    with open(filepath, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row[phase_key] != "1":
                continue
            if row["MINORGROUP"] not in minor_groups:
                continue
            if row["SCHSTATUS"] != "Open":
                continue
            schools[row["URN"]] = {
                "name": row["SCHNAME"],
                "la_name": row["LANAME"],
                "town": row["TOWN"],
                "postcode": row["POSTCODE"],
                "school_type": row["SCHOOLTYPE"],
                "minor_group": row["MINORGROUP"],
                "religious_character": row.get("RELCHAR") or "",
            }
    return schools


def load_census(*, school_type_prefix):
    """Load census data, filtering by school type prefix."""
    filepath = DATA_DIR / "england_census.csv"
    census = {}
    with open(filepath, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if not row["SCHOOLTYPE"].startswith(school_type_prefix):
                continue
            support = parse_pct(row["PSENELK"])
            ehcp = parse_pct(row["PSENELSE"])
            census[row["URN"]] = {
                "number_on_roll": parse_int(row["NOR"]),
                "pct_fsm_ever": parse_pct(row["PNUMFSMEVER"]),
                "pct_eal": parse_pct(row["PNUMEAL"]),
                "pct_sen": add_nullable(support, ehcp),
                "pct_sen_support": support,
                "pct_sen_ehcp": ehcp,
            }
    return census


def load_ks2():
    filepath = DATA_DIR / "england_ks2revised.csv"
    ks2 = {}
    with open(filepath, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["RECTYPE"] != "1":
                continue
            ks2[row["URN"]] = {
                "eligible_pupils": parse_int(row["TELIG"]),
                "pct_rwm_expected": parse_pct(row["PTRWM_EXP"]),
                "pct_rwm_higher": parse_pct(row["PTRWM_HIGH"]),
                "pct_reading_expected": parse_pct(row["PTREAD_EXP"]),
                "pct_reading_higher": parse_pct(row["PTREAD_HIGH"]),
                "pct_writing_expected": parse_pct(row["PTWRITTA_EXP"]),
                "pct_writing_higher": parse_pct(row["PTWRITTA_HIGH"]),
                "pct_maths_expected": parse_pct(row["PTMAT_EXP"]),
                "pct_maths_higher": parse_pct(row["PTMAT_HIGH"]),
                "pct_gps_expected": parse_pct(row["PTGPS_EXP"]),
                "pct_gps_higher": parse_pct(row["PTGPS_HIGH"]),
                "reading_average": parse_float(row["READ_AVERAGE"]),
                "maths_average": parse_float(row["MAT_AVERAGE"]),
                "gps_average": parse_float(row["GPS_AVERAGE"]),
                "pct_fsm6cla1a": parse_pct(row["PTFSM6CLA1A"]),
                "pct_rwm_exp_fsm": parse_pct(row["PTRWM_EXP_FSM6CLA1A"]),
                "pct_rwm_exp_not_fsm": parse_pct(row["PTRWM_EXP_NotFSM6CLA1A"]),
            }
    return ks2


def load_ks4():
    filepath = DATA_DIR / "england_ks4revised.csv"
    ks4 = {}
    with open(filepath, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["RECTYPE"] != "1":
                continue
            ks4[row["URN"]] = {
                "ks4_pupils": parse_int(row["TPUP"]),
                "att8": parse_float(row["ATT8SCR"]),
                "att8_english": parse_float(row["ATT8SCRENG"]),
                "att8_maths": parse_float(row["ATT8SCRMAT"]),
                "att8_ebacc": parse_float(row["ATT8SCREBAC"]),
                "att8_open": parse_float(row["ATT8SCROPEN"]),
                "pct_basics_94": parse_pct(row["PTL2BASICS_94"]),
                "pct_basics_95": parse_pct(row["PTL2BASICS_95"]),
                "pct_ebacc_entry": parse_pct(row["PTEBACC_E_PTQ_EE"]),
                "pct_ebacc_94": parse_pct(row["PTEBACC_94"]),
                "pct_ebacc_95": parse_pct(row["PTEBACC_95"]),
                "pct_fsm6cla1a": parse_pct(row["PTFSM6CLA1A"]),
                "att8_fsm": parse_float(row.get("ATT8SCR_FSM6CLA1A")),
                "att8_not_fsm": parse_float(row.get("ATT8SCR_NFSM6CLA1A")),
            }
    return ks4


def parse_ofsted_grade(val):
    """Parse an Ofsted grade: 1-4 are valid, everything else is null."""
    if not val or val in ("NULL", "Not judged", "9", "0"):
        return None
    try:
        g = int(val)
        return g if 1 <= g <= 4 else None
    except ValueError:
        return None


NEW_FRAMEWORK_VALID = {
    "Exceptional", "Strong standard", "Expected standard",
    "Needs attention", "Urgent improvement",
}


def parse_new_framework(val):
    """Parse a new framework judgement text value."""
    if not val or val == "NULL" or val == "Not applicable":
        return None
    return val if val in NEW_FRAMEWORK_VALID else None


def load_ofsted():
    """Load IDACI quintile and Ofsted judgements from management information."""
    ofsted = {}
    with open(OFSTED_CSV, encoding="cp1252") as f:
        next(f)  # skip title row
        next(f)  # skip filter instruction row
        for row in csv.DictReader(f):
            urn = row.get("URN", "").strip()
            if not urn:
                continue
            data = {}
            idaci = parse_int(row.get("The income deprivation affecting children index (IDACI) quintile", ""))
            if idaci is not None:
                data["idaci_quintile"] = idaci
            # OEIF graded inspection
            data["ofsted_overall"] = parse_ofsted_grade(row.get("Latest OEIF overall effectiveness", ""))
            data["ofsted_quality"] = parse_ofsted_grade(row.get("Latest OEIF quality of education", ""))
            data["ofsted_behaviour"] = parse_ofsted_grade(row.get("Latest OEIF behaviour and attitudes", ""))
            data["ofsted_personal"] = parse_ofsted_grade(row.get("Latest OEIF personal development", ""))
            data["ofsted_leadership"] = parse_ofsted_grade(row.get("Latest OEIF effectiveness of leadership and management", ""))
            data["ofsted_early_years"] = parse_ofsted_grade(row.get("Latest OEIF early years provision (where applicable)", ""))
            data["ofsted_sixth_form"] = parse_ofsted_grade(row.get("Latest OEIF sixth form provision (where applicable)", ""))
            # New framework
            nf_fields = {
                "nf_inclusion": parse_new_framework(row.get("Inclusion", "")),
                "nf_curriculum": parse_new_framework(row.get("Curriculum and teaching", "")),
                "nf_achievement": parse_new_framework(row.get("Achievement", "")),
                "nf_attendance": parse_new_framework(row.get("Attendance and behaviour", "")),
                "nf_personal": parse_new_framework(row.get("Personal development and wellbeing", "")),
                "nf_early_years": parse_new_framework(row.get("Early years (where applicable)", "")),
                "nf_leadership": parse_new_framework(row.get("Leadership and governance", "")),
            }
            has_new_framework = any(v is not None for v in nf_fields.values())
            data.update(nf_fields)
            # If inspected under the new framework, clear OEIF grades
            data["ofsted_framework"] = "New" if has_new_framework else "Old" if data.get("ofsted_overall") is not None else None
            # If inspected under the new framework, clear OEIF grades
            if has_new_framework:
                data["ofsted_overall"] = None
                data["ofsted_quality"] = None
                data["ofsted_behaviour"] = None
                data["ofsted_personal"] = None
                data["ofsted_leadership"] = None
                data["ofsted_early_years"] = None
                data["ofsted_sixth_form"] = None
            if data:
                ofsted[urn] = data
    return ofsted


def load_gias_trusts():
    filepath = GIAS_DIR / "edubasealldata20260312.csv"
    trusts = {}
    with open(filepath, encoding="cp1252") as f:
        for row in csv.DictReader(f):
            trust_name = row.get("Trusts (name)", "").strip()
            if trust_name:
                trusts[row["URN"]] = trust_name
    return trusts


# ---------------------------------------------------------------------------
# Merging
# ---------------------------------------------------------------------------

def build_data(school_info, census, results, gias_trusts, ofsted):
    schools = []
    for urn, info in school_info.items():
        if urn not in results:
            continue
        school = {"urn": int(urn)}
        school.update(info)
        school.update(census.get(urn, {}))
        school.update(results[urn])
        school["trust_name"] = gias_trusts.get(urn, "")
        school.update(ofsted.get(urn, {}))
        schools.append(school)
    trust_count = sum(1 for s in schools if s["trust_name"])
    print(f"  Merged: {len(schools)} ({trust_count} with trust)")
    return schools


def build_filter_options(schools):
    la_names = sorted(set(s["la_name"] for s in schools))
    school_types = sorted(set(s["school_type"] for s in schools))
    religious_characters = sorted(set(
        s["religious_character"] for s in schools if s["religious_character"]
    ))
    trust_names = sorted(set(
        s["trust_name"] for s in schools if s["trust_name"]
    ))
    ofsted_grades = ["1", "2", "3", "4"]
    ofsted_frameworks = ["Old", "New"]
    nf_judgements = ["1", "2", "3", "4", "5"]
    return {
        "la_names": la_names,
        "school_types": school_types,
        "religious_characters": religious_characters,
        "trust_names": trust_names,
        "ofsted_grades": ofsted_grades,
        "ofsted_frameworks": ofsted_frameworks,
        "nf_judgements": nf_judgements,
    }


# ---------------------------------------------------------------------------
# KS2 configuration
# ---------------------------------------------------------------------------

KS2_FIELD_LABELS = {
    "pct_fsm_ever": "% FSM ever",
    "pct_eal": "% EAL",
    "pct_sen": "% SEN (total)",
    "pct_sen_support": "% SEN support",
    "pct_sen_ehcp": "% SEN EHCP",
    "idaci_quintile": "IDACI quintile",
    "ofsted_overall": "Ofsted overall",
    "ofsted_quality": "Ofsted quality of education",
    "ofsted_behaviour": "Ofsted behaviour & attitudes",
    "ofsted_personal": "Ofsted personal development",
    "ofsted_leadership": "Ofsted leadership & management",
    "ofsted_early_years": "Ofsted early years",
    "nf_inclusion": "New Ofsted: inclusion",
    "nf_curriculum": "New Ofsted: curriculum & teaching",
    "nf_achievement": "New Ofsted: achievement",
    "nf_attendance": "New Ofsted: attendance & behaviour",
    "nf_personal": "New Ofsted: personal development",
    "nf_early_years": "New Ofsted: early years",
    "nf_leadership": "New Ofsted: leadership & governance",
    "number_on_roll": "Number on roll",
    "eligible_pupils": "Eligible pupils (KS2)",
    "pct_rwm_expected": "% RWM expected",
    "pct_rwm_higher": "% RWM higher",
    "pct_reading_expected": "% reading expected",
    "pct_reading_higher": "% reading higher",
    "pct_writing_expected": "% writing expected",
    "pct_writing_higher": "% writing higher",
    "pct_maths_expected": "% maths expected",
    "pct_maths_higher": "% maths higher",
    "pct_gps_expected": "% GPS expected",
    "pct_gps_higher": "% GPS higher",
    "reading_average": "Reading avg scaled score",
    "maths_average": "Maths avg scaled score",
    "gps_average": "GPS avg scaled score",
    "pct_fsm6cla1a": "% disadvantaged (KS2)",
    "pct_rwm_exp_fsm": "% RWM expected (FSM)",
    "pct_rwm_exp_not_fsm": "% RWM expected (non-FSM)",
}

KS2_DEMOGRAPHIC_FIELDS = [
    "pct_fsm_ever", "pct_eal", "pct_sen", "pct_sen_support", "pct_sen_ehcp",
    "idaci_quintile", "number_on_roll", "eligible_pupils",
]

KS2_FIELD_GROUPS = [
    ("School info", ["number_on_roll", "eligible_pupils"]),
    ("Demographics", [
        "pct_fsm_ever", "pct_eal", "pct_sen", "pct_sen_support", "pct_sen_ehcp",
        "idaci_quintile",
    ]),
    ("Ofsted", [
        "ofsted_overall", "ofsted_quality", "ofsted_behaviour",
        "ofsted_personal", "ofsted_leadership", "ofsted_early_years",
    ]),
    ("Ofsted (new framework)", [
        "nf_inclusion", "nf_curriculum", "nf_achievement",
        "nf_attendance", "nf_personal", "nf_early_years", "nf_leadership",
    ]),
    ("Attainment (expected)", [
        "pct_rwm_expected", "pct_reading_expected", "pct_writing_expected",
        "pct_maths_expected", "pct_gps_expected",
    ]),
    ("Attainment (higher)", [
        "pct_rwm_higher", "pct_reading_higher", "pct_writing_higher",
        "pct_maths_higher", "pct_gps_higher",
    ]),
    ("Scaled scores", ["reading_average", "maths_average", "gps_average"]),
    ("Disadvantage", [
        "pct_fsm6cla1a", "pct_rwm_exp_fsm", "pct_rwm_exp_not_fsm",
    ]),
]

KS2_TABLE_COLUMNS = [
    {"group": "School info", "key": "la_name", "label": "LA"},
    {"group": "School info", "key": "school_type", "label": "Type"},
    {"group": "School info", "key": "religious_character", "label": "Religion"},
    {"group": "School info", "key": "trust_name", "label": "Trust"},
    {"group": "School info", "key": "number_on_roll", "label": "NOR", "rank": True},
    {"group": "School info", "key": "eligible_pupils", "label": "KS2 pupils", "rank": True, "defaultOn": True},
    {"group": "Demographics", "key": "pct_fsm_ever", "label": "% FSM", "fmt": "pct", "rank": True, "defaultOn": True},
    {"group": "Demographics", "key": "pct_eal", "label": "% EAL", "fmt": "pct", "rank": True, "defaultOn": True},
    {"group": "Demographics", "key": "pct_sen", "label": "% SEN", "fmt": "pct", "rank": True, "defaultOn": True},
    {"group": "Demographics", "key": "pct_sen_support", "label": "% SEN sup", "fmt": "pct", "rank": True, "defaultOn": True},
    {"group": "Demographics", "key": "pct_sen_ehcp", "label": "% EHCP", "fmt": "pct", "rank": True, "defaultOn": True},
    {"group": "Demographics", "key": "idaci_quintile", "label": "IDACI", "rank": True, "defaultOn": True},
    {"group": "Ofsted", "key": "ofsted_overall", "label": "Overall", "headerLabel": "Ofsted", "rank": True, "defaultOn": True},
    {"group": "Ofsted", "key": "ofsted_quality", "label": "Quality", "rank": True},
    {"group": "Ofsted", "key": "ofsted_behaviour", "label": "Behaviour", "rank": True},
    {"group": "Ofsted", "key": "ofsted_personal", "label": "Personal", "rank": True},
    {"group": "Ofsted", "key": "ofsted_leadership", "label": "Leadership", "rank": True},
    {"group": "Ofsted", "key": "ofsted_early_years", "label": "Early yrs", "rank": True},
    {"group": "Ofsted (new)", "key": "nf_inclusion", "label": "Inclusion"},
    {"group": "Ofsted (new)", "key": "nf_curriculum", "label": "Curriculum"},
    {"group": "Ofsted (new)", "key": "nf_achievement", "label": "Achievement"},
    {"group": "Ofsted (new)", "key": "nf_attendance", "label": "Attendance"},
    {"group": "Ofsted (new)", "key": "nf_personal", "label": "Personal"},
    {"group": "Ofsted (new)", "key": "nf_early_years", "label": "Early yrs"},
    {"group": "Ofsted (new)", "key": "nf_leadership", "label": "Leadership"},
    {"group": "Attainment (expected)", "key": "pct_rwm_expected", "label": "% RWM exp", "fmt": "pct", "rank": True, "defaultOn": True},
    {"group": "Attainment (expected)", "key": "pct_reading_expected", "label": "% read exp", "fmt": "pct", "rank": True, "defaultOn": True},
    {"group": "Attainment (expected)", "key": "pct_writing_expected", "label": "% write exp", "fmt": "pct", "rank": True, "defaultOn": True},
    {"group": "Attainment (expected)", "key": "pct_maths_expected", "label": "% maths exp", "fmt": "pct", "rank": True, "defaultOn": True},
    {"group": "Attainment (expected)", "key": "pct_gps_expected", "label": "% GPS exp", "fmt": "pct", "rank": True, "defaultOn": True},
    {"group": "Attainment (higher)", "key": "pct_rwm_higher", "label": "% RWM high", "fmt": "pct", "rank": True},
    {"group": "Attainment (higher)", "key": "pct_reading_higher", "label": "% read high", "fmt": "pct", "rank": True},
    {"group": "Attainment (higher)", "key": "pct_writing_higher", "label": "% write high", "fmt": "pct", "rank": True},
    {"group": "Attainment (higher)", "key": "pct_maths_higher", "label": "% maths high", "fmt": "pct", "rank": True},
    {"group": "Attainment (higher)", "key": "pct_gps_higher", "label": "% GPS high", "fmt": "pct", "rank": True},
    {"group": "Scaled scores", "key": "reading_average", "label": "Read avg", "rank": True},
    {"group": "Scaled scores", "key": "maths_average", "label": "Maths avg", "rank": True},
    {"group": "Scaled scores", "key": "gps_average", "label": "GPS avg", "rank": True},
    {"group": "Disadvantage", "key": "pct_fsm6cla1a", "label": "% disadv", "fmt": "pct", "rank": True},
    {"group": "Disadvantage", "key": "pct_rwm_exp_fsm", "label": "% RWM (FSM)", "fmt": "pct", "rank": True},
    {"group": "Disadvantage", "key": "pct_rwm_exp_not_fsm", "label": "% RWM (non)", "fmt": "pct", "rank": True},
]

KS2_DEFAULTS = {
    "x": "pct_fsm_ever",
    "y": "pct_rwm_expected",
    "hist": "pct_fsm_ever",
}


# ---------------------------------------------------------------------------
# KS4 configuration
# ---------------------------------------------------------------------------

KS4_FIELD_LABELS = {
    "pct_fsm_ever": "% FSM ever",
    "pct_eal": "% EAL",
    "pct_sen": "% SEN (total)",
    "pct_sen_support": "% SEN support",
    "pct_sen_ehcp": "% SEN EHCP",
    "idaci_quintile": "IDACI quintile",
    "ofsted_overall": "Ofsted overall",
    "ofsted_quality": "Ofsted quality of education",
    "ofsted_behaviour": "Ofsted behaviour & attitudes",
    "ofsted_personal": "Ofsted personal development",
    "ofsted_leadership": "Ofsted leadership & management",
    "ofsted_sixth_form": "Ofsted sixth form",
    "nf_inclusion": "New Ofsted: inclusion",
    "nf_curriculum": "New Ofsted: curriculum & teaching",
    "nf_achievement": "New Ofsted: achievement",
    "nf_attendance": "New Ofsted: attendance & behaviour",
    "nf_personal": "New Ofsted: personal development",
    "nf_leadership": "New Ofsted: leadership & governance",
    "number_on_roll": "Number on roll",
    "ks4_pupils": "KS4 pupils",
    "att8": "Attainment 8",
    "att8_english": "Attainment 8 English",
    "att8_maths": "Attainment 8 Maths",
    "att8_ebacc": "Attainment 8 EBacc",
    "att8_open": "Attainment 8 Open",
    "pct_basics_94": "% Basics 9-4 (std pass)",
    "pct_basics_95": "% Basics 9-5 (strong pass)",
    "pct_ebacc_entry": "% entering EBacc",
    "pct_ebacc_94": "% EBacc 9-4",
    "pct_ebacc_95": "% EBacc 9-5",
    "pct_fsm6cla1a": "% disadvantaged (KS4)",
    "att8_fsm": "Attainment 8 (FSM)",
    "att8_not_fsm": "Attainment 8 (non-FSM)",
}

KS4_DEMOGRAPHIC_FIELDS = [
    "pct_fsm_ever", "pct_eal", "pct_sen", "pct_sen_support", "pct_sen_ehcp",
    "idaci_quintile", "number_on_roll", "ks4_pupils",
]

KS4_FIELD_GROUPS = [
    ("School info", ["number_on_roll", "ks4_pupils"]),
    ("Demographics", [
        "pct_fsm_ever", "pct_eal", "pct_sen", "pct_sen_support", "pct_sen_ehcp",
        "idaci_quintile",
    ]),
    ("Ofsted", [
        "ofsted_overall", "ofsted_quality", "ofsted_behaviour",
        "ofsted_personal", "ofsted_leadership", "ofsted_sixth_form",
    ]),
    ("Ofsted (new framework)", [
        "nf_inclusion", "nf_curriculum", "nf_achievement",
        "nf_attendance", "nf_personal", "nf_leadership",
    ]),
    ("Attainment 8", [
        "att8", "att8_english", "att8_maths", "att8_ebacc", "att8_open",
    ]),
    ("Basics", ["pct_basics_94", "pct_basics_95"]),
    ("EBacc", ["pct_ebacc_entry", "pct_ebacc_94", "pct_ebacc_95"]),
    ("Disadvantage", [
        "pct_fsm6cla1a", "att8_fsm", "att8_not_fsm",
    ]),
]

KS4_TABLE_COLUMNS = [
    {"group": "School info", "key": "la_name", "label": "LA"},
    {"group": "School info", "key": "school_type", "label": "Type"},
    {"group": "School info", "key": "religious_character", "label": "Religion"},
    {"group": "School info", "key": "trust_name", "label": "Trust"},
    {"group": "School info", "key": "number_on_roll", "label": "NOR", "rank": True},
    {"group": "School info", "key": "ks4_pupils", "label": "KS4 pupils", "rank": True, "defaultOn": True},
    {"group": "Demographics", "key": "pct_fsm_ever", "label": "% FSM", "fmt": "pct", "rank": True, "defaultOn": True},
    {"group": "Demographics", "key": "pct_eal", "label": "% EAL", "fmt": "pct", "rank": True, "defaultOn": True},
    {"group": "Demographics", "key": "pct_sen", "label": "% SEN", "fmt": "pct", "rank": True, "defaultOn": True},
    {"group": "Demographics", "key": "pct_sen_support", "label": "% SEN sup", "fmt": "pct", "rank": True, "defaultOn": True},
    {"group": "Demographics", "key": "pct_sen_ehcp", "label": "% EHCP", "fmt": "pct", "rank": True, "defaultOn": True},
    {"group": "Demographics", "key": "idaci_quintile", "label": "IDACI", "rank": True, "defaultOn": True},
    {"group": "Ofsted", "key": "ofsted_overall", "label": "Overall", "headerLabel": "Ofsted", "rank": True, "defaultOn": True},
    {"group": "Ofsted", "key": "ofsted_quality", "label": "Quality", "rank": True},
    {"group": "Ofsted", "key": "ofsted_behaviour", "label": "Behaviour", "rank": True},
    {"group": "Ofsted", "key": "ofsted_personal", "label": "Personal", "rank": True},
    {"group": "Ofsted", "key": "ofsted_leadership", "label": "Leadership", "rank": True},
    {"group": "Ofsted", "key": "ofsted_sixth_form", "label": "Sixth form", "rank": True},
    {"group": "Ofsted (new)", "key": "nf_inclusion", "label": "Inclusion"},
    {"group": "Ofsted (new)", "key": "nf_curriculum", "label": "Curriculum"},
    {"group": "Ofsted (new)", "key": "nf_achievement", "label": "Achievement"},
    {"group": "Ofsted (new)", "key": "nf_attendance", "label": "Attendance"},
    {"group": "Ofsted (new)", "key": "nf_personal", "label": "Personal"},
    {"group": "Ofsted (new)", "key": "nf_leadership", "label": "Leadership"},
    {"group": "Attainment 8", "key": "att8", "label": "Att 8", "rank": True, "defaultOn": True},
    {"group": "Attainment 8", "key": "att8_english", "label": "Att 8 Eng", "rank": True, "defaultOn": True},
    {"group": "Attainment 8", "key": "att8_maths", "label": "Att 8 Mat", "rank": True, "defaultOn": True},
    {"group": "Attainment 8", "key": "att8_ebacc", "label": "Att 8 EBac", "rank": True},
    {"group": "Attainment 8", "key": "att8_open", "label": "Att 8 Open", "rank": True},
    {"group": "Basics", "key": "pct_basics_94", "label": "% Bas 9-4", "fmt": "pct", "rank": True, "defaultOn": True},
    {"group": "Basics", "key": "pct_basics_95", "label": "% Bas 9-5", "fmt": "pct", "rank": True, "defaultOn": True},
    {"group": "EBacc", "key": "pct_ebacc_entry", "label": "% EBac ent", "fmt": "pct", "rank": True},
    {"group": "EBacc", "key": "pct_ebacc_94", "label": "% EBac 9-4", "fmt": "pct", "rank": True},
    {"group": "EBacc", "key": "pct_ebacc_95", "label": "% EBac 9-5", "fmt": "pct", "rank": True},
    {"group": "Disadvantage", "key": "pct_fsm6cla1a", "label": "% disadv", "fmt": "pct", "rank": True},
    {"group": "Disadvantage", "key": "att8_fsm", "label": "Att 8 (FSM)", "rank": True},
    {"group": "Disadvantage", "key": "att8_not_fsm", "label": "Att 8 (non)", "rank": True},
]

KS4_DEFAULTS = {
    "x": "pct_fsm_ever",
    "y": "att8",
    "hist": "pct_fsm_ever",
}


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def build_grouped_options(field_groups, field_labels, default):
    html = ""
    for group_name, fields in field_groups:
        html += f'<optgroup label="{group_name}">\n'
        for f in fields:
            selected = " selected" if f == default else ""
            html += f'<option value="{f}"{selected}>{field_labels[f]}</option>\n'
        html += "</optgroup>\n"
    return html


def build_html(*, title, subtitle, help_html, field_labels, demographic_fields,
               field_groups, defaults, filter_options, table_columns, data_url, nav_html):
    x_options = build_grouped_options(field_groups, field_labels, defaults["x"])
    y_options = build_grouped_options(field_groups, field_labels, defaults["y"])
    hist_options = build_grouped_options(field_groups, field_labels, defaults["hist"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="stylesheet" href="../style.css">
    <script defer data-domain="inglesp.github.io" src="https://plausible.io/js/script.js"></script>
</head>
<body>
    <h1>{title} <button id="help-btn" class="help-btn" aria-label="Help">?</button></h1>

    <p class="subtitle">{subtitle}</p>

    <nav class="page-nav">{nav_html}</nav>

    <div id="help-modal" class="modal-overlay">
        <div class="modal">
            <div class="modal-header">
                <h2>Field descriptions</h2>
                <button id="help-close" class="modal-close" aria-label="Close">&times;</button>
            </div>
            <div class="modal-body">
                {help_html}
            </div>
        </div>
    </div>

    <div class="top-layout">
        <div class="sidebar">
            <div class="controls">
                <div class="view-toggle">
                    <button type="button" id="view-scatter" class="view-btn active">Scatter</button>
                    <button type="button" id="view-hist" class="view-btn">Rank</button>
                </div>
                <div id="scatter-controls" class="axis-controls">
                    <div class="control-group">
                        <label for="x-axis">X axis:</label>
                        <select id="x-axis">
                            {x_options}
                        </select>
                    </div>
                    <div class="control-group">
                        <label for="y-axis">Y axis:</label>
                        <select id="y-axis">
                            {y_options}
                        </select>
                    </div>
                </div>
                <div id="hist-controls" class="axis-controls" style="display:none">
                    <div class="control-group">
                        <label for="hist-var">Variable:</label>
                        <select id="hist-var">
                            {hist_options}
                        </select>
                    </div>
                </div>
            </div>

            <div class="filters-panel">
                <div class="filters-header">
                    <label>Filters:</label>
                    <button type="button" id="add-filter" class="add-filter-btn">+ Add filter</button>
                </div>
                <div id="filter-rows"></div>
            </div>

            <div class="school-search">
                <label for="search-input">Highlight schools:</label>
                <div class="search-wrapper">
                    <input type="text" id="search-input" placeholder="Search by school name..." autocomplete="off">
                    <ul id="search-results" class="search-results"></ul>
                </div>
                <div id="selected-schools" class="selected-schools"></div>
            </div>

            <div id="stats" class="stats"></div>
        </div>

        <div class="chart-area">
            <div class="chart-container">
                <canvas id="scatterplot"></canvas>
                <div id="tooltip" class="tooltip"></div>
                <div id="chart-legend" class="chart-legend"></div>
            </div>
        </div>
    </div>

    <div id="column-selector" class="column-selector"></div>
    <div id="selected-table-container" class="selected-table-container"></div>

    <script>
        var FIELD_LABELS = {json.dumps(field_labels)};
        var DEMOGRAPHIC_FIELDS = {json.dumps(demographic_fields)};
        var FILTER_OPTIONS = {json.dumps(filter_options)};
        var TABLE_COLUMNS = {json.dumps(table_columns)};
        var DEFAULTS = {json.dumps(defaults)};
        var DATA_URL = "{data_url}";
    </script>
    <script src="../dashboard.js"></script>
</body>
</html>
"""


KS2_HELP = """\
<h3>Demographics</h3>
<dl>
    <dt>% FSM ever</dt>
    <dd>Percentage of pupils who have ever been eligible for free school meals (from school census).</dd>
    <dt>% EAL</dt>
    <dd>Percentage of pupils with English as an additional language.</dd>
    <dt>% SEN (total)</dt>
    <dd>Percentage of pupils with special educational needs (SEN support + EHCP combined).</dd>
    <dt>% SEN support</dt>
    <dd>Percentage of pupils receiving SEN support (the lower tier, without an EHCP).</dd>
    <dt>% SEN EHCP</dt>
    <dd>Percentage of pupils with an Education, Health and Care Plan (the most significant needs).</dd>
    <dt>IDACI quintile</dt>
    <dd>Income Deprivation Affecting Children Index quintile (1 = most deprived, 5 = least deprived). From Ofsted management information.</dd>
    <dt>Number on roll</dt>
    <dd>Total number of pupils at the school (from school census).</dd>
    <dt>Eligible pupils (KS2)</dt>
    <dd>Number of pupils included in KS2 performance measures (typically Year 6).</dd>
</dl>

<h3>Ofsted (old framework)</h3>
<p>Grades from the most recent inspection under the OEIF (pre-September 2025) framework.
Schools inspected under the new framework will not have these grades.</p>
<dl>
    <dt>Overall / Quality of education / Behaviour / Personal development / Leadership / Early years</dt>
    <dd>Grades 1 (Outstanding) to 4 (Inadequate).</dd>
</dl>

<h3>Ofsted (new framework)</h3>
<p>Judgements from inspections under the new framework (from September 2025).
Only a small number of schools have been inspected so far.</p>
<dl>
    <dt>Inclusion / Curriculum & teaching / Achievement / Attendance / Personal development / Early years / Leadership</dt>
    <dd>Rated as Exceptional, Strong standard, Expected standard, Needs attention, or Urgent improvement.</dd>
</dl>

<h3>Attainment</h3>
<p>KS2 tests are taken at the end of Year 6 (age 10-11). "Expected standard" includes pupils
achieving both the expected and higher standard.</p>
<dl>
    <dt>% RWM expected / higher</dt>
    <dd>Percentage reaching the expected/higher standard in reading, writing, and maths combined.</dd>
    <dt>% reading expected / higher</dt>
    <dd>Percentage reaching the expected/higher standard in reading.</dd>
    <dt>% writing expected / higher</dt>
    <dd>Percentage reaching the expected/higher standard in writing (teacher assessed).</dd>
    <dt>% maths expected / higher</dt>
    <dd>Percentage reaching the expected/higher standard in maths.</dd>
    <dt>% GPS expected / higher</dt>
    <dd>Percentage reaching the expected/higher standard in grammar, punctuation, and spelling.</dd>
    <dt>Reading / Maths / GPS avg scaled score</dt>
    <dd>Average scaled score (out of 120, with 100 being the expected standard threshold).</dd>
</dl>

<h3>Disadvantage gap</h3>
<dl>
    <dt>% disadvantaged (KS2)</dt>
    <dd>Percentage of KS2 eligible pupils classified as disadvantaged (FSM in last 6 years or looked-after/previously looked-after children).</dd>
    <dt>% RWM expected (FSM) / (non-FSM)</dt>
    <dd>Percentage reaching expected standard in RWM, split by disadvantage status.</dd>
</dl>

<h3>Percentiles</h3>
<p>Percentiles show where a school sits relative to all others. p0 = lowest, p100 = highest.
Both national and LA percentiles are shown. For all fields, a higher percentile means a
higher value (e.g. p90 for % FSM means higher deprivation than 90% of schools).</p>
"""

KS4_HELP = """\
<h3>Demographics</h3>
<dl>
    <dt>% FSM ever</dt>
    <dd>Percentage of pupils who have ever been eligible for free school meals (from school census).</dd>
    <dt>% EAL</dt>
    <dd>Percentage of pupils with English as an additional language.</dd>
    <dt>% SEN (total)</dt>
    <dd>Percentage of pupils with special educational needs (SEN support + EHCP combined).</dd>
    <dt>% SEN support</dt>
    <dd>Percentage of pupils receiving SEN support (the lower tier, without an EHCP).</dd>
    <dt>% SEN EHCP</dt>
    <dd>Percentage of pupils with an Education, Health and Care Plan (the most significant needs).</dd>
    <dt>IDACI quintile</dt>
    <dd>Income Deprivation Affecting Children Index quintile (1 = most deprived, 5 = least deprived). From Ofsted management information.</dd>
    <dt>Number on roll</dt>
    <dd>Total number of pupils at the school (from school census).</dd>
    <dt>KS4 pupils</dt>
    <dd>Number of pupils at the end of Key Stage 4 included in performance measures.</dd>
</dl>

<h3>Ofsted (old framework)</h3>
<p>Grades from the most recent inspection under the OEIF (pre-September 2025) framework.
Schools inspected under the new framework will not have these grades.</p>
<dl>
    <dt>Overall / Quality of education / Behaviour / Personal development / Leadership / Sixth form</dt>
    <dd>Grades 1 (Outstanding) to 4 (Inadequate).</dd>
</dl>

<h3>Ofsted (new framework)</h3>
<p>Judgements from inspections under the new framework (from September 2025).
Only a small number of schools have been inspected so far.</p>
<dl>
    <dt>Inclusion / Curriculum & teaching / Achievement / Attendance / Personal development / Leadership</dt>
    <dd>Rated as Exceptional, Strong standard, Expected standard, Needs attention, or Urgent improvement.</dd>
</dl>

<h3>Attainment 8</h3>
<p>Attainment 8 measures achievement across 8 qualifications. The overall score is the sum of
English (double weighted), Maths (double weighted), 3 EBacc subjects, and 3 open subjects.</p>
<dl>
    <dt>Attainment 8</dt>
    <dd>Average Attainment 8 score per pupil (max ~90, typical range 30-60).</dd>
    <dt>Attainment 8 English / Maths / EBacc / Open</dt>
    <dd>Average score for each Attainment 8 element.</dd>
</dl>

<h3>Basics</h3>
<dl>
    <dt>% Basics 9-4 (standard pass)</dt>
    <dd>Percentage achieving grade 4+ in both English and Maths GCSE.</dd>
    <dt>% Basics 9-5 (strong pass)</dt>
    <dd>Percentage achieving grade 5+ in both English and Maths GCSE.</dd>
</dl>

<h3>EBacc</h3>
<dl>
    <dt>% entering EBacc</dt>
    <dd>Percentage entered for the English Baccalaureate (English, Maths, Sciences, a language, and History or Geography).</dd>
    <dt>% EBacc 9-4 / 9-5</dt>
    <dd>Percentage achieving the EBacc at grade 4+/5+ in all EBacc subjects.</dd>
</dl>

<h3>Disadvantage gap</h3>
<dl>
    <dt>% disadvantaged (KS4)</dt>
    <dd>Percentage of KS4 pupils classified as disadvantaged.</dd>
    <dt>Attainment 8 (FSM) / (non-FSM)</dt>
    <dd>Average Attainment 8 score split by disadvantage status.</dd>
</dl>

<h3>Percentiles</h3>
<p>Percentiles show where a school sits relative to all others. p0 = lowest, p100 = highest.
Both national and LA percentiles are shown.</p>
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_page(*, out_dir, schools, field_labels, demographic_fields,
               field_groups, defaults, table_columns, title, subtitle, help_html, nav_html):
    """Build one dashboard page (HTML + data.json) in out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    filter_options = build_filter_options(schools)

    data_path = out_dir / "data.json"
    print(f"Writing {data_path} ...")
    with open(data_path, "w") as f:
        json.dump(schools, f, indent=2)
    print(f"  {data_path.stat().st_size / 1024 / 1024:.1f} MB")

    html_path = out_dir / "index.html"
    print(f"Writing {html_path} ...")
    with open(html_path, "w") as f:
        f.write(build_html(
            title=title,
            subtitle=subtitle,
            help_html=help_html,
            field_labels=field_labels,
            demographic_fields=demographic_fields,
            field_groups=field_groups,
            defaults=defaults,
            filter_options=filter_options,
            table_columns=table_columns,
            data_url="data.json",
            nav_html=nav_html,
        ))


def main():
    SITE_DIR.mkdir(exist_ok=True)

    print("Loading CSVs...")
    gias_trusts = load_gias_trusts()
    ofsted = load_ofsted()

    # --- KS2 ---
    print("\n--- KS2 (Primary) ---")
    ks2_school_info = load_school_info(phase_key="ISPRIMARY", minor_groups=("Maintained school", "Academy"))
    ks2_census = load_census(school_type_prefix="State-funded primary")
    ks2 = load_ks2()
    print(f"  School info: {len(ks2_school_info)}")
    print(f"  Census: {len(ks2_census)}")
    print(f"  KS2: {len(ks2)}")
    print(f"  GIAS trusts: {len(gias_trusts)}")
    ks2_schools = build_data(ks2_school_info, ks2_census, ks2, gias_trusts, ofsted)

    nav_html = '<strong>KS2</strong> · <a href="../ks4/">KS4</a>'
    build_page(
        out_dir=SITE_DIR / "ks2",
        schools=ks2_schools,
        field_labels=KS2_FIELD_LABELS,
        demographic_fields=KS2_DEMOGRAPHIC_FIELDS,
        field_groups=KS2_FIELD_GROUPS,
        defaults=KS2_DEFAULTS,
        table_columns=KS2_TABLE_COLUMNS,
        title="Primary School Performance and Demographics 2024-25",
        subtitle='Data from the DfE\'s <a href="https://www.compare-school-performance.service.gov.uk/" target="_blank" rel="noopener">compare school performance</a> service (2024-25), <a href="https://get-information-schools.service.gov.uk/" target="_blank" rel="noopener">GIAS</a>, and <a href="https://www.gov.uk/government/statistical-data-sets/monthly-management-information-ofsteds-school-inspections-outcomes" target="_blank" rel="noopener">Ofsted</a>. Covers state-funded primary schools in England with KS2 results.',
        help_html=KS2_HELP,
        nav_html=nav_html,
    )

    # --- KS4 ---
    print("\n--- KS4 (Secondary) ---")
    ks4_school_info = load_school_info(phase_key="ISSECONDARY", minor_groups=("Maintained school", "Academy"))
    ks4_census = load_census(school_type_prefix="State-funded secondary")
    ks4 = load_ks4()
    print(f"  School info: {len(ks4_school_info)}")
    print(f"  Census: {len(ks4_census)}")
    print(f"  KS4: {len(ks4)}")
    ks4_schools = build_data(ks4_school_info, ks4_census, ks4, gias_trusts, ofsted)

    nav_html = '<a href="../ks2/">KS2</a> · <strong>KS4</strong>'
    build_page(
        out_dir=SITE_DIR / "ks4",
        schools=ks4_schools,
        field_labels=KS4_FIELD_LABELS,
        demographic_fields=KS4_DEMOGRAPHIC_FIELDS,
        field_groups=KS4_FIELD_GROUPS,
        defaults=KS4_DEFAULTS,
        table_columns=KS4_TABLE_COLUMNS,
        title="Secondary School Performance and Demographics 2024-25",
        subtitle='Data from the DfE\'s <a href="https://www.compare-school-performance.service.gov.uk/" target="_blank" rel="noopener">compare school performance</a> service (2024-25), <a href="https://get-information-schools.service.gov.uk/" target="_blank" rel="noopener">GIAS</a>, and <a href="https://www.gov.uk/government/statistical-data-sets/monthly-management-information-ofsteds-school-inspections-outcomes" target="_blank" rel="noopener">Ofsted</a>. Covers state-funded secondary schools in England with KS4 results.',
        help_html=KS4_HELP,
        nav_html=nav_html,
    )

    # --- Root redirect ---
    with open(SITE_DIR / "index.html", "w") as f:
        f.write('<!DOCTYPE html><html><head><meta http-equiv="refresh" content="0;url=ks2/"></head></html>\n')

    # Copy static assets to site root
    shutil.copy(STATIC_DIR / "dashboard.js", SITE_DIR / "dashboard.js")
    shutil.copy(STATIC_DIR / "style.css", SITE_DIR / "style.css")
    print("\nCopied dashboard.js and style.css")

    print("Done! Serve with: python -m http.server -d _site")


if __name__ == "__main__":
    main()
