"""
Builds a clean circle x operator x month panel of wireless subscribers
(Mar-2024 to Apr-2025) from TRAI's monthly 'Telecom Subscription Data'
press releases (Annexure-II), and validates every row.

Each press release prints two months side by side. Column order in Annexure-II:
Airtel | Reliance Com | Vodafone Idea | BSNL (MTNL in Delhi & Mumbai) |
[BSNL VNO - Tamil Nadu only] | Reliance Jio | Total | Net addition
"""
import re
from pathlib import Path
import pandas as pd

RAW = Path(__file__).parent / "raw"
rows, checks = [], []

def tokens(line):
    """Numbers in a row; fixes merged tokens like '010,317,179' -> 0, 10317179."""
    out = []
    for t in re.findall(r"-?[\d,]+(?:\.\d+)?", line):
        t = t.replace(",", "")
        if len(t) > 1 and t.startswith("0") and "." not in t:
            out += [0, int(t[1:])]
        else:
            out.append(float(t))
    return out

for f in sorted(RAW.glob("pr_*.txt")):
    lines = f.read_text().splitlines()
    m1, m2 = lines[0].split(":")[1].split()
    for line in lines[1:]:
        circle = re.match(r"^[A-Za-z.&() ]+?(?=\s[-\d])", line).group(0).strip()
        nums = tokens(line[len(circle):])
        if circle == "TOTAL":
            checks.append({"file": f.name, "month1": m1, "month2": m2,
                           "printed_total_m1": nums[0], "printed_total_m2": nums[1]})
            continue
        if len(nums) == 12:                 # one Reliance Com zero dropped in extraction
            nums.insert(3, 0)
        has_vno = len(nums) == 15
        names = ["airtel", "rcom", "vi", "psu"] + (["vno"] if has_vno else []) + ["jio", "total"]
        vals = {n: (nums[2 * i], nums[2 * i + 1]) for i, n in enumerate(names)}
        for k, month in enumerate([m1, m2]):
            parts = {n: vals[n][k] for n in names if n != "total"}
            parts.setdefault("vno", 0)
            s = sum(parts.values())
            printed = {vals["total"][0], vals["total"][1]}   # some rows print the two totals swapped
            rows.append({"source": f.name, "month": month, "circle": circle, **parts,
                         "total": s, "sum_matches_printed": s in printed})

for f in sorted(RAW.glob("csv_*.csv")):
    d = pd.read_csv(f)
    m2 = f"{f.stem[4:8]}-{f.stem[9:11]}"
    m1 = (pd.Period(m2, "M") - 1).strftime("%Y-%m")
    for _, r in d.iterrows():
        for k, month in [("m1", m1), ("m2", m2)]:
            parts = {"airtel": r[f"airtel_{k}"], "rcom": 0, "vi": r[f"vi_{k}"],
                     "psu": r[f"psu_{k}"], "vno": 0, "jio": r[f"jio_{k}"]}
            s = sum(parts.values())
            rows.append({"source": f.name, "month": month, "circle": r["circle"], **parts,
                         "total": s, "sum_matches_printed": abs(s - r[f"total_{k}"]) <= 1000})

panel = pd.DataFrame(rows)

# ---- validation 1: every row's operators add up to the printed circle total
bad = panel[~panel["sum_matches_printed"]]
print(f"Rows checked: {len(panel)} | rows not matching printed total: {len(bad)}")
if len(bad):
    print(bad[["source", "month", "circle", "total"]].to_string())

# ---- validation 2: months that appear in two releases must agree
dup = panel.groupby(["month", "circle"])[["airtel", "vi", "psu", "jio"]].agg(["min", "max"])
diffs = {op: (dup[(op, "max")] - dup[(op, "min")]).abs().max() for op in ["airtel", "vi", "psu", "jio"]}
print("Max disagreement between overlapping releases:", diffs)

# ---- validation 3: national sum of circles vs TRAI printed national total
nat = panel.drop_duplicates(["month", "circle"]).groupby("month")["total"].sum()
for c in checks:
    for k in ("1", "2"):
        m, p = c[f"month{k}"], c[f"printed_total_m{k}"]
        print(f"{m}: circles sum {nat[m]:,.0f} vs printed {p:,.0f}  diff {nat[m]-p:,.0f}")

panel = (panel.sort_values("source").drop_duplicates(["month", "circle"], keep="last")
              .drop(columns=["source", "sum_matches_printed"]).sort_values(["circle", "month"]))
panel.to_csv(Path(__file__).parent / "data" / "trai_wireless_panel.csv", index=False)
print("Months:", sorted(panel["month"].unique()), "| circles:", panel["circle"].nunique())
