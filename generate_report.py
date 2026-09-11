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

# ── Profitability diagnosis (July 2026, per-order P&L for 7 focus brands) ────────
# Значення з dbx fact_provider_monthly (per delivered order, липень 2026).
DIAG = [
    {"brand": "VARUS", "aov": 16.06, "own": 0, "comm_pct": 5.7, "comm": 0.92, "ef": 1.91, "cpo": 2.38,
     "inc": 1.14, "refund": 0.31, "camp": 0.67, "camp_ord": 84, "cpo_ord": -0.50, "margin": -3.1,
     "why": "Покращення до -3.1% (з -8.3% у червні). Головне зараз - CPO €2.38 (зросла) + надважке промо (84% замовлень, incentives €1.14/зам). Комісія 5.7%, refunds під контролем (€0.31)."},
    {"brand": "LOKO", "aov": 14.71, "own": 100, "comm_pct": 3.2, "comm": 0.46, "ef": 0.00, "cpo": 0.00,
     "inc": 0.70, "refund": -0.03, "camp": 0.70, "camp_ord": 10, "cpo_ord": -0.26, "margin": -1.8,
     "why": "Власна доставка (CPO=0), майже беззбитково (-1.8%). Комісія 3.2% (€0.46/зам) низька, а Bolt-промо зросло (incentives €0.70/зам). Важелі - комісія + контроль промо."},
    {"brand": "KOPIYKA", "aov": 12.14, "own": 2, "comm_pct": 7.5, "comm": 0.91, "ef": 1.50, "cpo": 1.87,
     "inc": 1.10, "refund": 0.30, "camp": 0.73, "camp_ord": 83, "cpo_ord": -0.24, "margin": -2.0,
     "why": "Майже беззбитково (-2.0%). Тисне надважке промо (83% замовлень, incentives €1.10 + campaign €0.73/зам) + CPO €1.87 при низькому AOV €12.1."},
    {"brand": "RUKAVYCHKA", "aov": 13.70, "own": 10, "comm_pct": 6.2, "comm": 0.85, "ef": 1.76, "cpo": 2.26,
     "inc": 1.40, "refund": 0.54, "camp": 0.89, "camp_ord": 16, "cpo_ord": -0.42, "margin": -3.0,
     "why": "CPO €2.26 + високі incentives €1.40/зам - головні драйвери; комісія 6.2%. Промо за к-стю замовлень низьке (16%), але дороге per-order."},
    {"brand": "KOPIYKA MINI", "aov": 12.24, "own": 1, "comm_pct": 7.1, "comm": 0.87, "ef": 1.60, "cpo": 2.16,
     "inc": 1.37, "refund": -0.28, "camp": 0.81, "camp_ord": 81, "cpo_ord": -0.00, "margin": -0.0,
     "why": "Вийшла в ~нуль (0.0%) завдяки refund-кредиту. Структурно тримається надважким промо (81% замовлень) + CPO €2.16 при AOV €12.2. Миколаїв CPO €3.5, -11.9%."},
    {"brand": "TAISTRA", "aov": 13.29, "own": 3, "comm_pct": 8.7, "comm": 1.15, "ef": 1.31, "cpo": 1.81,
     "inc": 0.84, "refund": -0.20, "camp": 0.33, "camp_ord": 11, "cpo_ord": 0.08, "margin": 0.6,
     "why": "Уже прибуткова (+0.6%!). Добра комісія (8.7%), низьке промо (11% замовлень), refunds ~0, нижча CPO €1.81. Модель для масштабування."},
    {"brand": "SANTIM", "aov": 15.44, "own": 2, "comm_pct": 8.2, "comm": 1.26, "ef": 1.80, "cpo": 2.06,
     "inc": 1.21, "refund": 1.25, "camp": 0.93, "camp_ord": 82, "cpo_ord": -0.16, "margin": -1.0,
     "why": "Відновлення до -1.0% (з -7.2% у липні - сплеск refunds минув). Тисне надважке промо (82% замовлень, incentives €1.21 + campaign €0.93). Комісія висока (8.2%)."},
]
diag_rows = ""
for d in DIAG:
    diag_rows += (
        f'<tr class="neg"><td class="axis">{d["brand"]}</td><td>€{d["aov"]:.1f}</td>'
        f'<td>{d["own"]}%</td><td>{d["comm_pct"]:.1f}%</td><td>€{d["comm"]:.2f}</td>'
        f'<td>€{d["ef"]:.2f}</td><td>€{d["cpo"]:.2f}</td><td>€{d["inc"]:.2f}</td>'
        f'<td>€{d["refund"]:.2f}</td><td>€{d["camp"]:.2f}</td><td>{d["camp_ord"]}%</td>'
        f'<td><span class="down">€{d["cpo_ord"]:.2f}</span></td><td><span class="down">{d["margin"]:.1f}%</span></td></tr>'
    )

# Де найбільший мінус CP (місто з найбільшим тягарем CP у липні 2026)
CITYWORST = [
    ("VARUS", "Dnipro", 4033, -2667, -4.3, 2.18, 87, 0.34, "Далі Zaporizhia (-€1.2k, -9.2%, CPO €2.89). Промо 87% - головний важіль."),
    ("LOKO", "Kyiv", 2000, -534, -1.8, 0.0, 7, -0.02, "Збиток рівномірний (~-2% скрізь) - системна проблема комісії 3.2%."),
    ("KOPIYKA", "Odesa", 2054, -484, -1.9, 1.86, 83, 0.30, "Майже весь обсяг в Одесі; промо 83%."),
    ("RUKAVYCHKA", "Lviv", 742, -285, -2.8, 2.25, 16, 0.50, "Практично лише Львів. Ivano-Frankivsk - CPO €3.7, деприоритезувати."),
    ("SANTIM", "Odesa", 454, -74, -1.0, 2.06, 82, 1.25, "Єдине місто. Refunds повернулись до норми vs липневий сплеск."),
    ("KOPIYKA MINI", "Mykolaiv", 62, -92, -11.9, 3.48, 82, 0.42, "Odesa вже +1.9%. Миколаїв - CPO €3.5, пауза/own-delivery."),
    ("TAISTRA", "Ternopil", 38, -11, -2.2, 1.72, 66, 0.01, "Бренд загалом у плюсі; Хмельницький +0.9%."),
]
cityworst_rows = "".join(
    f'<tr class="neg"><td class="axis">{b}</td><td>{c}</td><td>{o:,}</td>'
    f'<td><span class="down">{eur(cp)}</span></td><td><span class="down">{m:.1f}%</span></td>'
    f'<td>€{cpo:.2f}</td><td>{cs}%</td><td>€{rf:.2f}</td><td style="text-align:left;font-size:12px">{note}</td></tr>'
    for (b, c, o, cp, m, cpo, cs, rf, note) in CITYWORST
)

RECO = {
    "VARUS": ["Промо: 84% замовлень з кампанією (incentives €1.14/зам) — головний важіль. Зрізати глибину/охоплення, partner cost-share, таргет ELC/churn.",
              "Комісія 5.7% → 8–10% (партнер №1 за GMV, +49% MoM — є переговорна сила).",
              "CPO €2.38 (зросла): батчинг у Дніпрі та Запоріжжі (CPO €2.9), MOV↑, звузити зони.",
              "Першими бити: Dnipro (−€2.7k) та Zaporizhia (−9.2%). Refunds уже під контролем (€0.31)."],
    "LOKO": ["Комісія 3.2% → 6–8% — головний важіль (own-delivery, Bolt не несе курʼєрки).",
             "Промо зросло (incentives €0.70/зам при лише 10% замовлень) — переглянути ефективність.",
             "Майже беззбитково (−1.8%) — невеликий крок по комісії виводить у плюс.",
             "Own-delivery → eater fees=0: розглянути service fee як додатковий дохід."],
    "KOPIYKA": ["Промо — головний важіль: 83% замовлень, incentives €1.10 + campaign €0.73/зам. Partner cost-share + таргет.",
                "AOV €12.1 (низький): MOV↑, бандли — розмити CPO €1.87.",
                "Фокус — Одеса (весь обсяг тут)."],
    "RUKAVYCHKA": ["CPO €2.26 + incentives €1.40/зам — головні драйвери: батчинг + перегляд промо-глибини у Львові.",
                   "Комісія 6.2% → 8%.",
                   "Деприоритезувати дрібні міста з CPO €3+ (Ivano-Frankivsk €3.7)."],
    "KOPIYKA MINI": ["Уже в ~нулі — закріпити: зрізати надважке промо (81% замовлень) + MOV↑ (AOV €12.2).",
                     "Mykolaiv (CPO €3.5, −11.9%) — пауза або лише own-delivery.",
                     "Комісія 7.1% → 8%."],
    "TAISTRA": ["Уже прибуткова (+0.6%) — еталон: низьке промо (11%), добра комісія (8.7%), refunds ~0, CPO €1.81.",
                "Масштабувати цю модель на інші бренди/міста.",
                "Тримати промо-дисципліну."],
    "SANTIM": ["Промо — головний важіль: 82% замовлень, incentives €1.21 + campaign €0.93/зам. Partner cost-share.",
               "Refunds повернулись до норми (€1.25 з €3.15) — тримати контроль.",
               "Комісія висока (8.2%) — проблема не в ній; фокус на промо + CPO €2.06."],
}
reco_cards = ""
for d in DIAG:
    lis = "".join(f"<li>{x}</li>" for x in RECO[d["brand"]])
    reco_cards += (
        f'<div class="callout" style="border-left-color:var(--accent)">'
        f'<h3>{d["brand"]} · CP {d["margin"]:.1f}%</h3>'
        f'<p style="margin-bottom:6px">{d["why"]}</p>'
        f'<ul style="margin:0;padding-left:18px;color:var(--soft);font-size:14px">{lis}</ul></div>'
    )

SIM = json.loads((HERE / "sim_data.json").read_text(encoding="utf-8")) if (HERE / "sim_data.json").exists() else {}

# ── Commission tab (Jan–Aug 2026) ───────────────────────────────────────────────
COMM = json.loads((HERE / "commission_data.json").read_text(encoding="utf-8"))
cmi = COMM["total"][-1]        # latest month (Aug)
cmi_prev = COMM["total"][-2]   # Jul
cm_first = COMM["total"][0]    # Jan
# Segment monthly commission %GMV table (ENT / SMB; MM reclassified ≈0)
def _pctcell(v):
    return "<td>–</td>" if v is None else f"<td>{v:.1f}%</td>"


comm_seg_rows = ""
for seg in ["Enterprise", "SMB"]:
    cells = "".join(_pctcell(r["comm_pct"]) for r in COMM["segment"][seg])
    comm_seg_rows += f'<tr><td class="axis">{seg} · comm %GMV</td>{cells}</tr>'
# total row
tot_cells = "".join(f'<td>{r["comm_pct"]:.1f}%</td>' for r in COMM["total"])
comm_seg_rows += f'<tr class="pos"><td class="axis">TOTAL · comm %GMV</td>{tot_cells}</tr>'
aov_cells = "".join(f'<td>€{r["aov"]:.1f}</td>' for r in COMM["total"])
comm_seg_rows += f'<tr><td class="axis">TOTAL · AOV</td>{aov_cells}</tr>'
comm_month_headers = "".join(f"<th>{m}</th>" for m in COMM["months"])

# Partner commission leaderboard (Aug)
comm_partner_rows = ""
for p in COMM["partners"]:
    mom = p.get("mom")
    comm_partner_rows += (
        f'<tr><td class="axis">{p["brand"]}</td><td>{p["seg"]}</td>'
        f'<td>{eur(p["comm"])}</td><td>{p["share"]:.1f}%</td><td>{p["comm_pct"]:.1f}%</td>'
        f'<td>€{p["aov"]:.1f}</td><td>{delta_span(mom)}</td></tr>'
    )

# New-merchant top-brand detail (Aug)
tb_rows = ""
for d in sorted(COMM["aug_topbrand"], key=lambda x: -x["comm"]):
    stat = "активний" if d["comm"] > 0 else "greenfield (0 нових)"
    tone = "pos" if d["comm"] > 0 else "neg"
    rate = f'{d["comm_pct"]:.1f}%' if d["gmv"] else "–"
    aovs = f'€{d["aov"]:.1f}' if d.get("aov") else "–"
    tb_rows += (
        f'<tr class="{tone}"><td class="axis">{d["brand"]}</td><td>{eur(d["comm"])}</td>'
        f'<td>{eur(d["gmv"])}</td><td>{d["providers"]}</td><td>{rate}</td><td>{aovs}</td>'
        f'<td style="text-align:left">{stat}</td></tr>'
    )
tgt = COMM["targets"]

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

  <h2 class="section" id="commission"><span class="bar"></span>Commission — рівень, тренд, партнери та нові мерчанти</h2>
  <p class="section-desc">Період: <b>січень–серпень 2026</b> (місячно), останній повний місяць — серпень. Total commission from GMV, AOV + розріз ENT / SMB / MM. Джерело: dbx <code>main.ng_delivery.fact_provider_monthly</code>.</p>
  <div class="grid kpis">
    <div class="kpi base"><div class="n">{eur(cmi['comm'])}</div><div class="l">Total commission (Aug)</div></div>
    <div class="kpi"><div class="n">{cmi['comm_pct']:.1f}%</div><div class="l">Commission %GMV (Jan {cm_first['comm_pct']:.1f}% → Aug)</div></div>
    <div class="kpi"><div class="n">€{cmi['aov']:.1f}</div><div class="l">AOV (Aug) · Jan €{cm_first['aov']:.1f}</div></div>
    <div class="kpi opt"><div class="n">{eur(tgt['new_top']['aug'] + tgt['new_other_ent']['aug'])}</div><div class="l">Commission нових мерчантів (Aug)</div></div>
    <div class="kpi"><div class="n">{cmi['orders']/1000:.1f}k</div><div class="l">Orders (Aug)</div></div>
  </div>
  <div class="callout" style="border-left-color:var(--warn)"><h3>Головне про рівень комісії</h3><p>Блендована ставка <b>падає з 14.6% (січ) до 11.1% (сер)</b> — не через зниження ставок, а через <b>міксшифт</b>: низькокомісійний grocery (VARUS 5.7%, LOKO 3.2%, KOPIYKA 7.5%) росте швидше за високомаржинальний напійний ритейл (REMESLO 28.5%, BEERLAND 23%, HOP HEY 19%). SMB тримає ~23% comm%GMV, Enterprise ~9–10%. Mid-market у 2026 фактично реклесифіковано в ENT/SMB (≈0).</p></div>
  <div class="two">
    <div class="chartcard"><h3>Commission %GMV — тренд по сегментах</h3><p class="cap">Total / Enterprise / SMB · Jan–Aug 2026</p><canvas id="commPctChart" height="210"></canvas></div>
    <div class="chartcard"><h3>Commission (€) &amp; AOV — total</h3><p class="cap">Стовпці — commission €, лінія — AOV €</p><canvas id="commEurChart" height="210"></canvas></div>
  </div>
  <h3 style="margin:22px 0 4px">Commission %GMV &amp; AOV — помісячно</h3>
  <div class="tablewrap"><table class="matrix"><thead><tr><th>Метрика</th>{comm_month_headers}</tr></thead><tbody>{comm_seg_rows}</tbody></table></div>

  <h3 style="margin:22px 0 4px">Які партнери формують комісію (Aug 2026)</h3>
  <p class="section-desc">Топ-15 за абсолютною комісією. VARUS — №1 за обсягом (18% усієї комісії), але низька ставка 5.7%; напійні бренди дають високий %GMV.</p>
  <div class="tablewrap"><table class="matrix"><thead><tr><th>Partner</th><th>Segment</th><th>Commission</th><th>Share</th><th>Comm %GMV</th><th>AOV</th><th>MoM</th></tr></thead><tbody>{comm_partner_rows}</tbody></table></div>

  <h3 style="margin:26px 0 4px">Нові мерчанти — цільові метрики (для квартальних цілей)</h3>
  <p class="section-desc">«Новий мерчант» = провайдер із першим доставленим замовленням у 2026 (first_delivered_order_ts ≥ 2026-01-01). Дві цільові метрики: <b>Commission of New merchants (Top Brands)</b> = LOKO, VARUS, RUKAVYCHKA, ATB, FORA, AUCHAN, Біле та Сухе; <b>Commission of New merchants (Other ENT)</b> = решта нових Enterprise.</p>
  <div class="grid kpis" style="grid-template-columns:repeat(4,1fr)">
    <div class="kpi opt"><div class="n">{eur(tgt['new_top']['aug'])}</div><div class="l">New · Top Brands — Aug/міс</div></div>
    <div class="kpi"><div class="n">{eur(tgt['new_top']['cum'])}</div><div class="l">New · Top Brands — Jan–Aug сума</div></div>
    <div class="kpi opt"><div class="n">{eur(tgt['new_other_ent']['aug'])}</div><div class="l">New · Other ENT — Aug/міс</div></div>
    <div class="kpi"><div class="n">{eur(tgt['new_other_ent']['cum'])}</div><div class="l">New · Other ENT — Jan–Aug сума</div></div>
  </div>
  <div class="chartcard"><h3>Commission нових мерчантів — помісячно (stacked)</h3><p class="cap">New · Top Brands / New · Other ENT / New · MM&amp;SMB · Jan–Aug 2026</p><canvas id="bucketChart" height="150"></canvas></div>
  <h3 style="margin:22px 0 4px">Нові мерчанти по Top Brands (Aug)</h3>
  <div class="tablewrap"><table class="matrix"><thead><tr><th>Top Brand</th><th>Commission</th><th>GMV</th><th>New providers</th><th>Comm %GMV</th><th>AOV</th><th>Статус</th></tr></thead><tbody>{tb_rows}</tbody></table></div>
  <div class="callout" style="border-left-color:var(--accent)"><h3>Що це означає для цілей</h3><p><b>Активні зараз:</b> VARUS (56 нових, €13.3k/міс, ставка 5.7%) і LOKO (118 нових, €2.5k/міс, ставка 3.2% — own-delivery) дають майже всю «New · Top Brands» комісію. <b>Greenfield:</b> ATB (845 провайдерів у базі) та FORA (278) присутні, але <b>0 нових активних у 2026</b> — величезний потенціал онбордингу/активації. <b>AUCHAN та «Біле та Сухе» ще відсутні</b> в UA 3P Stores — це нові логотипи для залучення. Low commission grocery (VARUS/LOKO) варто балансувати вищою ставкою або eater fees.</p></div>
  <div class="chartcard">
    <h3>Калькулятор цілей на квартал</h3>
    <p class="cap">Встав місячний таргет по кожній метриці — покаже приріст vs серпень і квартальну суму (×3).</p>
    <div style="display:flex;flex-wrap:wrap;gap:28px;align-items:flex-start;margin:6px 0">
      <label style="font-size:14px">New · Top Brands, €/міс<br><input type="number" id="tgtTop" value="{tgt['new_top']['aug']}" step="1000" style="width:160px;padding:6px;border:1px solid var(--line);border-radius:8px"></label>
      <label style="font-size:14px">New · Other ENT, €/міс<br><input type="number" id="tgtOther" value="{tgt['new_other_ent']['aug']}" step="1000" style="width:160px;padding:6px;border:1px solid var(--line);border-radius:8px"></label>
    </div>
    <table class="matrix"><thead><tr><th>Метрика</th><th>Aug (факт)</th><th>Ваш таргет/міс</th><th>Приріст vs Aug</th><th>Квартал (×3)</th></tr></thead><tbody id="tgtBody"></tbody></table>
  </div>

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
  <p class="section-desc">P&amp;L на замовлення (серпень 2026). CP/зам. = Contribution Profit на одне доставлене замовлення. Own% — частка власної доставки партнера (при 100% Bolt не несе курʼєрських витрат). «Inc» = demand + supply incentives; «Camp» = campaign spend Bolt.</p>
  <div class="tablewrap"><table class="matrix"><thead><tr><th>Partner</th><th>AOV</th><th>Own%</th><th>Comm %GMV</th><th>Comm/ord</th><th>Eater fee/ord</th><th>CPO</th><th>Inc/ord</th><th>Refund/ord</th><th>Camp/ord</th><th>Camp ord%</th><th>CP/ord</th><th>CP margin</th></tr></thead><tbody>{diag_rows}</tbody></table></div>
  <div class="callout" style="border-left-color:var(--warn)"><h3>Суть (серпень 2026)</h3><p>Більшість фокус-партнерів у серпні наблизились до беззбитковості (SANTIM відновився після липневого сплеску refunds, TAISTRA вже <b>+0.6%</b>, KOPIYKA MINI ~0%). Головний спільний тягар тепер — <b>надважке промо</b> (VARUS/KOPIYKA/SANTIM/KOPIYKA MINI: 80–84% замовлень з кампанією) + <b>CPO €1.8–2.4</b>. <b>LOKO</b> (own-delivery, CPO=0) стримується низькою комісією 3.2%.</p></div>

  <h3 style="margin:22px 0 4px">Де найбільший мінус CP (по містах, серпень 2026)</h3>
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
    <p class="cap" style="margin-top:8px">Спрощена модель (ceteris paribus): не враховує вплив на обсяг замовлень від зміни знижок/комісії. Bolt промо = campaign spend Bolt + demand incentives (серпень 2026).</p>
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
const COMM={json.dumps(COMM, ensure_ascii=False)};
const cml=COMM.months;
new Chart(document.getElementById('commPctChart'),{{type:'line',data:{{labels:cml,datasets:[
  {{label:'Total',data:COMM.total.map(r=>r.comm_pct),borderColor:'#13203a',backgroundColor:'#13203a',tension:.3,borderWidth:2}},
  {{label:'Enterprise',data:COMM.segment.Enterprise.map(r=>r.comm_pct),borderColor:'#2563eb',backgroundColor:'#2563eb',tension:.3}},
  {{label:'SMB',data:COMM.segment.SMB.map(r=>r.comm_pct),borderColor:'#15a34a',backgroundColor:'#15a34a',tension:.3}}]}},
  options:{{plugins:{{legend:{{position:'bottom'}}}},scales:{{y:{{ticks:{{callback:v=>v+'%'}}}}}}}}}});
new Chart(document.getElementById('commEurChart'),{{data:{{labels:cml,datasets:[
  {{type:'bar',label:'Commission €',data:COMM.total.map(r=>r.comm),backgroundColor:'#2563eb',yAxisID:'y'}},
  {{type:'line',label:'AOV €',data:COMM.total.map(r=>r.aov),borderColor:'#d1493f',backgroundColor:'#d1493f',tension:.3,yAxisID:'y1'}}]}},
  options:{{plugins:{{legend:{{position:'bottom'}}}},scales:{{
    y:{{position:'left',ticks:{{callback:eurTick}}}},
    y1:{{position:'right',grid:{{drawOnChartArea:false}},ticks:{{callback:v=>'€'+v}}}}}}}}}});
new Chart(document.getElementById('bucketChart'),{{type:'bar',data:{{labels:cml,datasets:[
  {{label:'New · Top Brands',data:COMM.buckets.map(r=>r.new_top),backgroundColor:'#2563eb'}},
  {{label:'New · Other ENT',data:COMM.buckets.map(r=>r.new_other_ent),backgroundColor:'#0e7faa'}},
  {{label:'New · MM&SMB',data:COMM.buckets.map(r=>r.new_mm_smb),backgroundColor:'#15a34a'}}]}},
  options:{{plugins:{{legend:{{position:'bottom'}}}},scales:{{x:{{stacked:true}},y:{{stacked:true,ticks:{{callback:eurTick}}}}}}}}}});
// target calculator
const augTop=COMM.targets.new_top.aug, augOther=COMM.targets.new_other_ent.aug;
function renderTgt(){{
  const t=parseFloat(document.getElementById('tgtTop').value)||0;
  const o=parseFloat(document.getElementById('tgtOther').value)||0;
  const row=(name,aug,val)=>{{
    const up=aug?((val/aug-1)*100):0; const cls=val>=aug?'up':'down';
    return `<tr><td class="axis">${{name}}</td><td>${{fmtE(aug)}}</td><td>${{fmtE(val)}}</td>`
      +`<td><span class="${{cls}}">${{(up>0?'+':'')+up.toFixed(0)}}%</span></td><td>${{fmtE(val*3)}}</td></tr>`;
  }};
  document.getElementById('tgtBody').innerHTML=row('New · Top Brands',augTop,t)+row('New · Other ENT',augOther,o)
    +`<tr class="pos"><td class="axis">Разом нові</td><td>${{fmtE(augTop+augOther)}}</td><td>${{fmtE(t+o)}}</td><td></td><td>${{fmtE((t+o)*3)}}</td></tr>`;
}}
document.getElementById('tgtTop').addEventListener('input',renderTgt);
document.getElementById('tgtOther').addEventListener('input',renderTgt);
renderTgt();
</script>
</body>
</html>
"""

(HERE / "index.html").write_text(HTML, encoding="utf-8")
print(f"Wrote index.html ({len(HTML):,} bytes) · {len(DATA['cities'])} cities · {jun['brands']} partners")
