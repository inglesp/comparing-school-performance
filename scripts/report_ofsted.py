"""Generate an HTML report summarising the Ofsted inspection data.

Reads data/ofsted/20260228.csv and produces reports/ofsted.html.
"""

import csv
from collections import Counter
from pathlib import Path

OFSTED_CSV = Path("data/ofsted/20260228.csv")
OUT = Path("reports/ofsted.html")

GRADE_LABELS = {"1": "Outstanding", "2": "Good", "3": "Requires improvement", "4": "Inadequate", "9": "N/A"}


def h(text):
    """HTML-escape."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def html_table(headers, rows, max_rows=50):
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
    return html_table([col1, col2], rows[:max_rows] + (
        [("...", f"{len(rows) - max_rows} more")] if len(rows) > max_rows else []
    ))


def section(title, content):
    return f"<h2>{h(title)}</h2>\n{content}\n"


def subsection(title, content):
    return f"<h3>{h(title)}</h3>\n{content}\n"


def read_ofsted_csv():
    """Read the Ofsted CSV, skipping the 2 preamble rows."""
    with open(OFSTED_CSV, encoding="cp1252") as f:
        # Skip 2 preamble rows
        next(f)
        next(f)
        reader = csv.DictReader(f)
        rows = list(reader)
        headers = list(reader.fieldnames)
    return rows, headers


def grade_counter(rows, col):
    """Count grades, labelling them."""
    raw = Counter(r.get(col, "") or "" for r in rows)
    labelled = Counter()
    for k, v in raw.items():
        k = k.strip()
        if k == "" or k == "NULL":
            labelled["(empty/NULL)"] += v
        elif k in GRADE_LABELS:
            labelled[f"{k} – {GRADE_LABELS[k]}"] += v
        else:
            labelled[k] += v
    return labelled


def main():
    rows, headers = read_ofsted_csv()
    parts = []

    parts.append(f"<p><strong>{len(rows)}</strong> rows, <strong>{len(headers)}</strong> columns</p>")

    # Column listing
    col_rows = []
    for col in headers:
        vals = [r.get(col, "") or "" for r in rows]
        non_empty = [v for v in vals if v.strip() and v.strip() != "NULL"]
        if not non_empty:
            col_rows.append((col, f"{len(vals)} rows, all empty/NULL"))
            continue

        # Try numeric
        numeric = []
        for v in non_empty:
            try:
                numeric.append(float(v))
            except ValueError:
                pass

        empty_count = len(vals) - len(non_empty)
        if len(numeric) > len(non_empty) * 0.8:
            summary = (
                f"{len(non_empty)} values ({empty_count} empty) · "
                f"range: {min(numeric):.1f} – {max(numeric):.1f} · "
                f"mean: {sum(numeric)/len(numeric):.1f}"
            )
        else:
            counter = Counter(non_empty)
            top = counter.most_common(5)
            top_str = ", ".join(f"{v} ({c})" for v, c in top)
            extra = f" + {len(counter) - 5} more" if len(counter) > 5 else ""
            summary = f"{len(non_empty)} values ({empty_count} empty) · top: {top_str}{extra}"

        col_rows.append((col, summary))

    parts.append(section("All columns", html_table(["Column", "Summary"], col_rows, max_rows=200)))

    # Phase breakdown
    phase_counts = Counter(r.get("Ofsted phase", "") for r in rows)
    parts.append(section("Schools by Ofsted phase", counter_table(phase_counts, "Phase", "Count")))

    # Type breakdown
    type_counts = Counter(r.get("Type of education", "") for r in rows)
    parts.append(section("Schools by type of education", counter_table(type_counts, "Type", "Count")))

    # OEIF graded inspection judgements
    oeif_cols = [
        "Latest OEIF overall effectiveness",
        "Latest OEIF quality of education",
        "Latest OEIF behaviour and attitudes",
        "Latest OEIF personal development",
        "Latest OEIF effectiveness of leadership and management",
        "Latest OEIF early years provision (where applicable)",
        "Latest OEIF sixth form provision (where applicable)",
    ]

    oeif_parts = []
    for col in oeif_cols:
        if col in headers:
            gc = grade_counter(rows, col)
            oeif_parts.append(subsection(col, counter_table(gc, "Grade", "Count")))
    parts.append(section("OEIF graded inspection judgements (all schools)", "\n".join(oeif_parts)))

    # OEIF by phase
    for phase in ["Primary", "Secondary", "Nursery", "All-through", "Special", "Alternative provision"]:
        phase_rows = [r for r in rows if r.get("Ofsted phase") == phase]
        if not phase_rows:
            continue
        gc = grade_counter(phase_rows, "Latest OEIF overall effectiveness")
        # Calculate percentages for graded schools
        graded = {k: v for k, v in gc.items() if not k.startswith("(empty")}
        total_graded = sum(graded.values())
        pct_rows = []
        for k, v in sorted(graded.items()):
            pct_rows.append((k, v, f"{v/total_graded*100:.1f}%"))
        pct_rows.append(("Total graded", total_graded, ""))
        pct_rows.append(("No graded inspection", gc.get("(empty/NULL)", 0), ""))
        parts.append(section(
            f"OEIF overall effectiveness – {phase} ({len(phase_rows)} schools)",
            html_table(["Grade", "Count", "%"], pct_rows, max_rows=20)
        ))

    # New framework judgements
    new_cols = [
        "Safeguarding standards",
        "Inclusion",
        "Curriculum and teaching",
        "Achievement",
        "Attendance and behaviour",
        "Personal development and wellbeing",
        "Early years (where applicable)",
        "Post-16 provision (where applicable)",
        "Leadership and governance",
    ]

    new_parts = []
    for col in new_cols:
        if col in headers:
            gc = grade_counter(rows, col)
            new_parts.append(subsection(col, counter_table(gc, "Grade", "Count")))
    if new_parts:
        parts.append(section("New framework judgements (all schools)", "\n".join(new_parts)))

    # Category of concern
    concern_counts = Counter(r.get("Most recent category of concern", "") or "" for r in rows)
    parts.append(section("Most recent category of concern",
                         counter_table(concern_counts, "Category", "Count")))

    # Ungraded inspection outcomes
    if "Ungraded inspection overall outcome" in headers:
        ug_counts = Counter(r.get("Ungraded inspection overall outcome", "") or "" for r in rows)
        parts.append(section("Ungraded inspection outcomes",
                             counter_table(ug_counts, "Outcome", "Count")))

    # OEIF safeguarding
    if "Latest OEIF  safeguarding is effective?" in headers:
        sg_counts = Counter(r.get("Latest OEIF  safeguarding is effective?", "") or "" for r in rows)
        parts.append(section("OEIF safeguarding is effective?",
                             counter_table(sg_counts, "Value", "Count")))

    # URN coverage
    urns = {r["URN"] for r in rows if r.get("URN")}
    parts.append(section("URN coverage", f"<p><strong>{len(urns)}</strong> unique URNs</p>"))

    # Sample rows
    sample = rows[:10]
    sample_cols = ["URN", "School name", "Ofsted phase", "Type of education", "Local authority",
                   "Latest OEIF overall effectiveness", "Inspection start date of latest OEIF graded inspection"]
    sample_rows = []
    for r in sample:
        sample_rows.append(tuple(r.get(c, "") for c in sample_cols))
    parts.append(section("Sample rows (first 10)", html_table(sample_cols, sample_rows, max_rows=10)))

    # Assemble
    body = "\n".join(parts)
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Ofsted Data Report</title>
<style>
body {{ font-family: -apple-system, sans-serif; max-width: 1200px; margin: 2rem auto; padding: 0 1rem; color: #333; }}
h1 {{ border-bottom: 2px solid #333; padding-bottom: 0.5rem; }}
h2 {{ margin-top: 2rem; color: #2166ac; border-bottom: 1px solid #ddd; padding-bottom: 0.3rem; }}
h3 {{ margin-top: 1rem; color: #555; }}
table {{ border-collapse: collapse; margin: 0.5rem 0 1rem; }}
th, td {{ border: 1px solid #ddd; padding: 0.3rem 0.6rem; text-align: left; font-size: 0.85rem; }}
th {{ background: #f5f5f5; position: sticky; top: 0; }}
tr:nth-child(even) td {{ background: #fafafa; }}
code {{ background: #eee; padding: 0.1rem 0.3rem; border-radius: 2px; }}
</style>
</head>
<body>
<h1>Ofsted Data Report</h1>
<p>Data from <code>{OFSTED_CSV}</code></p>
{body}
</body>
</html>
"""

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html)
    print(f"Report written to {OUT} ({len(html) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
