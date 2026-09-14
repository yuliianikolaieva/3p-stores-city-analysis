#!/usr/bin/env python3
"""Build a self-contained index.html for the 3P Stores city/partner analysis.

Reads threep_data.json (exported from Databricks: ng_delivery_spark.fact_provider_monthly
joined with dim_provider_v2, UA, delivery_vertical IN store_3p_ent/store_3p_mm_smb) and
renders a static GitHub Pages report. No runtime data fetch — data is embedded server-side.
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
DATA = json.loads((HERE / "threep_data.json").read_text(encoding="utf-8"))
MLABEL = {"jan": "Jan", "feb": "Feb", "mar": "Mar", "apr": "Apr", "may": "May", "jun": "Jun", "jul": "Jul", "aug": "Aug"}
SEGS = ["Enterprise", "Mid-market", "SMB"]
CUR = DATA["meta"].get("cur", "jun")
PREV = DATA["meta"].get("prev", "may")
CURLBL = MLABEL[CUR]
PREVLBL = MLABEL[PREV]
PERIOD = DATA["meta"].get("period", "Apr–Jun 2026")
LATEST = DATA["meta"].get("latest", "June 2026")


def eur(n):
    if n is None:
        return "–"
    neg = n < 0
    a = abs(n)
    s = f"€{a/1000:.1f}k" if a >= 1000 else f"€{a:.0f}"
    if a >= 100000:
        s = f"€{a/1000:.0f}k"
    return ("−" + s) if neg else s


def pct(n, sign=False):
    if n is None:
        return "–"
    return ("+" if sign and n > 0 else "") + f"{n:.1f}%"


def seg_val(seg, month, field):
    for s in DATA["segments"]:
        if s["segment"] == seg and s["month"] == month:
            return s[field]
    return 0


def delta_span(v):
    if v is None:
        return '<span class="mut">–</span>'
    cls = "up" if v > 0 else ("down" if v < 0 else "mut")
    return f'<span class="{cls}">{("+" if v>0 else "")}{v:.1f}%</span>'


def money_span(v):
    cls = "up" if v > 0 else ("down" if v < 0 else "mut")
    return f'<span class="{cls}">{eur(v)}</span>'


def row_cls(cp, margin=None):
    if cp < 0:
        return "neg"
    if margin is not None and margin >= 5:
        return "pos"
    return ""


# ── KPIs ──────────────────────────────────────────────────────────────────────
jun, may = DATA["totals"][CUR], DATA["totals"][PREV]
gmv_mom = (jun["gmv"] / may["gmv"] - 1) * 100
ord_mom = (jun["orders"] / may["orders"] - 1) * 100
cp_margin = jun["cp"] / jun["gmv"] * 100

kpis = f"""
<div class="grid kpis">
  <div class="kpi base"><div class="n">{eur(jun['gmv'])}</div><div class="l">GMV · MoM {pct(gmv_mom, True)}</div></div>
  <div class="kpi {'opt' if jun['cp']>=0 else 'warn'}"><div class="n">{eur(jun['cp'])}</div><div class="l">Contribution Profit</div></div>
  <div class="kpi {'opt' if cp_margin>=0 else 'warn'}"><div class="n">{cp_margin:.1f}%</div><div class="l">CP margin</div></div>
  <div class="kpi base"><div class="n">{jun['orders']/1000:.1f}k</div><div class="l">Orders · MoM {pct(ord_mom, True)}</div></div>
  <div class="kpi"><div class="n">{jun['brands']}</div><div class="l">Partners · {len(DATA['cities'])} active cities</div></div>
</div>
<div class="grid kpis" style="margin-top:14px">
  <div class="kpi"><div class="n">€{jun['ef_pou']:.2f}</div><div class="l">Eater fees / order</div></div>
  <div class="kpi"><div class="n">{jun['ef_pct']:.1f}%</div><div class="l">Eater fees, % GMV</div></div>
  <div class="kpi warn"><div class="n">€{jun['cpo']:.2f}</div><div class="l">CPO (courier cost / order)</div></div>
  <div class="kpi"><div class="n">{jun['camp_bolt_pct']:.1f}%</div><div class="l">Campaign spend Bolt, % GMV</div></div>
  <div class="kpi"><div class="n">{jun['camp_share']:.1f}%</div><div class="l">Campaign orders share</div></div>
</div>
"""

# ── Segment scorecard ───────────────────────────────────────────────────────────
seg_rows = ""
for seg in SEGS:
    g = seg_val(seg, CUR, "gmv")
    gm = seg_val(seg, PREV, "gmv")
    cp = seg_val(seg, CUR, "cp")
    orders = seg_val(seg, CUR, "orders")
    brands = seg_val(seg, CUR, "brands")
    ef = seg_val(seg, CUR, "eater_fee")
    cc = seg_val(seg, CUR, "courier_costs")
    cb = seg_val(seg, CUR, "camp_bolt")
    co = seg_val(seg, CUR, "camp_orders")
    share = g / jun["gmv"] * 100
    mom = (g / gm - 1) * 100 if gm else None
    margin = cp / g * 100 if g else 0
    ef_pou = ef / orders if orders else 0
    cpo = cc / orders if orders else 0
    cb_pct = cb / g * 100 if g else 0
    camp_ord = co / orders * 100 if orders else 0
    seg_rows += (
        f'<tr class="{row_cls(cp)}"><td class="axis">{seg}</td><td>{eur(g)}</td><td>{share:.0f}%</td>'
        f"<td>{delta_span(mom)}</td><td>{money_span(cp)}</td><td>{margin:.1f}%</td>"
        f"<td>{orders:,}</td><td>€{ef_pou:.2f}</td><td>{ef/g*100 if g else 0:.1f}%</td>"
        f"<td>€{cpo:.2f}</td><td>{cb_pct:.1f}%</td><td>{camp_ord:.0f}%</td><td>{brands}</td></tr>"
    )

# ── City ranking (all active cities, sorted by GMV) ─────────────────────────────
def rate(v):
    return "–" if v is None else f"{v:.1f}%"


cities = sorted(DATA["cities"], key=lambda c: -c["gmv"])
city_rows = ""
for c in cities:
    margin_s = rate(c["cp_margin"])
    city_rows += (
        f'<tr class="{row_cls(c["cp"], c["cp_margin"])}"><td class="axis">{c["city"]}</td>'
        f'<td>{eur(c["gmv"])}</td><td>{c["share"]:.1f}%</td><td>{delta_span(c["pop"])}</td>'
        f'<td>{money_span(c["cp"])}</td><td>{margin_s}</td>'
        f'<td>{c["orders"]:,}</td><td>€{c["aov"]:.1f}</td>'
        f'<td>{rate(c["failed_rate"])}</td><td>{rate(c["late_rate"])}</td></tr>'
    )

# ── City eater fees, CPO & campaigns ────────────────────────────────────────────
def rate0(v):
    return "–" if v is None else f"{v:.0f}%"


city_econ_rows = ""
for c in cities:
    ef_pou_s = "–" if c["ef_pou"] is None else f"€{c['ef_pou']:.2f}"
    cpo_s = "–" if c["cpo"] is None else f"€{c['cpo']:.2f}"
    city_econ_rows += (
        f'<tr><td class="axis">{c["city"]}</td><td>{c["orders"]:,}</td>'
        f'<td>{eur(c["eater_fee"])}</td><td>{ef_pou_s}</td><td>{rate(c["ef_pct"])}</td>'
        f'<td>{cpo_s}</td>'
        f'<td>{eur(c["camp_bolt"])}</td><td>{eur(c["camp_prov"])}</td><td>{eur(c["camp_disc"])}</td>'
        f'<td>{rate(c["camp_bolt_pct"])}</td><td>{rate0(c["camp_share"])}</td></tr>'
    )

# ── Per-city partner breakdown (top 15 cities) ──────────────────────────────────
city_cards = ""
for c in cities[:15]:
    seg_bits = []
    for s in SEGS:
        sd = c["segments"].get(s)
        if sd and sd["gmv"] > 0:
            m = sd["cp"] / sd["gmv"] * 100 if sd["gmv"] else 0
            seg_bits.append(f'<span class="pill">{s}: {eur(sd["gmv"])} · CP {money_span(sd["cp"])} ({m:.0f}%)</span>')
    brows = ""
    for b in c["top_brands"]:
        ef_s = "–" if b.get("ef_pou") is None else f"€{b['ef_pou']:.2f}"
        cpo_s = "–" if b.get("cpo") is None else f"€{b['cpo']:.2f}"
        camp_s = "–" if b.get("camp_share") is None else f"{b['camp_share']:.0f}%"
        brows += (
            f'<tr class="{row_cls(b["cp"])}"><td class="axis">{b["brand"]}</td><td>{b["seg"]}</td>'
            f'<td>{eur(b["gmv"])}</td><td>{b["orders"]:,}</td><td>{delta_span(b["pop"])}</td>'
            f'<td>{money_span(b["cp"])}</td><td>{ef_s}</td><td>{cpo_s}</td><td>{camp_s}</td></tr>'
        )
    cmargin_s = rate(c["cp_margin"])
    city_cards += f"""
    <div class="chartcard">
      <h3>{c['city']} — {eur(c['gmv'])} GMV · CP {money_span(c['cp'])} ({cmargin_s}) · MoM {delta_span(c['pop'])}</h3>
      <div class="meta" style="margin:6px 0 10px">{''.join(seg_bits)}</div>
      <table class="matrix"><thead><tr><th>Partner</th><th>Segment</th><th>GMV</th><th>Orders</th><th>MoM</th><th>CP</th><th>Eater fee/ord</th><th>CPO</th><th>Camp ord%</th></tr></thead><tbody>{brows}</tbody></table>
    </div>"""

# ── Partner leaderboard ─────────────────────────────────────────────────────────
brand_rows = ""
for b in DATA["brands"]:
    ef_s = "–" if b.get("ef_pou") is None else f"€{b['ef_pou']:.2f}"
    cpo_s = "–" if b.get("cpo") is None else f"€{b['cpo']:.2f}"
    camp_s = "–" if b.get("camp_share") is None else f"{b['camp_share']:.0f}%"
    brand_rows += (
        f'<tr class="{row_cls(b["cp"])}"><td class="axis">{b["brand"]}</td><td>{b["seg"]}</td>'
        f'<td>{b["main_city"]}</td><td>{b["ncities"]}</td><td>{eur(b["gmv"])}</td>'
        f'<td>{delta_span(b["pop"])}</td><td>{money_span(b["cp"])}</td><td>{b["cp_margin"]:.1f}%</td>'
        f'<td>{ef_s}</td><td>{cpo_s}</td><td>{camp_s}</td></tr>'
    )

# ── Movers ──────────────────────────────────────────────────────────────────────
elig = [b for b in DATA["brands"] if b.get("gmv_may") and b["gmv_may"] > 3000 and b["pop"] is not None]
growing = sorted(elig, key=lambda b: -b["pop"])[:6]
declining = sorted(elig, key=lambda b: b["pop"])[:6]


def mover_rows(arr):
    return "".join(
        f'<tr><td class="axis">{b["brand"]}</td><td>{b["main_city"]}</td><td>{eur(b["gmv"])}</td><td>{delta_span(b["pop"])}</td></tr>'
        for b in arr
    )

# ── Profitability diagnosis (auto-refreshed from diag_data.json) ─────────────────
_DG = json.loads((HERE / "diag_data.json").read_text(encoding="utf-8"))
DIAG = _DG["DIAG"]; DIAG_MONTH = _DG["month_label"]; CITYWORST = _DG["CITYWORST"]
UAMON = {"Jan": "січень", "Feb": "лютий", "Mar": "березень", "Apr": "квітень", "May": "травень",
         "Jun": "червень", "Jul": "липень", "Aug": "серпень", "Sep": "вересень", "Oct": "жовтень",
         "Nov": "листопад", "Dec": "грудень"}
DIAG_MONTH_UA = UAMON.get(DIAG_MONTH, DIAG_MONTH)
_prof = [d["brand"] for d in DIAG if d["margin"] >= 0]
_loss = sorted(DIAG, key=lambda d: d["margin"])
diag_summary = (f"У {DIAG_MONTH_UA}: прибуткові — {', '.join(_prof) if _prof else 'немає'}; "
                f"найглибший мінус — {_loss[0]['brand']} ({_loss[0]['margin']:.1f}%). "
                f"Головні важелі: промо (частка замовлень з кампанією), CPO і комісія.")
diag_rows = ""
for d in DIAG:
    diag_rows += (
        f'<tr class="neg"><td class="axis">{d["brand"]}</td><td>€{d["aov"]:.1f}</td>'
        f'<td>{d["own"]}%</td><td>{d["comm_pct"]:.1f}%</td><td>€{d["comm"]:.2f}</td>'
        f'<td>€{d["ef"]:.2f}</td><td>€{d["cpo"]:.2f}</td><td>€{d["inc"]:.2f}</td>'
        f'<td>€{d["refund"]:.2f}</td><td>€{d["camp"]:.2f}</td><td>{d["camp_ord"]}%</td>'
        f'<td><span class="down">€{d["cpo_ord"]:.2f}</span></td><td><span class="down">{d["margin"]:.1f}%</span></td></tr>'
    )
cityworst_rows = "".join(
    f'<tr class="neg"><td class="axis">{b}</td><td>{c}</td><td>{o:,}</td>'
    f'<td><span class="down">{eur(cp)}</span></td><td><span class="down">{m:.1f}%</span></td>'
    f'<td>€{cpo:.2f}</td><td>{cs}%</td><td>€{rf:.2f}</td><td style="text-align:left;font-size:12px">{note}</td></tr>'
    for (b, c, o, cp, m, cpo, cs, rf, note) in CITYWORST
)
reco_cards = ""
for d in DIAG:
    lis = "".join(f"<li>{x}</li>" for x in d["reco"])
    reco_cards += (
        f'<div class="callout" style="border-left-color:var(--accent)">'
        f'<h3>{d["brand"]} · CP {d["margin"]:.1f}%</h3>'
        f'<p style="margin-bottom:6px">{d["why"]}</p>'
        f'<ul style="margin:0;padding-left:18px;color:var(--soft);font-size:14px">{lis}</ul></div>'
    )

SIM = json.loads((HERE / "sim_data.json").read_text(encoding="utf-8")) if (HERE / "sim_data.json").exists() else {}

# ── Commission tab: actuals (dbx, auto) + forecast (Excel, static) ──────────────
COMM_ACT = json.loads((HERE / "commission_actuals.json").read_text(encoding="utf-8"))
COMM_FC = json.loads((HERE / "commission_forecast.json").read_text(encoding="utf-8"))
GLBL = COMM_FC["grp_label"]; GRP_ORDER = ["TOTAL", "TOP", "ENT_OTH", "SMB", "MM"]
top_brands_list = COMM_FC["top_brands_list"]
ACT_MONTHS = COMM_ACT["months"]; _last_act = ACT_MONTHS[-1]; _fc_all = COMM_FC["months"]
FC_MONTHS = _fc_all[_fc_all.index(_last_act) + 1:] if _last_act in _fc_all else []
CM_MONTHS = ACT_MONTHS + FC_MONTHS
_act = {g: {x["m"]: x for x in COMM_ACT["actual_series"][g]} for g in GRP_ORDER}
_fc = {g: {x["m"]: x for x in COMM_FC["opt"][g]} for g in GRP_ORDER}
def _cell_for(g, m, key):
    src = _act[g].get(m) if m in ACT_MONTHS else _fc[g].get(m)
    return None if not src else src.get(key)
COMM_JS = {"months": CM_MONTHS, "grp_label": GLBL, "opt": {}}
for g in GRP_ORDER:
    COMM_JS["opt"][g] = [{"m": m, "comm_pct": _cell_for(g, m, "comm_pct"), "comm_aov": _cell_for(g, m, "comm_aov"),
                          "comm": _cell_for(g, m, "comm"), "aov": _cell_for(g, m, "aov")} for m in CM_MONTHS]
cm_last = _act["TOTAL"][_last_act]; cm_first = COMM_JS["opt"]["TOTAL"][0]
q4o = COMM_FC["q4_opt"]; q4p = COMM_FC["q4_pess"]
cm_jul_pct = f'{cm_last["comm_pct"]:.1f}%'; cm_jan_pct = f'{cm_first["comm_pct"]:.1f}%'
cm_jul_aov = f'{cm_last["aov"]:.2f}'
q4o_comm = eur(q4o["TOTAL"]["comm"]); q4o_pct = f'{q4o["TOTAL"]["comm_pct"]:.1f}%'
q4o_aov = f'{q4o["TOTAL"]["aov"]:.2f}'; q4p_comm = eur(q4p["TOTAL"]["comm"])
comm_month_headers = "".join(f"<th>{m}</th>" for m in CM_MONTHS)
def _pct_cell(v): return "<td>-</td>" if v is None else f"<td>{v:.1f}%</td>"
def _ratio_row(g, key, tag, cls=""):
    cells = "".join(_pct_cell(x[key]) for x in COMM_JS["opt"][g])
    return f'<tr class="{cls}"><td class="axis">{GLBL[g]} · {tag}</td>{cells}</tr>'
comm_grp_rows = ""
for _g in GRP_ORDER:
    comm_grp_rows += _ratio_row(_g, "comm_pct", "%GMV", "pos" if _g == "TOTAL" else "")
    comm_grp_rows += _ratio_row(_g, "comm_aov", "%AOV")
_aov_cells = "".join(("<td>-</td>" if x["aov"] is None else f"<td>€{x['aov']:.1f}</td>") for x in COMM_JS["opt"]["TOTAL"])
_eur_cells = "".join(("<td>-</td>" if x["comm"] is None else f"<td>{eur(x['comm'])}</td>") for x in COMM_JS["opt"]["TOTAL"])
comm_grp_rows += f'<tr><td class="axis">Total · AOV</td>{_aov_cells}</tr>'
comm_grp_rows += f'<tr><td class="axis">Total · commission €</td>{_eur_cells}</tr>'
def _q4_row(g):
    o = q4o[g]; pp = q4p[g]
    op = "-" if o["comm_pct"] is None else f'{o["comm_pct"]:.1f}%'
    pc = "-" if pp["comm_pct"] is None else f'{pp["comm_pct"]:.1f}%'
    oa = "-" if o["aov"] is None else f'€{o["aov"]:.1f}'
    cls = "pos" if g == "TOTAL" else ""
    return (f'<tr class="{cls}"><td class="axis">{GLBL[g]}</td>'
            f'<td>{eur(o["comm"])}</td><td>{op}</td><td>{oa}</td><td>{eur(o["gmv"])}</td>'
            f'<td>{eur(pp["comm"])}</td><td>{pc}</td></tr>')
q4_rows = "".join(_q4_row(g) for g in GRP_ORDER)
def _tbq_row(d):
    jp = "-" if d["jul_pct"] is None else f'{d["jul_pct"]:.1f}%'
    qp = "-" if d["q4_pct"] is None else f'{d["q4_pct"]:.1f}%'
    jc = eur(d["jul_comm"]) if d["jul_comm"] else "-"
    status = "" if d["jul_comm"] else "новий у прогнозі"
    cls = "" if d["jul_comm"] else "pos"
    return (f'<tr class="{cls}"><td class="axis">{d["brand"]}</td><td>{jc}</td><td>{jp}</td>'
            f'<td>{eur(d["q4_comm"])}</td><td>{qp}</td><td>{d["q4_locs"]}</td>'
            f'<td style="text-align:left">{status}</td></tr>')
comm_tbq_rows = "".join(_tbq_row(d) for d in COMM_FC["top_brand_q4"])
def _p_row(rec):
    a = "-" if rec.get("aov") is None else f'€{rec["aov"]:.1f}'
    return (f'<tr><td class="axis">{rec["brand"]}</td><td>{rec["seg"]}</td>'
            f'<td>{eur(rec["comm"])}</td><td>{rec["comm_pct"]:.1f}%</td><td>{a}</td></tr>')
comm_oth_rows = "".join(_p_row(r) for r in COMM_ACT["partners_ent_oth"])

# ── Chart data ──────────────────────────────────────────────────────────────────
months = DATA["meta"]["months"]
chart_labels = json.dumps([MLABEL[m] for m in months])
gmv_ds = {seg: [seg_val(seg, m, "gmv") for m in months] for seg in SEGS}
cp_ds = {seg: [seg_val(seg, m, "cp") for m in months] for seg in SEGS}
city_bar_labels = json.dumps([c["city"] for c in cities[:12]])
city_bar_gmv = json.dumps([c["gmv"] for c in cities[:12]])
city_bar_cp = json.dumps([c["cp"] for c in cities[:12]])

HTML = f"""<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>3P Stores — City & Partner Analysis · Bolt Food UA</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root{{
    --bg:#eef1f7; --panel:#ffffff; --panel2:#f6f8fc; --line:#dfe5ee;
    --text:#13203a; --muted:#5d6b85; --soft:#33425d;
    --accent:#2563eb; --accent2:#0e7faa;
    --base:#2563eb; --opt:#15a34a; --warn:#d1493f; --up:#15a34a; --down:#d1493f;
  }}
  *{{box-sizing:border-box}}
  html{{scroll-behavior:smooth}}
  body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
       background:radial-gradient(1200px 600px at 80% -10%,#ffffff 0%,var(--bg) 55%);color:var(--text);line-height:1.55}}
  a{{color:var(--accent)}}
  nav.topnav{{position:sticky;top:0;z-index:50;background:rgba(255,255,255,.92);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}}
  nav.topnav .inner{{max-width:1180px;margin:0 auto;padding:10px 20px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}}
  nav.topnav .brand{{font-weight:800;font-size:13px;color:var(--accent2);margin-right:8px;white-space:nowrap}}
  nav.topnav a{{color:var(--muted);text-decoration:none;font-size:13px;padding:6px 11px;border-radius:8px;border:1px solid transparent;white-space:nowrap}}
  nav.topnav a:hover{{background:#eef2f8;color:var(--text)}}
  .wrap{{max-width:1180px;margin:0 auto;padding:28px 20px 80px}}
  section[id]{{scroll-margin-top:64px}}
  header.hero{{padding:34px 30px;border:1px solid var(--line);border-radius:18px;
       background:linear-gradient(135deg,#ffffff 0%,#eef3fb 100%);position:relative;overflow:hidden;box-shadow:0 1px 3px rgba(20,40,80,.05)}}
  .hero h1{{margin:0 0 6px;font-size:27px;letter-spacing:.2px}}
  .hero .sub{{color:var(--soft);font-size:15px;max-width:880px}}
  .hero .tag{{display:inline-block;margin-bottom:14px;font-size:12px;letter-spacing:2px;text-transform:uppercase;color:var(--accent2);font-weight:700}}
  .meta{{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px}}
  .meta .pill{{background:#f1f5fb;border:1px solid var(--line);border-radius:999px;padding:6px 13px;font-size:12.5px;color:var(--muted)}}
  h2.section{{font-size:20px;margin:42px 0 6px;display:flex;align-items:center;gap:10px}}
  h2.section .bar{{width:6px;height:22px;border-radius:3px;background:var(--accent)}}
  .section-desc{{color:var(--muted);font-size:14px;margin:0 0 18px}}
  .grid{{display:grid;gap:16px}}
  .kpis{{grid-template-columns:repeat(5,1fr);margin-top:22px}}
  .kpi{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px 18px;box-shadow:0 1px 3px rgba(20,40,80,.05)}}
  .kpi .n{{font-size:24px;font-weight:800}}
  .kpi .l{{color:var(--muted);font-size:12px;margin-top:2px}}
  .kpi.base .n{{color:var(--base)}} .kpi.opt .n{{color:var(--opt)}} .kpi.warn .n{{color:var(--warn)}}
  .callout{{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--warn);border-radius:12px;padding:16px 18px;margin-top:18px;box-shadow:0 1px 3px rgba(20,40,80,.05)}}
  .callout h3{{margin:0 0 8px;font-size:15px}}
  .callout p{{margin:0;color:var(--soft);font-size:14px}}
  .two{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
  table.matrix{{border-collapse:collapse;width:100%;margin-top:12px;font-size:13px;border:1px solid var(--line);border-radius:10px;overflow:hidden}}
  table.matrix th,table.matrix td{{border:1px solid var(--line);padding:8px 10px;text-align:right}}
  table.matrix th{{background:#eef2f8;color:var(--muted);font-weight:600;text-align:right;position:sticky;top:0}}
  table.matrix th:first-child,table.matrix td:first-child{{text-align:left}}
  table.matrix td.axis{{background:#f3f6fb;color:var(--soft);font-weight:700;text-align:left}}
  table.matrix tr.neg td{{background:rgba(209,73,63,.07)}}
  table.matrix tr.pos td{{background:rgba(21,163,74,.07)}}
  .tablewrap{{max-height:560px;overflow:auto;border-radius:10px}}
  .up{{color:var(--up);font-weight:600}} .down{{color:var(--down);font-weight:600}} .mut{{color:var(--muted)}}
  .chartcard{{background:var(--panel);border:1px solid var(--line);border-radius:16px;margin-top:16px;padding:18px 20px;box-shadow:0 1px 3px rgba(20,40,80,.05)}}
  .chartcard h3{{margin:0 0 2px;font-size:15px}}
  .chartcard .cap{{color:var(--muted);font-size:12px;margin:0 0 10px}}
  footer{{margin-top:48px;padding-top:20px;border-top:1px solid var(--line);color:var(--muted);font-size:12.5px}}
  @media(max-width:900px){{.kpis{{grid-template-columns:repeat(2,1fr)}}.two{{grid-template-columns:1fr}}.hero h1{{font-size:22px}}}}
</style>
</head>
<body>
<nav class="topnav"><div class="inner">
  <span class="brand">3P Stores · Bolt Food UA</span>
  <a href="#top">Overview</a>
  <a href="#segments">Segments</a>
  <a href="#commission">Commission</a>
  <a href="#cities">Cities</a>
  <a href="#econ">Eater fees · CPO · Campaigns</a>
  <a href="#deepdive">City deep-dive</a>
  <a href="#partners">Partners</a>
  <a href="#diagnosis">Why loss-making + reco</a>
  <a href="#movers">Movers</a>
</div></nav>
<div class="wrap">
  <header class="hero" id="top">
    <span class="tag">Ukraine retail · 3P Stores</span>
    <h1>3P Stores — аналіз по містах, фінанс, опс і партнери</h1>
    <p class="sub">Bolt Food · Україна · вертикаль <b>3P Stores</b> (store_3p_ent + store_3p_mm_smb). Всі ключові метрики delivery-репорту в розрізі міст і партнерів, з поділом на Enterprise / Mid-market / SMB. Останній повний місяць — <b>{LATEST}</b>.</p>
    <div class="meta">
      <span class="pill">Period: {PERIOD}</span>
      <span class="pill">Latest: {CURLBL} 2026</span>
      <span class="pill">Source: dbx fact_provider_monthly + dim_provider_v2</span>
      <span class="pill">{len(DATA['cities'])} active cities · {jun['brands']} partners</span>
    </div>
    {kpis}
  </header>

  <section id="overview">
    <div class="callout">
      <h3>Головний висновок: обсяг і маржа рознесені по сегментах</h3>
      <p>Enterprise робить <b>~88% GMV</b> і вже вийшов у ~нуль по CP (+0.6%). SMB — ~12% GMV, найприбутковіший сегмент (CP margin ~13%). Mid-market у 2026 реклесифіковано в ENT/SMB (≈0). Загальний CP уперше стабільно додатний (+€13.5k у серпні при GMV €649k). Багато «3P Stores» — це фактично крафт-пиво/напої (LOKO, HOP HEY, BEER MARKET, REMESLO BREWERY), а не продуктовий рітейл.</p>
    </div>
  </section>

  <h2 class="section" id="segments"><span class="bar"></span>Growth &amp; profitability by segment</h2>
  <p class="section-desc">Enterprise / Mid-market / SMB (business_segment_v2), {PERIOD}. Примітка: Mid-market у 2026 реклесифіковано в ENT/SMB, тож фактично сегментація зараз = ENT + SMB.</p>
  <div class="two">
    <div class="chartcard"><h3>GMV by segment (€ / month)</h3><p class="cap">Source: dbx fact_provider_monthly</p><canvas id="gmvChart" height="200"></canvas></div>
    <div class="chartcard"><h3>Contribution Profit by segment (€ / month)</h3><p class="cap">Below zero = loss-making</p><canvas id="cpChart" height="200"></canvas></div>
  </div>
  <div class="tablewrap"><table class="matrix"><thead><tr><th>Segment</th><th>GMV ({CURLBL})</th><th>Share</th><th>MoM</th><th>CP</th><th>CP margin</th><th>Orders</th><th>Eater fee/ord</th><th>EF %GMV</th><th>CPO</th><th>Camp Bolt %GMV</th><th>Camp ord%</th><th>Partners</th></tr></thead><tbody>{seg_rows}</tbody></table></div>

  <h2 class="section" id="commission"><span class="bar"></span>Commission — рівень, тренд, партнери та прогноз Q4</h2>
  <p class="section-desc">Джерело: <b>FC Stores Forecast (Oct26–Mar27)</b> — actual Jan–Jul (dbx), projection Aug–Sep, forecast Oct26–Marʼ27 (Optimistic). Групи: <b>TOP Brands</b> ({top_brands_list}), <b>ENT other</b> (решта Enterprise), <b>SMB</b>, <b>MM</b>.</p>
  <div class="grid kpis">
    <div class="kpi"><div class="n">{cm_jul_pct}</div><div class="l">Commission %GMV (Jul, факт) · Jan {cm_jan_pct}</div></div>
    <div class="kpi"><div class="n">€{cm_jul_aov}</div><div class="l">AOV (Jul, факт)</div></div>
    <div class="kpi base"><div class="n">{q4o_comm}</div><div class="l">Q4ʼ26 commission (Opt)</div></div>
    <div class="kpi"><div class="n">{q4o_pct}</div><div class="l">Q4ʼ26 commission %GMV</div></div>
    <div class="kpi"><div class="n">€{q4o_aov}</div><div class="l">Q4ʼ26 AOV (Opt)</div></div>
  </div>
  <div class="callout" style="border-left-color:var(--warn)"><h3>Головне про комісію</h3><p>Блендована ставка падає з <b>~14.5% (січ) до ~9% (Q4 прогноз)</b> — TOP Brands (VARUS/LOKO/ATB/Fora ~3–6%, grocery) швидко масштабуються і розмивають високу ставку напійного ENT other (~16%). SMB тримає ~22%, MM ~18% (від GMV; від AOV відповідно вище: Total ~13% зараз, TOP ~5.5%, ENT other ~17%, SMB ~27%). Абсолютна комісія при цьому росте: Q4ʼ26 <b>{q4o_comm}</b> (Opt) vs {q4p_comm} (Pess).</p></div>
  <div class="two">
    <div class="chartcard"><h3>Commission %GMV — по групах</h3><p class="cap">Комісія від GMV. Jan26–Marʼ27 · actual→forecast (Optimistic)</p><canvas id="commGrpPct" height="220"></canvas></div>
    <div class="chartcard"><h3>Commission %AOV — по групах</h3><p class="cap">Комісія від AOV (ціни мерчанта, без eater fees). Jan26–Marʼ27 (Optimistic)</p><canvas id="commGrpAov" height="220"></canvas></div>
  </div>
  <div class="chartcard"><h3>Commission € — по групах (stacked)</h3><p class="cap">Optimistic · Jan26–Marʼ27</p><canvas id="commGrpEur" height="200"></canvas></div>
  <div class="chartcard"><h3>AOV — по групах (€)</h3><p class="cap">Total / TOP Brands / ENT other</p><canvas id="commAov" height="150"></canvas></div>
  <h3 style="margin:22px 0 4px">Commission %GMV, AOV, € — помісячно (Jan26–Marʼ27, Optimistic)</h3>
  <div class="tablewrap"><table class="matrix"><thead><tr><th>Метрика</th>{comm_month_headers}</tr></thead><tbody>{comm_grp_rows}</tbody></table></div>
  <p class="cap">Actual: Jan–Jul · Projection: Aug–Sep · Forecast: Oct26–Marʼ27.</p>

  <h3 style="margin:24px 0 4px">Прогноз Q4ʼ26 (Oct–Dec) по групах — Optimistic vs Pessimistic</h3>
  <div class="tablewrap"><table class="matrix"><thead><tr><th>Група</th><th>Comm € (Opt)</th><th>%GMV</th><th>AOV</th><th>GMV (Opt)</th><th>Comm € (Pess)</th><th>%GMV (Pess)</th></tr></thead><tbody>{q4_rows}</tbody></table></div>

  <h3 style="margin:24px 0 4px">TOP Brands — факт (Jul) → прогноз Q4ʼ26</h3>
  <div class="tablewrap"><table class="matrix"><thead><tr><th>Brand</th><th>Comm Jul</th><th>%GMV Jul</th><th>Comm Q4ʼ26</th><th>%GMV Q4</th><th>Locations Q4</th><th>Статус</th></tr></thead><tbody>{comm_tbq_rows}</tbody></table></div>
  <div class="callout" style="border-left-color:var(--accent)"><h3>TOP Brands у Q4 — драйвери</h3><p>Головний приріст комісії дають <b>ATB</b> (650 локацій, ~€24k, 4%), <b>Fora</b> (250, ~€22k, 6%) та <b>Rukavichka</b> (76, ~€13k, 6.8% — з майже нуля). <b>VARUS</b> лишається №1 (~€38k), але ставка низька 5.5%. Нові логотипи: <b>Auchan</b> (~€7k, 9%) і <b>Біле та Сухе</b> (~€5k, 15%). Разом TOP Brands у Q4 ≈ €117k комісії при ставці ~5.3%.</p></div>

  <h3 style="margin:24px 0 4px">ENT other — партнери за комісією (Jul, факт)</h3>
  <p class="section-desc">Напійний/спеціалізований Enterprise-рітейл (без TOP Brands) — високий %GMV. Топ-15.</p>
  <div class="tablewrap"><table class="matrix"><thead><tr><th>Partner</th><th>Segment</th><th>Commission</th><th>%GMV</th><th>AOV</th></tr></thead><tbody>{comm_oth_rows}</tbody></table></div>

  <h2 class="section" id="cities"><span class="bar"></span>City ranking — фінанс &amp; опс</h2>
  <p class="section-desc">Топ-5 міст (Kyiv, Dnipro, Lviv, Odesa, Kharkiv) = ~73% GMV; Kyiv сам ~35%. Зелений рядок — CP margin ≥ 5%, червоний — збиткове місто.</p>
  <div class="chartcard"><h3>GMV &amp; Contribution Profit — top 12 cities (Jun 2026)</h3><p class="cap">Source: dbx fact_provider_monthly</p><canvas id="cityChart" height="140"></canvas></div>
  <div class="tablewrap"><table class="matrix"><thead><tr><th>City</th><th>GMV</th><th>Share</th><th>MoM</th><th>CP</th><th>CP margin</th><th>Orders</th><th>AOV</th><th>Failed</th><th>Late</th></tr></thead><tbody>{city_rows}</tbody></table></div>

  <h2 class="section" id="econ"><span class="bar"></span>Eater fees, CPO &amp; campaigns — по містах</h2>
  <p class="section-desc">Eater fees = виручка з комісій їдока (service + small-order + delivery fee). CPO = courier cost / order. Campaign spend Bolt/Provider — інвойсовані витрати на кампанії; Camp ord% — частка замовлень із кампанією. Червень 2026.</p>
  <div class="tablewrap"><table class="matrix"><thead><tr><th>City</th><th>Orders</th><th>Eater fees</th><th>EF / order</th><th>EF %GMV</th><th>CPO</th><th>Camp spend Bolt</th><th>Camp spend Prov.</th><th>Camp discount</th><th>Camp Bolt %GMV</th><th>Camp ord%</th></tr></thead><tbody>{city_econ_rows}</tbody></table></div>

  <h2 class="section" id="deepdive"><span class="bar"></span>City deep-dive — які партнери формують місто</h2>
  <p class="section-desc">Топ-15 міст: спліт по сегментах і топ-партнери з динамікою MoM та CP.</p>
  {city_cards}

  <h2 class="section" id="partners"><span class="bar"></span>Partner leaderboard (top-{len(DATA['brands'])} by GMV)</h2>
  <p class="section-desc">VARUS — №1 за GMV (~€233k, +49% MoM), і найбільший тягар по CP (−€7.2k, хоча маржа покращилась із −8.3% до −3.1%).</p>
  <div class="tablewrap"><table class="matrix"><thead><tr><th>Partner</th><th>Segment</th><th>Main city</th><th>Cities</th><th>GMV</th><th>MoM</th><th>CP</th><th>CP margin</th><th>Eater fee/ord</th><th>CPO</th><th>Camp ord%</th></tr></thead><tbody>{brand_rows}</tbody></table></div>

  <h2 class="section" id="diagnosis"><span class="bar"></span>Чому збиткові &amp; що робити — VARUS, KOPIYKA, SANTIM, LOKO</h2>
  <p class="section-desc">P&amp;L на замовлення ({DIAG_MONTH_UA} 2026). CP/зам. = Contribution Profit на одне доставлене замовлення. Own% — частка власної доставки партнера (при 100% Bolt не несе курʼєрських витрат). «Inc» = demand + supply incentives; «Camp» = campaign spend Bolt.</p>
  <div class="tablewrap"><table class="matrix"><thead><tr><th>Partner</th><th>AOV</th><th>Own%</th><th>Comm %GMV</th><th>Comm/ord</th><th>Eater fee/ord</th><th>CPO</th><th>Inc/ord</th><th>Refund/ord</th><th>Camp/ord</th><th>Camp ord%</th><th>CP/ord</th><th>CP margin</th></tr></thead><tbody>{diag_rows}</tbody></table></div>
  <div class="callout" style="border-left-color:var(--warn)"><h3>Суть ({DIAG_MONTH_UA} 2026)</h3><p>{diag_summary}</p></div>

  <h3 style="margin:22px 0 4px">Де найбільший мінус CP (по містах, {DIAG_MONTH_UA} 2026)</h3>
  <p class="section-desc">Місто з найбільшим тягарем CP для кожного партнера — куди бити першими.</p>
  <div class="tablewrap"><table class="matrix"><thead><tr><th>Partner</th><th>Місто #1 за втратами</th><th>Orders</th><th>CP</th><th>Margin</th><th>CPO</th><th>Camp ord%</th><th>Refund/ord</th><th>Коментар</th></tr></thead><tbody>{cityworst_rows}</tbody></table></div>

  <h3 style="margin:26px 0 4px">Симулятор прибутковості</h3>
  <p class="section-desc">Потягни повзунки: <b>+комісія</b> (у процентних пунктах до GMV) і <b>−промо</b> (скорочення Bolt-фінансованих знижок = campaign spend Bolt + demand incentives). Таблиця перерахує CP і маржу по кожному партнеру. Формула: новий CP = поточний CP + Δкомісія%·GMV + скорочення%·(Bolt промо).</p>
  <div class="chartcard">
    <div style="display:flex;flex-wrap:wrap;gap:28px;align-items:center;margin-bottom:6px">
      <label style="font-size:14px">+ Комісія: <b><span id="commVal">+2.0</span> pp</b><br><input type="range" id="commSlider" min="0" max="6" step="0.5" value="2" style="width:240px"></label>
      <label style="font-size:14px">− Промо (Bolt): <b><span id="promoVal">30</span>%</b><br><input type="range" id="promoSlider" min="0" max="100" step="5" value="30" style="width:240px"></label>
      <div id="simTotal" style="font-size:14px;color:var(--soft)"></div>
    </div>
    <table class="matrix"><thead><tr><th>Partner</th><th>GMV</th><th>Комісія зараз</th><th>CP зараз</th><th>Margin зараз</th><th>→ CP новий</th><th>→ Margin новий</th><th>Статус</th></tr></thead><tbody id="simBody"></tbody></table>
    <p class="cap" style="margin-top:8px">Спрощена модель (ceteris paribus): не враховує вплив на обсяг замовлень від зміни знижок/комісії. Bolt промо = campaign spend Bolt + demand incentives ({DIAG_MONTH_UA} 2026).</p>
  </div>

  <h2 class="section" id="movers"><span class="bar"></span>Movers — хто зростає, хто падає</h2>
  <p class="section-desc">Партнери з GMV &gt; €3k у травні, за динамікою MoM.</p>
  <div class="two">
    <div><div class="chartcard" style="padding:0"><table class="matrix" style="margin:0;border:none"><thead><tr><th>Growing partner</th><th>Main city</th><th>GMV</th><th>MoM</th></tr></thead><tbody>{mover_rows(growing)}</tbody></table></div></div>
    <div><div class="chartcard" style="padding:0"><table class="matrix" style="margin:0;border:none"><thead><tr><th>Declining partner</th><th>Main city</th><th>GMV</th><th>MoM</th></tr></thead><tbody>{mover_rows(declining)}</tbody></table></div></div>
  </div>

  <footer>
    <p>CP = Contribution Profit (invoiced). Сегмент = business_segment_v2 (dim_provider_v2). MoM = серпень vs липень 2026. Ставки failed/late зважені за замовленнями. Період даних: {PERIOD}. Міста з нульовим GMV у поточному місяці виключені.</p>
    <p>Джерело даних: Databricks <code>ng_delivery_spark.fact_provider_monthly</code> + <code>dim_provider_v2</code>, вертикаль <code>store_3p_ent</code> + <code>store_3p_mm_smb</code>, country_code = 'ua'. Згенеровано з <code>threep_data.json</code>.</p>
  </footer>
</div>
<script>
const C={{ent:'#2563eb',mm:'#d1a53f',smb:'#15a34a'}};
const seriesColor=['#2563eb','#d1a53f','#15a34a'];
const gmv={{labels:{chart_labels},datasets:[
  {{label:'Enterprise',data:{json.dumps(gmv_ds['Enterprise'])},borderColor:C.ent,backgroundColor:C.ent,tension:.3}},
  {{label:'Mid-market',data:{json.dumps(gmv_ds['Mid-market'])},borderColor:C.mm,backgroundColor:C.mm,tension:.3}},
  {{label:'SMB',data:{json.dumps(gmv_ds['SMB'])},borderColor:C.smb,backgroundColor:C.smb,tension:.3}}]}};
const cp={{labels:{chart_labels},datasets:[
  {{label:'Enterprise',data:{json.dumps(cp_ds['Enterprise'])},backgroundColor:C.ent}},
  {{label:'Mid-market',data:{json.dumps(cp_ds['Mid-market'])},backgroundColor:C.mm}},
  {{label:'SMB',data:{json.dumps(cp_ds['SMB'])},backgroundColor:C.smb}}]}};
const eurTick=v=>'€'+(Math.abs(v)>=1000?(v/1000).toFixed(0)+'k':v);
new Chart(document.getElementById('gmvChart'),{{type:'line',data:gmv,options:{{plugins:{{legend:{{position:'bottom'}}}},scales:{{y:{{ticks:{{callback:eurTick}}}}}}}}}});
new Chart(document.getElementById('cpChart'),{{type:'bar',data:cp,options:{{plugins:{{legend:{{position:'bottom'}}}},scales:{{y:{{ticks:{{callback:eurTick}}}}}}}}}});
new Chart(document.getElementById('cityChart'),{{type:'bar',data:{{labels:{city_bar_labels},datasets:[
  {{label:'GMV',data:{city_bar_gmv},backgroundColor:'#2563eb'}},
  {{label:'Contribution Profit',data:{city_bar_cp},backgroundColor:'#15a34a'}}]}},
  options:{{plugins:{{legend:{{position:'bottom'}}}},scales:{{y:{{ticks:{{callback:eurTick}}}}}}}}}});

// ── Profitability simulator ──
const SIM={json.dumps(SIM, ensure_ascii=False)};
const simOrder=['VARUS','LOKO','KOPIYKA','RUKAVYCHKA','KOPIYKA MINI','TAISTRA','SANTIM'];
const fmtE=v=>{{const n=Math.abs(v);const s=n>=1000?'€'+(v/1000).toFixed(1)+'k':'€'+Math.round(v);return v<0?'−'+(n>=1000?(n/1000).toFixed(1)+'k':Math.round(n)):s;}};
function renderSim(){{
  const cpp=parseFloat(document.getElementById('commSlider').value);
  const pc=parseFloat(document.getElementById('promoSlider').value);
  document.getElementById('commVal').textContent='+'+cpp.toFixed(1);
  document.getElementById('promoVal').textContent=pc.toFixed(0);
  let body='',totOld=0,totNew=0,totGmv=0;
  simOrder.forEach(k=>{{
    const d=SIM[k]; if(!d)return;
    const boltPromo=(d.camp_bolt||0)+(d.demand_inc||0);
    const newCp=d.cp + cpp/100*d.gmv + pc/100*boltPromo;
    const oldM=d.cp/d.gmv*100, newM=newCp/d.gmv*100;
    totOld+=d.cp; totNew+=newCp; totGmv+=d.gmv;
    const status=newCp>=0?'<span class="up">прибуткове</span>':'<span class="down">ще збиткове</span>';
    const nCls=newCp>=0?'up':'down';
    body+=`<tr><td class="axis">${{k}}</td><td>${{fmtE(d.gmv)}}</td><td>${{d.comm_pct.toFixed(1)}}%</td>`
      +`<td><span class="down">${{fmtE(d.cp)}}</span></td><td><span class="down">${{oldM.toFixed(1)}}%</span></td>`
      +`<td><span class="${{nCls}}">${{fmtE(newCp)}}</span></td><td><span class="${{nCls}}">${{newM.toFixed(1)}}%</span></td><td>${{status}}</td></tr>`;
  }});
  document.getElementById('simBody').innerHTML=body;
  const om=totOld/totGmv*100, nm=totNew/totGmv*100;
  document.getElementById('simTotal').innerHTML=`Разом (7 партнерів): CP <span class="down">${{fmtE(totOld)}}</span> (${{om.toFixed(1)}}%) → <span class="${{totNew>=0?'up':'down'}}">${{fmtE(totNew)}}</span> (${{nm.toFixed(1)}}%)`;
}}
document.getElementById('commSlider').addEventListener('input',renderSim);
document.getElementById('promoSlider').addEventListener('input',renderSim);
renderSim();

// ── Commission tab ──
const COMM={json.dumps(COMM_JS, ensure_ascii=False)};
const cml=COMM.months;
const grpColor={{TOTAL:'#13203a',TOP:'#2563eb',ENT_OTH:'#0e7faa',SMB:'#15a34a',MM:'#d1a53f'}};
const glbl=COMM.grp_label;
const gord=['TOTAL','TOP','ENT_OTH','SMB','MM'];
new Chart(document.getElementById('commGrpPct'),{{type:'line',data:{{labels:cml,datasets:gord.map(g=>({{label:glbl[g],data:COMM.opt[g].map(r=>r.comm_pct),borderColor:grpColor[g],backgroundColor:grpColor[g],tension:.3,borderWidth:g=='TOTAL'?2.5:1.5,spanGaps:true}}))}},options:{{plugins:{{legend:{{position:'bottom'}}}},scales:{{y:{{ticks:{{callback:v=>v+'%'}}}}}}}}}});
new Chart(document.getElementById('commGrpAov'),{{type:'line',data:{{labels:cml,datasets:gord.map(g=>({{label:glbl[g],data:COMM.opt[g].map(r=>r.comm_aov),borderColor:grpColor[g],backgroundColor:grpColor[g],tension:.3,borderWidth:g=='TOTAL'?2.5:1.5,spanGaps:true}}))}},options:{{plugins:{{legend:{{position:'bottom'}}}},scales:{{y:{{ticks:{{callback:v=>v+'%'}}}}}}}}}});
new Chart(document.getElementById('commGrpEur'),{{type:'bar',data:{{labels:cml,datasets:['TOP','ENT_OTH','SMB','MM'].map(g=>({{label:glbl[g],data:COMM.opt[g].map(r=>r.comm),backgroundColor:grpColor[g]}}))}},options:{{plugins:{{legend:{{position:'bottom'}}}},scales:{{x:{{stacked:true}},y:{{stacked:true,ticks:{{callback:eurTick}}}}}}}}}});
new Chart(document.getElementById('commAov'),{{type:'line',data:{{labels:cml,datasets:[
  {{label:'Total',data:COMM.opt.TOTAL.map(r=>r.aov),borderColor:'#d1493f',backgroundColor:'#d1493f',tension:.3}},
  {{label:'TOP Brands',data:COMM.opt.TOP.map(r=>r.aov),borderColor:'#2563eb',backgroundColor:'#2563eb',tension:.3}},
  {{label:'ENT other',data:COMM.opt.ENT_OTH.map(r=>r.aov),borderColor:'#0e7faa',backgroundColor:'#0e7faa',tension:.3}}]}},options:{{plugins:{{legend:{{position:'bottom'}}}},scales:{{y:{{ticks:{{callback:v=>'€'+v}}}}}}}}}});
</script>
</body>
</html>
"""

(HERE / "index.html").write_text(HTML, encoding="utf-8")
print(f"Wrote index.html ({len(HTML):,} bytes) · {len(DATA['cities'])} cities · {jun['brands']} partners")
