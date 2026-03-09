"""Build static site from CSV data.

Reads the DfE CSV files, merges them, and writes:
  - _site/data.json  (school data)
  - _site/index.html
  - _site/dashboard.js
  - _site/style.css
"""

import csv
import json
import shutil
from pathlib import Path

DATA_DIR = Path("data/2024-25")
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


def load_school_info():
    filepath = DATA_DIR / "england_school_information.csv"
    schools = {}
    with open(filepath, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["ISPRIMARY"] != "1":
                continue
            if row["MINORGROUP"] not in ("Maintained school", "Academy"):
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


def load_census():
    filepath = DATA_DIR / "england_census.csv"
    census = {}
    with open(filepath, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["SCHOOLTYPE"] != "State-funded primary":
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


def build_data():
    print("Loading CSVs...")
    school_info = load_school_info()
    census = load_census()
    ks2 = load_ks2()

    print(f"  School info: {len(school_info)}")
    print(f"  Census: {len(census)}")
    print(f"  KS2: {len(ks2)}")

    schools = []
    for urn, info in school_info.items():
        if urn not in ks2:
            continue
        school = {"urn": int(urn)}
        school.update(info)
        school.update(census.get(urn, {}))
        school.update(ks2[urn])
        schools.append(school)

    print(f"  Merged: {len(schools)}")
    return schools


def build_filter_options(schools):
    la_names = sorted(set(s["la_name"] for s in schools))
    school_types = sorted(set(s["school_type"] for s in schools))
    religious_characters = sorted(set(
        s["religious_character"] for s in schools if s["religious_character"]
    ))
    return {
        "la_names": la_names,
        "school_types": school_types,
        "religious_characters": religious_characters,
    }


FIELD_LABELS = {
    "pct_fsm_ever": "% FSM ever",
    "pct_eal": "% EAL",
    "pct_sen": "% SEN (total)",
    "pct_sen_support": "% SEN support",
    "pct_sen_ehcp": "% SEN EHCP",
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

DEMOGRAPHIC_FIELDS = [
    "pct_fsm_ever",
    "pct_eal",
    "pct_sen",
    "pct_sen_support",
    "pct_sen_ehcp",
    "number_on_roll",
    "eligible_pupils",
]

ATTAINMENT_FIELDS = [
    "pct_rwm_expected",
    "pct_rwm_higher",
    "pct_reading_expected",
    "pct_reading_higher",
    "pct_writing_expected",
    "pct_writing_higher",
    "pct_maths_expected",
    "pct_maths_higher",
    "pct_gps_expected",
    "pct_gps_higher",
    "reading_average",
    "maths_average",
    "gps_average",
]


def build_html(filter_options):
    x_options = "".join(
        f'<option value="{f}"{" selected" if f == "pct_fsm_ever" else ""}>'
        f"{FIELD_LABELS[f]}</option>\n"
        for f in DEMOGRAPHIC_FIELDS
    )
    y_options = "".join(
        f'<option value="{f}"{" selected" if f == "pct_rwm_expected" else ""}>'
        f"{FIELD_LABELS[f]}</option>\n"
        for f in ATTAINMENT_FIELDS
    )
    la_options = "".join(
        f'<option value="{la}">{la}</option>\n'
        for la in filter_options["la_names"]
    )
    type_options = "".join(
        f'<option value="{t}">{t}</option>\n'
        for t in filter_options["school_types"]
    )
    religion_options = "".join(
        f'<option value="{r}">{r}</option>\n'
        for r in filter_options["religious_characters"]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Primary School Performance Dashboard 2024-25</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <h1>Primary School Performance 2024-25</h1>

    <div class="controls">
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
        <div class="control-group">
            <label for="filter-la">Local authority:</label>
            <select id="filter-la">
                <option value="">All</option>
                {la_options}
            </select>
        </div>
        <div class="control-group">
            <label for="filter-type">School type:</label>
            <select id="filter-type">
                <option value="">All</option>
                {type_options}
            </select>
        </div>
        <div class="control-group">
            <label for="filter-religion">Religious character:</label>
            <select id="filter-religion">
                <option value="">All</option>
                {religion_options}
            </select>
        </div>
    </div>

    <div class="school-search">
        <label for="search-input">Highlight schools:</label>
        <div class="search-wrapper">
            <input type="text" id="search-input" placeholder="Search by school name..." autocomplete="off">
            <ul id="search-results" class="search-results"></ul>
        </div>
        <div id="selected-schools" class="selected-schools"></div>
    </div>

    <div class="chart-container">
        <canvas id="scatterplot"></canvas>
        <div id="tooltip" class="tooltip"></div>
    </div>

    <div id="stats" class="stats"></div>

    <div id="selected-table-container" class="selected-table-container"></div>

    <script>
        var FIELD_LABELS = {json.dumps(FIELD_LABELS)};
        var DATA_URL = "data.json";
    </script>
    <script src="dashboard.js"></script>
</body>
</html>
"""


def main():
    SITE_DIR.mkdir(exist_ok=True)

    schools = build_data()
    filter_options = build_filter_options(schools)

    data_path = SITE_DIR / "data.json"
    print(f"Writing {data_path} ...")
    with open(data_path, "w") as f:
        json.dump(schools, f, indent=2)
    print(f"  {data_path.stat().st_size / 1024 / 1024:.1f} MB")

    html_path = SITE_DIR / "index.html"
    print(f"Writing {html_path} ...")
    with open(html_path, "w") as f:
        f.write(build_html(filter_options))

    # Copy static assets
    shutil.copy(STATIC_DIR / "dashboard.js", SITE_DIR / "dashboard.js")
    shutil.copy(STATIC_DIR / "style.css", SITE_DIR / "style.css")
    print("Copied dashboard.js and style.css")

    print("Done! Serve with: python -m http.server -d _site")


if __name__ == "__main__":
    main()
