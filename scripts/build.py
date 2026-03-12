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
    hist_options = "".join(
        f'<option value="{f}"{" selected" if f == "pct_fsm_ever" else ""}>'
        f"{FIELD_LABELS[f]}</option>\n"
        for f in DEMOGRAPHIC_FIELDS + ATTAINMENT_FIELDS
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Primary School Performance and Demographics Dashboard 2024-25</title>
    <link rel="stylesheet" href="style.css">
    <script defer data-domain="inglesp.github.io" src="https://plausible.io/js/script.js"></script>
</head>
<body>
    <h1>Primary School Performance and Demographics 2024-25 <button id="help-btn" class="help-btn" aria-label="Help">?</button></h1>

    <p class="subtitle">Data from the DfE's <a href="https://www.compare-school-performance.service.gov.uk/" target="_blank" rel="noopener">compare school performance</a> service for 2024-25. Covers state-funded primary schools in England with KS2 results.</p>

    <div id="help-modal" class="modal-overlay">
        <div class="modal">
            <div class="modal-header">
                <h2>Field descriptions</h2>
                <button id="help-close" class="modal-close" aria-label="Close">&times;</button>
            </div>
            <div class="modal-body">
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
                    <dt>Number on roll</dt>
                    <dd>Total number of pupils at the school (from school census).</dd>
                    <dt>Eligible pupils (KS2)</dt>
                    <dd>Number of pupils included in KS2 performance measures (typically Year 6).</dd>
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
                    <dd>Percentage reaching expected standard in RWM, split by disadvantage status. The gap between these shows within-school inequality.</dd>
                </dl>

                <h3>Percentiles</h3>
                <p>Percentiles show where a school sits relative to all others. p0 = lowest, p100 = highest.
                Both national and LA percentiles are shown. For all fields, a higher percentile means a
                higher value (e.g. p90 for % FSM means higher deprivation than 90% of schools).</p>
            </div>
        </div>
    </div>

    <div class="top-layout">
        <div class="sidebar">
            <div class="controls">
                <div class="view-toggle">
                    <button type="button" id="view-hist" class="view-btn active">Histogram</button>
                    <button type="button" id="view-scatter" class="view-btn">Scatter</button>
                </div>
                <div id="scatter-controls" class="axis-controls" style="display:none">
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
                <div id="hist-controls" class="axis-controls">
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
        var FIELD_LABELS = {json.dumps(FIELD_LABELS)};
        var DEMOGRAPHIC_FIELDS = {json.dumps(DEMOGRAPHIC_FIELDS)};
        var FILTER_OPTIONS = {json.dumps(filter_options)};
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
