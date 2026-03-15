"""Generate an HTML report summarising the GIAS data.

Reads the GIAS CSV files and produces reports/gias.html with an overview
of what's available and how it relates to the school performance data.
"""

import csv
from collections import Counter
from pathlib import Path

GIAS_DIR = Path("data/gias/20260312")
OUT = Path("reports/gias.html")


def read_csv(filepath):
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            with open(filepath, encoding=encoding) as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Cannot decode {filepath}")


def h(text):
    """HTML-escape."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def table(headers, rows, max_rows=50):
    html = "<table><thead><tr>"
    for hdr in headers:
        html += f"<th>{h(hdr)}</th>"
    html += "</tr></thead><tbody>"
    for i, row in enumerate(rows):
        if i >= max_rows:
            html += f'<tr><td colspan="{len(headers)}"><em>... {len(rows) - max_rows} more rows</em></td></tr>'
            break
        html += "<tr>"
        for cell in row:
            html += f"<td>{h(cell)}</td>"
        html += "</tr>"
    html += "</tbody></table>"
    return html


def counter_table(counter, col1="Value", col2="Count", max_rows=30):
    rows = [(k, v) for k, v in counter.most_common()]
    return table([col1, col2], rows[:max_rows] + (
        [("...", f"{len(rows) - max_rows} more")] if len(rows) > max_rows else []
    ))


def section(title, content):
    return f"<h2>{h(title)}</h2>\n{content}\n"


def main():
    html_parts = []

    # --- File inventory ---
    files_info = []
    for p in sorted(GIAS_DIR.glob("*.csv")):
        rows = read_csv(p)
        cols = list(rows[0].keys()) if rows else []
        files_info.append((p.name, len(rows), len(cols), ", ".join(cols[:8]) + ("..." if len(cols) > 8 else "")))

    html_parts.append(section("Files", f"""
        <p>{len(files_info)} CSV files in <code>{GIAS_DIR}</code></p>
        {table(["File", "Rows", "Columns", "First columns"], files_info, max_rows=100)}
    """))

    # --- Establishment data (edubasealldata) ---
    estab = read_csv(GIAS_DIR / "edubasealldata20260312.csv")
    html_parts.append(section("Establishment data (edubasealldata)", f"<p>{len(estab)} rows</p>"))

    # Status breakdown
    status_counts = Counter(r.get("EstablishmentStatus (name)", "") for r in estab)
    html_parts.append(section("Establishment status", counter_table(status_counts, "Status", "Count")))

    # Type group breakdown
    type_group_counts = Counter(r.get("EstablishmentTypeGroup (name)", "") for r in estab)
    html_parts.append(section("Establishment type groups", counter_table(type_group_counts, "Type group", "Count")))

    # Phase breakdown (open only)
    open_estab = [r for r in estab if r.get("EstablishmentStatus (name)") == "Open"]
    phase_counts = Counter(r.get("PhaseOfEducation (name)", "") for r in open_estab)
    html_parts.append(section("Phase of education (open establishments)", counter_table(phase_counts, "Phase", "Count")))

    # Type breakdown (open only)
    type_counts = Counter(r.get("TypeOfEstablishment (name)", "") for r in open_estab)
    html_parts.append(section("Type of establishment (open)", counter_table(type_counts, "Type", "Count")))

    # Trust fields
    trust_flag_counts = Counter(r.get("TrustSchoolFlag (name)", "") for r in open_estab)
    html_parts.append(section("Trust school flag (open)", counter_table(trust_flag_counts, "Flag", "Count")))

    has_trust = [r for r in open_estab if r.get("Trusts (name)")]
    no_trust = [r for r in open_estab if not r.get("Trusts (name)")]
    html_parts.append(section("Trust membership (open)", f"""
        <p>With trust name: {len(has_trust)}</p>
        <p>Without trust name: {len(no_trust)}</p>
    """))

    # Top trusts by school count
    trust_counter = Counter(r["Trusts (name)"] for r in has_trust)
    html_parts.append(section("Largest trusts (by school count)", counter_table(trust_counter, "Trust", "Schools")))

    # --- Groups data ---
    groups = read_csv(GIAS_DIR / "groups.csv")
    group_type_counts = Counter(r.get("Group Type", "") for r in groups)
    group_status_counts = Counter(r.get("Group Status", "") for r in groups)
    html_parts.append(section("Groups data (groups.csv)", f"""
        <p>{len(groups)} groups</p>
        <h3>Group types</h3>
        {counter_table(group_type_counts, "Type", "Count")}
        <h3>Group status</h3>
        {counter_table(group_status_counts, "Status", "Count")}
    """))

    # --- Group links (academy trust membership) ---
    group_links = read_csv(GIAS_DIR / "grouplinks_edubaseallacademiesandfree20260312.csv")
    gl_type_counts = Counter(r.get("Group Type", "") for r in group_links)
    html_parts.append(section("Group links (academy trust → school)", f"""
        <p>{len(group_links)} links</p>
        <h3>By group type</h3>
        {counter_table(gl_type_counts, "Type", "Count")}
    """))

    # --- Assemble HTML ---
    body = "\n".join(html_parts)
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>GIAS Data Report</title>
<style>
body {{ font-family: -apple-system, sans-serif; max-width: 960px; margin: 2rem auto; padding: 0 1rem; color: #333; }}
h1 {{ border-bottom: 2px solid #333; padding-bottom: 0.5rem; }}
h2 {{ margin-top: 2rem; color: #2166ac; }}
h3 {{ margin-top: 1rem; color: #555; }}
table {{ border-collapse: collapse; margin: 0.5rem 0 1rem; }}
th, td {{ border: 1px solid #ddd; padding: 0.3rem 0.6rem; text-align: left; font-size: 0.85rem; }}
th {{ background: #f5f5f5; }}
tr:nth-child(even) td {{ background: #fafafa; }}
code {{ background: #eee; padding: 0.1rem 0.3rem; border-radius: 2px; }}
</style>
</head>
<body>
<h1>GIAS Data Report</h1>
<p>Data from <code>{GIAS_DIR}</code></p>
{body}
</body>
</html>
"""

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html)
    print(f"Report written to {OUT} ({len(html) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
