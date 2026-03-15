"""Generate an HTML report summarising the CSP (Compare School Performance) data.

Reads the CSV files from data/csp/2024-2025 and produces reports/csp.html
with an overview of what's available across all key stages.
"""

import csv
from collections import Counter
from pathlib import Path

CSP_DIR = Path("data/csp/2024-2025")
OUT = Path("reports/csp.html")


def read_csv(filepath, max_rows=None):
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            with open(filepath, encoding=encoding) as f:
                reader = csv.DictReader(f)
                if max_rows:
                    return list(row for _, row in zip(range(max_rows), reader)), list(reader.fieldnames)
                rows = list(reader)
                return rows, list(reader.fieldnames)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Cannot decode {filepath}")


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


SUPPRESSED = {"SUPP", "NE", "NA", "NP", "NEW", "LOW", "DNS", ""}


def value_summary(rows, col):
    """Summarise a column: count non-suppressed, numeric range, common values."""
    vals = [r.get(col, "") or "" for r in rows]
    total = len(vals)
    suppressed = sum(1 for v in vals if v.strip().upper() in SUPPRESSED or v.strip() == "")
    non_supp = [v.strip() for v in vals if v.strip().upper() not in SUPPRESSED and v.strip() != ""]

    if not non_supp:
        return f"{total} rows, all suppressed/empty"

    # Try to detect numeric
    numeric = []
    for v in non_supp:
        v_clean = v.replace("%", "").strip()
        try:
            numeric.append(float(v_clean))
        except ValueError:
            pass

    if len(numeric) > len(non_supp) * 0.8:
        return (
            f"{len(non_supp)} values ({suppressed} suppressed) · "
            f"range: {min(numeric):.1f} – {max(numeric):.1f} · "
            f"mean: {sum(numeric)/len(numeric):.1f}"
        )
    else:
        counter = Counter(non_supp)
        top = counter.most_common(5)
        top_str = ", ".join(f"{v} ({c})" for v, c in top)
        extra = f" + {len(counter) - 5} more" if len(counter) > 5 else ""
        return f"{len(non_supp)} values ({suppressed} suppressed) · top: {top_str}{extra}"


def analyse_csv(filepath):
    """Analyse a CSV file and return HTML sections."""
    rows, headers = read_csv(filepath)
    parts = []

    name = filepath.name
    parts.append(f"<p><strong>{len(rows)}</strong> rows, <strong>{len(headers)}</strong> columns</p>")

    # Column listing with value summaries
    col_rows = []
    for col in headers:
        summary = value_summary(rows, col)
        col_rows.append((col, summary))

    parts.append(html_table(["Column", "Summary"], col_rows, max_rows=200))

    # Key breakdowns depending on file type
    if "RECTYPE" in headers:
        rectype_counts = Counter(r.get("RECTYPE", "") for r in rows)
        parts.append(subsection("Record types (RECTYPE)", counter_table(rectype_counts, "RECTYPE", "Count")))

    if "NFTYPE" in headers:
        nftype_counts = Counter(r.get("NFTYPE", "") for r in rows)
        parts.append(subsection("School types (NFTYPE)", counter_table(nftype_counts, "NFTYPE", "Count")))

    if "SCHOOLTYPE" in headers:
        st_counts = Counter(r.get("SCHOOLTYPE", "") for r in rows)
        parts.append(subsection("School types (SCHOOLTYPE)", counter_table(st_counts, "SCHOOLTYPE", "Count")))

    return section(name, "\n".join(parts))


def main():
    html_parts = []

    # File inventory
    all_files = sorted(CSP_DIR.iterdir())
    csv_files = [f for f in all_files if f.suffix == ".csv"]
    xlsx_files = [f for f in all_files if f.suffix == ".xlsx"]

    file_rows = []
    for f in all_files:
        size_kb = f.stat().st_size / 1024
        if size_kb > 1024:
            size_str = f"{size_kb/1024:.1f} MB"
        else:
            size_str = f"{size_kb:.0f} KB"

        if f.suffix == ".csv":
            rows, headers = read_csv(f)
            file_rows.append((f.name, f.suffix, size_str, len(rows), len(headers)))
        elif f.suffix == ".xlsx":
            file_rows.append((f.name, f.suffix, size_str, "—", "—"))

    html_parts.append(section("File inventory", f"""
        <p>{len(csv_files)} CSV files, {len(xlsx_files)} Excel files in <code>{CSP_DIR}</code></p>
        {html_table(["File", "Type", "Size", "Rows", "Columns"], file_rows, max_rows=50)}
    """))

    # Cross-file URN overlap
    urn_sets = {}
    for f in csv_files:
        rows, headers = read_csv(f)
        if "URN" in headers:
            urns = {r["URN"] for r in rows if r.get("URN")}
            urn_sets[f.name] = urns

    if urn_sets:
        overlap_rows = []
        names = sorted(urn_sets.keys())
        for i, n1 in enumerate(names):
            for n2 in names[i+1:]:
                shared = len(urn_sets[n1] & urn_sets[n2])
                only_1 = len(urn_sets[n1] - urn_sets[n2])
                only_2 = len(urn_sets[n2] - urn_sets[n1])
                overlap_rows.append((n1, n2, len(urn_sets[n1]), len(urn_sets[n2]), shared, only_1, only_2))

        html_parts.append(section("URN overlap between files",
            html_table(["File 1", "File 2", "URNs in 1", "URNs in 2", "Shared", "Only in 1", "Only in 2"],
                       overlap_rows, max_rows=100)))

    # Detailed analysis of each CSV
    for f in csv_files:
        html_parts.append(analyse_csv(f))

    # Assemble
    body = "\n".join(html_parts)
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>CSP Data Report — 2024-25</title>
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
<h1>CSP Data Report — 2024-25</h1>
<p>Data from <code>{CSP_DIR}</code></p>
{body}
</body>
</html>
"""

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html)
    print(f"Report written to {OUT} ({len(html) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
