"""
How much pricing power do India's telcos have?
Evidence from the July 2024 tariff hike.

Data
- data/trai_wireless_panel.csv : wireless subscribers by circle x operator x month,
  Mar-2024 to Apr-2025, from TRAI monthly press releases (built by build_dataset.py)
- ARPU (Rs/month) from company quarterly results, Q1 FY25 (Apr-Jun 2024, pre-hike)
  and Q4 FY25 (Jan-Mar 2025, post-hike)

Run: python analysis.py   -> outputs/ (CSVs + charts)
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
OUT = HERE / "outputs"; OUT.mkdir(exist_ok=True)

# ------------------------------------------------------------------ inputs
panel = pd.read_csv(HERE / "data" / "trai_wireless_panel.csv")
OPS = ["jio", "airtel", "vi", "psu"]
LABEL = {"jio": "Jio", "airtel": "Airtel", "vi": "Vi", "psu": "BSNL/MTNL"}
COLOR = {"jio": "#2a78d6", "airtel": "#eb6834", "vi": "#1baf7a", "psu": "#eda100"}
INK, INK2, GRID, BG = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"

# Company-reported ARPU (Rs/month). Vi = customer ARPU excl. M2M (same definition both quarters).
ARPU = pd.DataFrame({
    "q1fy25": {"jio": 181.7, "airtel": 211.0, "vi": 154.0},
    "q4fy25": {"jio": 206.2, "airtel": 245.0, "vi": 175.3},
})

# DoT licence category of each circle (Metro / A / B / C). C = least affluent, most rural.
CATEGORY = {
    "Delhi": "Metro", "Mumbai": "Metro", "Kolkata": "Metro",
    "Andhra Pradesh": "A", "Gujarat": "A", "Karnataka": "A", "Maharashtra": "A", "Tamil Nadu": "A",
    "Haryana": "B", "Kerala": "B", "Madhya Pradesh": "B", "Punjab": "B", "Rajasthan": "B",
    "U.P.(E)": "B", "U.P.(W)": "B", "West Bengal": "B",
    "Assam": "C", "Bihar": "C", "Himachal Pradesh": "C", "J & K": "C", "North East": "C", "Odisha": "C",
}
panel["category"] = panel["circle"].map(CATEGORY)
panel["private"] = panel[["jio", "airtel", "vi"]].sum(axis=1)

PRE, TROUGH, LAST = "2024-06", "2024-11", "2025-04"   # hike took effect 3-4 July 2024

plt.rcParams.update({"font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False,
                     "axes.spines.right": False, "figure.facecolor": BG, "axes.facecolor": BG})
def save(fig, name):
    fig.tight_layout(); fig.savefig(OUT / name, dpi=180); plt.close(fig)

# ------------------------------------------------------------------ 1. national picture
nat = panel.groupby("month")[OPS + ["private", "total"]].sum() / 1e6     # millions
nat.round(2).to_csv(OUT / "01_national_subscribers_mn.csv")

# Counterfactual: continue each operator's pre-hike trend (avg monthly change Mar->Jun 2024)
trend = (nat.loc[PRE] - nat.loc["2024-03"]) / 3
months_after = {m: i for i, m in enumerate(nat.index) if m > PRE for i in [nat.index.get_loc(m) - nat.index.get_loc(PRE)]}
def vs_trend(month):
    k = nat.index.get_loc(month) - nat.index.get_loc(PRE)
    expected = nat.loc[PRE] + trend * k
    return nat.loc[month] - expected

shock = pd.DataFrame({
    "subs_jun24_mn": nat.loc[PRE],
    "change_to_nov24_mn": nat.loc[TROUGH] - nat.loc[PRE],
    "pct_change_to_nov24": (nat.loc[TROUGH] / nat.loc[PRE] - 1) * 100,
    "vs_pretrend_nov24_mn": vs_trend(TROUGH),
    "change_to_apr25_mn": nat.loc[LAST] - nat.loc[PRE],
    "vs_pretrend_apr25_mn": vs_trend(LAST),
}).loc[OPS + ["private", "total"]]
shock.round(2).to_csv(OUT / "02_hike_shock_by_operator.csv")

# Where did private operators' lost subscribers go?
lost_private = -(nat.loc[TROUGH, "private"] - nat.loc[PRE, "private"])
to_psu = nat.loc[TROUGH, "psu"] - nat.loc[PRE, "psu"]
left_market = lost_private - to_psu
flows = pd.Series({"private_lost_mn": lost_private, "moved_to_bsnl_mtnl_mn": to_psu,
                   "left_market_sim_consolidation_mn": left_market,
                   "share_left_market": left_market / lost_private})
flows.round(3).to_csv(OUT / "03_where_subscribers_went.csv", header=["value"])

# ------------------------------------------------------------------ 2. circles
c = panel.pivot_table(index="circle", columns="month", values=["private", "psu", "total"], aggfunc="sum")
circ = pd.DataFrame({
    "category": pd.Series(CATEGORY),
    "private_jun24_mn": c[("private", PRE)] / 1e6,
    "private_pct_change_jun_nov": (c[("private", TROUGH)] / c[("private", PRE)] - 1) * 100,
    "psu_share_jun24_pct": c[("psu", PRE)] / c[("total", PRE)] * 100,
    "psu_gain_pp": (c[("psu", TROUGH)] / c[("total", TROUGH)] - c[("psu", PRE)] / c[("total", PRE)]) * 100,
    "private_pct_change_jun_apr25": (c[("private", LAST)] / c[("private", PRE)] - 1) * 100,
}).sort_values("private_pct_change_jun_nov")
circ.round(2).to_csv(OUT / "04_circle_response.csv")

cat = panel[panel["month"].isin([PRE, TROUGH])].groupby(["category", "month"])["private"].sum().unstack()
cat_resp = ((cat[TROUGH] / cat[PRE] - 1) * 100).reindex(["Metro", "A", "B", "C"])
cat_resp.round(2).to_csv(OUT / "05_category_response.csv", header=["private_pct_change_jun_nov"])
corr = circ["psu_share_jun24_pct"].corr(circ["psu_gain_pp"])

# ------------------------------------------------------------------ 3. did the hike pay off?
q1 = nat.loc[["2024-04", "2024-05", "2024-06"], ["jio", "airtel", "vi"]].mean()
q4 = nat.loc[["2025-01", "2025-02", "2025-03"], ["jio", "airtel", "vi"]].mean()
pay = pd.DataFrame({"subs_q1fy25_mn": q1, "subs_q4fy25_mn": q4,
                    "arpu_q1fy25": ARPU["q1fy25"], "arpu_q4fy25": ARPU["q4fy25"]})
pay["arpu_pct"] = (pay["arpu_q4fy25"] / pay["arpu_q1fy25"] - 1) * 100
pay["subs_pct"] = (pay["subs_q4fy25_mn"] / pay["subs_q1fy25_mn"] - 1) * 100
pay["rev_q1_rs_cr_month"] = pay["subs_q1fy25_mn"] * pay["arpu_q1fy25"] / 10      # mn x Rs -> Rs cr
pay["rev_q4_rs_cr_month"] = pay["subs_q4fy25_mn"] * pay["arpu_q4fy25"] / 10
pay["rev_pct"] = (pay["rev_q4_rs_cr_month"] / pay["rev_q1_rs_cr_month"] - 1) * 100
# Price-response ratio: % subscribers changed per 1% ARPU increase, net of pre-hike trend
trend_q = trend[["jio", "airtel", "vi"]] * 9 / pay["subs_q1fy25_mn"] * 100   # 9 months of pre-trend, in %
pay["subs_pct_vs_trend"] = pay["subs_pct"] - trend_q
pay["response_per_1pct_price"] = pay["subs_pct_vs_trend"] / pay["arpu_pct"]
pay.drop(columns=["rev_q1_rs_cr_month", "rev_q4_rs_cr_month"]).round(3).to_csv(OUT / "06_did_hike_pay_off.csv")

# ------------------------------------------------------------------ 4. next-hike scenarios
pay["response_raw_per_1pct_price"] = pay["subs_pct"] / pay["arpu_pct"]   # no trend adjustment
rows = []
# Two bounds: 'raw' = subscriber change as observed; 'vs_trend' = shortfall vs pre-hike growth path
for case, col in [("raw", "response_raw_per_1pct_price"), ("vs_trend", "response_per_1pct_price")]:
    for hike in [10, 15, 20]:
        for op in ["jio", "airtel", "vi"]:
            base_subs = pay.loc[op, "subs_q4fy25_mn"]
            subs_chg = min(pay.loc[op, col], 0) * hike        # assume no subscriber gain from a price rise
            rev_chg = ((1 + subs_chg / 100) * (1 + hike / 100) - 1) * 100
            rows.append({"case": case, "hike_pct": hike, "operator": LABEL[op],
                         "subs_change_mn": base_subs * subs_chg / 100,
                         "subs_change_pct": subs_chg, "revenue_change_pct": rev_chg})
scen = pd.DataFrame(rows)
scen.round(1).to_csv(OUT / "07_next_hike_scenarios.csv", index=False)

# ------------------------------------------------------------------ 5. charts
# (a) indexed subscribers
fig, ax = plt.subplots(figsize=(7, 3.6))
idx = nat[OPS].div(nat.loc[PRE, OPS]) * 100
x = np.arange(len(idx))
for op in OPS:
    ax.plot(x, idx[op], color=COLOR[op], lw=2)
    ax.text(x[-1] + 0.2, idx[op].iloc[-1], LABEL[op], color=INK, va="center", fontsize=9)
ax.axvline(idx.index.get_loc("2024-07") - 0.5, color=INK2, lw=1, ls="--")
ax.text(idx.index.get_loc("2024-07") - 0.4, ax.get_ylim()[1] - 0.4, "Tariff hike\n(3-4 Jul 2024)", fontsize=8, color=INK2, va="top")
ax.axhline(100, color=GRID, lw=1)
ax.set_xticks(x[::2], [pd.Period(m).strftime("%b-%y") for m in idx.index[::2]])
ax.set_ylabel("Subscribers (Jun-24 = 100)"); ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True)
ax.set_xlim(-0.3, len(x) + 1.2)
ax.set_title("Subscribers after the July 2024 tariff hike", loc="left", color=INK)
save(fig, "chart1_subscribers_indexed.png")

# (b) where lost subscribers went
fig, ax = plt.subplots(figsize=(7, 2.0))
ax.barh([0], [to_psu], color=COLOR["psu"], height=0.5)
ax.barh([0], [left_market], left=[to_psu + 0.15], color="#8b8a85", height=0.5)
ax.text(to_psu / 2, 0, f"Moved to BSNL/MTNL\n{to_psu:.1f} mn", ha="center", va="center", color=INK, fontsize=9)
ax.text(to_psu + left_market / 2, 0, f"Dropped a SIM / left market\n{left_market:.1f} mn", ha="center", va="center", color="white", fontsize=9)
ax.set_yticks([]); ax.set_xlabel("Million subscribers (Jun-24 to Nov-24)"); ax.set_xlim(0, lost_private * 1.02)
ax.set_title(f"Private operators lost {lost_private:.1f} mn subscribers: where did they go?", loc="left", color=INK)
save(fig, "chart2_where_subscribers_went.png")

# (c) circle response
fig, ax = plt.subplots(figsize=(7, 5.4))
cat_colors = {"Metro": "#6250d6", "A": "#2a78d6", "B": "#1baf7a", "C": "#eb6834"}
cc = circ.iloc[::-1]
ax.barh(cc.index, cc["private_pct_change_jun_nov"], color=[cat_colors[k] for k in cc["category"]], height=0.65)
ax.axvline(0, color=INK2, lw=1)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=cat_colors[k], label=f"Category {k}" if k != "Metro" else "Metro") for k in ["Metro", "A", "B", "C"]],
          frameon=False, loc="lower left", fontsize=8)
ax.set_xlabel("Change in Jio + Airtel + Vi subscribers, Jun-24 to Nov-24 (%)")
ax.xaxis.grid(True, color=GRID); ax.set_axisbelow(True); ax.tick_params(axis="y", labelsize=8.5)
ax.set_title("Which circles pushed back hardest on the price hike", loc="left", color=INK)
save(fig, "chart3_circle_response.png")

# (d) price up vs subscribers vs revenue
fig, ax = plt.subplots(figsize=(7, 3.2))
ops = ["jio", "airtel", "vi"]; w = 0.26; xx = np.arange(3)
series = [("arpu_pct", "ARPU change", "#2a78d6"), ("subs_pct", "Subscriber change", "#eb6834"),
          ("rev_pct", "Revenue change (est.)", "#1baf7a")]
for i, (col, lab, colr) in enumerate(series):
    vals = pay.loc[ops, col]
    ax.bar(xx + (i - 1) * w, vals, width=w - 0.03, color=colr, label=lab)
    for xv, v in zip(xx + (i - 1) * w, vals):
        ax.text(xv, v + (0.4 if v >= 0 else -0.4), f"{v:+.1f}%", ha="center", va="bottom" if v >= 0 else "top", fontsize=8, color=INK)
ax.axhline(0, color=INK2, lw=1); ax.set_ylim(-8, 20)
ax.set_xticks(xx, [LABEL[o] for o in ops]); ax.set_ylabel("% change, Q1 FY25 to Q4 FY25")
ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True)
ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12), fontsize=8.5)
ax.set_title("Price went up far more than customers went down", loc="left", color=INK)
save(fig, "chart4_did_it_pay_off.png")

# ------------------------------------------------------------------ print
pd.set_option("display.width", 200); pd.set_option("display.float_format", lambda v: f"{v:,.2f}")
print("NATIONAL (mn)\n", nat.round(2))
print("\nSHOCK\n", shock)
print("\nFLOWS\n", flows)
print("\nCIRCLES\n", circ)
print("\nCATEGORY\n", cat_resp, "\ncorr(psu share, psu gain) =", round(corr, 2))
print("\nPAY-OFF\n", pay.T)
print("\nSCENARIOS\n", scen)
