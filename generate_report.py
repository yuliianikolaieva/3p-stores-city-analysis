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
MLABEL = {"apr": "Apr", "may": "May", "jun": "Jun"}
SEGS = ["Enterprise", "Mid-market", "SMB"]


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
jun, may = DATA["totals"]["jun"], DATA["totals"]["may"]
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
    g = seg_val(seg, "jun", "gmv")
    gm = seg_val(seg, "may", "gmv")
    cp = seg_val(seg, "jun", "cp")
    orders = seg_val(seg, "jun", "orders")
    brands = seg_val(seg, "jun", "brands")
    ef = seg_val(seg, "jun", "eater_fee")
    cc = seg_val(seg, "jun", "courier_costs")
    cb = seg_val(seg, "jun", "camp_bolt")
    co = seg_val(seg, "jun", "camp_orders")
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

# ── Per-city partner breakdown (top 6 cities) ───────────────────────────────────
city_cards = ""
for c in cities[:6]:
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

# ── Profitability diagnosis (June 2026, per-order P&L for 7 focus brands) ────────
# Значення з dbx fact_provider_monthly (per delivered order, червень 2026).
DIAG = [
    {"brand": "VARUS", "aov": 13.55, "own": 0, "comm_pct": 5.8, "comm": 0.79, "ef": 1.70, "cpo": 2.03,
     "inc": 0.51, "refund": 0.71, "camp": 0.00, "camp_ord": 59, "cpo_ord": -1.13, "margin": -8.3,
     "why": "Bolt-доставка: CPO €2.03/зам — найбільший драйвер. Eater fees €1.70 не покривають курʼєрку; комісія лише 5.8%; refunds €0.71/зам — дуже високі."},
    {"brand": "LOKO", "aov": 15.00, "own": 100, "comm_pct": 3.2, "comm": 0.47, "ef": 0.00, "cpo": 0.00,
     "inc": 0.47, "refund": 0.04, "camp": 0.41, "camp_ord": 5, "cpo_ord": -0.48, "margin": -3.2,
     "why": "Власна доставка (CPO=0) — справа НЕ в курʼєрці. Комісія лише 3.2% (€0.47/зам), а Bolt-знижки (demand €0.47 + campaign €0.41 ≈ €0.88/зам) з'їдають усю комісію."},
    {"brand": "KOPIYKA", "aov": 11.32, "own": 0, "comm_pct": 7.9, "comm": 0.89, "ef": 1.49, "cpo": 1.79,
     "inc": 0.95, "refund": 0.60, "camp": 0.36, "camp_ord": 54, "cpo_ord": -0.72, "margin": -6.4,
     "why": "Низький AOV €11.3 + промо (incentives+campaign ≈ €1.3/зам, 54% замовлень з кампанією) + CPO €1.79 + refunds €0.60."},
    {"brand": "RUKAVYCHKA", "aov": 13.80, "own": 5, "comm_pct": 5.9, "comm": 0.82, "ef": 1.71, "cpo": 1.97,
     "inc": 0.80, "refund": 0.25, "camp": 0.47, "camp_ord": 5, "cpo_ord": -0.57, "margin": -4.1,
     "why": "CPO €1.97 + низька комісія 5.9%. Промо низьке (5% замовлень), refunds помірні — головне курʼєрка + комісія."},
    {"brand": "KOPIYKA MINI", "aov": 11.43, "own": 5, "comm_pct": 7.3, "comm": 0.84, "ef": 1.48, "cpo": 1.98,
     "inc": 1.02, "refund": 0.32, "camp": 0.36, "camp_ord": 63, "cpo_ord": -0.80, "margin": -7.0,
     "why": "Як KOPIYKA, але гірше: низький AOV €11.4 + CPO €1.98 + важке промо (63% замовлень). У Миколаєві CPO €3.5, margin −10%."},
    {"brand": "TAISTRA", "aov": 14.04, "own": 0, "comm_pct": 8.5, "comm": 1.19, "ef": 1.47, "cpo": 2.14,
     "inc": 0.98, "refund": 0.08, "camp": 0.27, "camp_ord": 55, "cpo_ord": -0.39, "margin": -2.8,
     "why": "Найближче до нуля. Комісія вже добра (8.5%), refunds мінімальні. Проблема — CPO €2.14 + промо (55%). У Тернополі вже +1.6%."},
    {"brand": "SANTIM", "aov": 16.24, "own": 1, "comm_pct": 7.7, "comm": 1.25, "ef": 1.88, "cpo": 2.14,
     "inc": 1.63, "refund": 0.55, "camp": 0.82, "camp_ord": 67, "cpo_ord": -0.60, "margin": -3.7,
     "why": "GP додатній, але промо вбиває CP: incentives €1.63 + campaign €0.82/зам, 67% замовлень з кампанією. CPO €2.14."},
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

# Де найбільший мінус CP (місто з найбільшим тягарем CP у червні)
CITYWORST = [
    ("VARUS", "Dnipro", 2746, -3179, -8.5, 1.7, 48, 0.7, "Другий за втратами — Kyiv (−€2.4k). Найгірша маржа: Kryvyi Rih −14.8%, Zaporizhia −14.4%."),
    ("LOKO", "Kyiv", 1759, -958, -3.4, 0.0, 2, 0.1, "Збиток рівномірний (−3% скрізь) — це системна проблема комісії 3.2%, не локальна."),
    ("KOPIYKA", "Odesa", 1327, -936, -6.2, 1.8, 54, 0.6, "Присутня майже лише в Одесі — весь мінус тут."),
    ("RUKAVYCHKA", "Lviv", 805, -453, -4.1, 1.9, 6, 0.2, "Практично лише Львів. Ivano-Frankivsk — CPO €3.3, деприоритезувати."),
    ("KOPIYKA MINI", "Odesa", 417, -302, -6.6, 1.8, 61, 0.3, "Mykolaiv: −9.9% margin, CPO €3.5 — розглянути паузу/own-delivery."),
    ("TAISTRA", "Chernivtsi", 551, -306, -4.0, 2.2, 47, 0.1, "Ternopil уже +1.6% — модель робоча при нижчому промо."),
    ("SANTIM", "Odesa", 390, -235, -3.7, 2.1, 67, 0.6, "Єдине місто присутності."),
]
cityworst_rows = "".join(
    f'<tr class="neg"><td class="axis">{b}</td><td>{c}</td><td>{o:,}</td>'
    f'<td><span class="down">{eur(cp)}</span></td><td><span class="down">{m:.1f}%</span></td>'
    f'<td>€{cpo:.2f}</td><td>{cs}%</td><td>€{rf:.2f}</td><td style="text-align:left;font-size:12px">{note}</td></tr>'
    for (b, c, o, cp, m, cpo, cs, rf, note) in CITYWORST
)

RECO = {
    "VARUS": ["Комісія 5.8% → 8–10% (партнер №1, +40% MoM — є переговорна сила).",
              "CPO: MOV↑ / small-order fee, батчинг у Києві та Дніпрі (batched ~0%), звузити зони; own-delivery у щільних локаціях.",
              "Refunds €0.71/зам — операційний фікс (наявність SKU, збірка, заміни, disputes). Ціль −30%.",
              "Першими бити: Dnipro (−€3.2k) та Kyiv (−€2.4k); у Kryvyi Rih/Zaporizhia найгірша маржа."],
    "LOKO": ["Комісія 3.2% → 6–8% — головний важіль (own-delivery, Bolt не несе курʼєрки).",
             "Знижки demand €0.47 + campaign €0.41/зам перевищують усю комісію — зменшити Bolt cost-share, таргетувати промо.",
             "Own-delivery → eater fees=0: розглянути service fee на платформі як додатковий дохід.",
             "33 міста — промо-бюджет у топ-міста, зрізати хвіст."],
    "KOPIYKA": ["AOV €11.3 (найнижчий): MOV↑, бандли — розмити фіксовану курʼєрку.",
                "54% замовлень з кампанією — зрізати неефективні, cost-share на партнера, таргет ELC/churn.",
                "Refunds €0.60 — availability & picking.",
                "Фокус — Одеса (весь обсяг і мінус тут)."],
    "RUKAVYCHKA": ["Комісія 5.9% → 8% — головний важіль (промо вже низьке).",
                   "CPO €1.97: батчинг + MOV у Львові (основне місто).",
                   "Деприоритезувати дрібні міста з CPO €3+ (Ivano-Frankivsk)."],
    "KOPIYKA MINI": ["Ті ж важелі, що й KOPIYKA, але гостріше: MOV↑ (AOV €11.4) + зрізати промо (63% замовлень).",
                     "Mykolaiv (CPO €3.5, −10%) — пауза або лише own-delivery.",
                     "Комісія 7.3% → 8%."],
    "TAISTRA": ["Найближче до беззбитковості (−2.8%): достатньо трохи зрізати промо (55%) у Чернівцях.",
                "CPO €2.14 — батчинг/зони. Комісія 8.5% вже добра.",
                "Ternopil уже прибутковий — масштабувати цю модель."],
    "SANTIM": ["Промо — головний важіль: incentives €1.63 + campaign €0.82/зам (67% замовлень). Перейти на partner cost-share.",
               "GP додатній → прибрати надлишкове Bolt-фінансування = швидкий вихід у плюс.",
               "CPO при AOV €16.2 прийнятний — фокус на incentives, не на курʼєрці."],
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
    <p class="sub">Bolt Food · Україна · вертикаль <b>3P Stores</b> (store_3p_ent + store_3p_mm_smb). Всі ключові метрики delivery-репорту в розрізі міст і партнерів, з поділом на Enterprise / Mid-market / SMB. Останній повний місяць — <b>червень 2026</b>.</p>
    <div class="meta">
      <span class="pill">Period: Apr–Jun 2026</span>
      <span class="pill">Latest: Jun 2026</span>
      <span class="pill">Source: dbx fact_provider_monthly + dim_provider_v2</span>
      <span class="pill">{len(DATA['cities'])} active cities · {jun['brands']} partners</span>
    </div>
    {kpis}
  </header>

  <section id="overview">
    <div class="callout">
      <h3>Головний висновок: обсяг і маржа рознесені по сегментах</h3>
      <p>Enterprise робить <b>~84% GMV</b>, але працює біля/нижче нуля по CP (велика продуктова роздрібниця — VARUS, KOPIYKA — тягне маржу вниз). SMB — лише ~11% GMV, але це найприбутковіший сегмент (CP margin ~12%). Mid-market малий (~5% GMV), помірно прибутковий. Зростання GMV зараз іде переважно за рахунок збиткового Enterprise. Багато «3P Stores» — це фактично крафт-пиво/напої (LOKO, HOP HEY, BEER MARKET, REMESLO BREWERY), а не продуктовий рітейл.</p>
    </div>
  </section>

  <h2 class="section" id="segments"><span class="bar"></span>Growth &amp; profitability by segment</h2>
  <p class="section-desc">Enterprise / Mid-market / SMB (business_segment_v2), квітень–червень 2026.</p>
  <div class="two">
    <div class="chartcard"><h3>GMV by segment (€ / month)</h3><p class="cap">Source: dbx fact_provider_monthly</p><canvas id="gmvChart" height="200"></canvas></div>
    <div class="chartcard"><h3>Contribution Profit by segment (€ / month)</h3><p class="cap">Below zero = loss-making</p><canvas id="cpChart" height="200"></canvas></div>
  </div>
  <div class="tablewrap"><table class="matrix"><thead><tr><th>Segment</th><th>GMV (Jun)</th><th>Share</th><th>MoM</th><th>CP</th><th>CP margin</th><th>Orders</th><th>Eater fee/ord</th><th>EF %GMV</th><th>CPO</th><th>Camp Bolt %GMV</th><th>Camp ord%</th><th>Partners</th></tr></thead><tbody>{seg_rows}</tbody></table></div>

  <h2 class="section" id="cities"><span class="bar"></span>City ranking — фінанс &amp; опс</h2>
  <p class="section-desc">Топ-5 міст (Kyiv, Lviv, Dnipro, Kharkiv, Odesa) = ~77% GMV; Kyiv сам ~35%. Зелений рядок — CP margin ≥ 5%, червоний — збиткове місто.</p>
  <div class="chartcard"><h3>GMV &amp; Contribution Profit — top 12 cities (Jun 2026)</h3><p class="cap">Source: dbx fact_provider_monthly</p><canvas id="cityChart" height="140"></canvas></div>
  <div class="tablewrap"><table class="matrix"><thead><tr><th>City</th><th>GMV</th><th>Share</th><th>MoM</th><th>CP</th><th>CP margin</th><th>Orders</th><th>AOV</th><th>Failed</th><th>Late</th></tr></thead><tbody>{city_rows}</tbody></table></div>

  <h2 class="section" id="econ"><span class="bar"></span>Eater fees, CPO &amp; campaigns — по містах</h2>
  <p class="section-desc">Eater fees = виручка з комісій їдока (service + small-order + delivery fee). CPO = courier cost / order. Campaign spend Bolt/Provider — інвойсовані витрати на кампанії; Camp ord% — частка замовлень із кампанією. Червень 2026.</p>
  <div class="tablewrap"><table class="matrix"><thead><tr><th>City</th><th>Orders</th><th>Eater fees</th><th>EF / order</th><th>EF %GMV</th><th>CPO</th><th>Camp spend Bolt</th><th>Camp spend Prov.</th><th>Camp discount</th><th>Camp Bolt %GMV</th><th>Camp ord%</th></tr></thead><tbody>{city_econ_rows}</tbody></table></div>

  <h2 class="section" id="deepdive"><span class="bar"></span>City deep-dive — які партнери формують місто</h2>
  <p class="section-desc">Топ-6 міст: спліт по сегментах і топ-партнери з динамікою MoM та CP.</p>
  {city_cards}

  <h2 class="section" id="partners"><span class="bar"></span>Partner leaderboard (top-{len(DATA['brands'])} by GMV)</h2>
  <p class="section-desc">VARUS — №1 за GMV (~€101k, +40% MoM), але й найбільший тягар по CP (−€8.4k).</p>
  <div class="tablewrap"><table class="matrix"><thead><tr><th>Partner</th><th>Segment</th><th>Main city</th><th>Cities</th><th>GMV</th><th>MoM</th><th>CP</th><th>CP margin</th><th>Eater fee/ord</th><th>CPO</th><th>Camp ord%</th></tr></thead><tbody>{brand_rows}</tbody></table></div>

  <h2 class="section" id="diagnosis"><span class="bar"></span>Чому збиткові &amp; що робити — VARUS, KOPIYKA, SANTIM, LOKO</h2>
  <p class="section-desc">P&amp;L на замовлення (червень 2026). CP/зам. = Contribution Profit на одне доставлене замовлення. Own% — частка власної доставки партнера (при 100% Bolt не несе курʼєрських витрат). «Inc» = demand + supply incentives; «Camp» = campaign spend Bolt.</p>
  <div class="tablewrap"><table class="matrix"><thead><tr><th>Partner</th><th>AOV</th><th>Own%</th><th>Comm %GMV</th><th>Comm/ord</th><th>Eater fee/ord</th><th>CPO</th><th>Inc/ord</th><th>Refund/ord</th><th>Camp/ord</th><th>Camp ord%</th><th>CP/ord</th><th>CP margin</th></tr></thead><tbody>{diag_rows}</tbody></table></div>
  <div class="callout" style="border-left-color:var(--warn)"><h3>Суть у двох реченнях</h3><p><b>Bolt-доставка</b> (VARUS, KOPIYKA, KOPIYKA MINI, SANTIM, TAISTRA, RUKAVYCHKA) збиткова, бо <b>курʼєрка (CPO €1.8–2.1) + промо + refunds</b> перевищують комісію (5.8–8.5%) та eater fees. <b>LOKO</b> (власна доставка, CPO=0) збиткове з іншої причини — <b>комісія лише 3.2%</b>, а Bolt-фінансовані знижки з'їдають її повністю.</p></div>

  <h3 style="margin:22px 0 4px">Де найбільший мінус CP (по містах, червень 2026)</h3>
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
    <p class="cap" style="margin-top:8px">Спрощена модель (ceteris paribus): не враховує вплив на обсяг замовлень від зміни знижок/комісії. Bolt промо = campaign spend Bolt + demand incentives (червень 2026).</p>
  </div>

  <h2 class="section" id="movers"><span class="bar"></span>Movers — хто зростає, хто падає</h2>
  <p class="section-desc">Партнери з GMV &gt; €3k у травні, за динамікою MoM.</p>
  <div class="two">
    <div><div class="chartcard" style="padding:0"><table class="matrix" style="margin:0;border:none"><thead><tr><th>Growing partner</th><th>Main city</th><th>GMV</th><th>MoM</th></tr></thead><tbody>{mover_rows(growing)}</tbody></table></div></div>
    <div><div class="chartcard" style="padding:0"><table class="matrix" style="margin:0;border:none"><thead><tr><th>Declining partner</th><th>Main city</th><th>GMV</th><th>MoM</th></tr></thead><tbody>{mover_rows(declining)}</tbody></table></div></div>
  </div>

  <footer>
    <p>CP = Contribution Profit (invoiced). Сегмент = business_segment_v2 (dim_provider_v2). MoM = червень vs травень 2026. Ставки failed/late зважені за замовленнями. 3 міста з нульовим GMV у червні виключені.</p>
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
</script>
</body>
</html>
"""

(HERE / "index.html").write_text(HTML, encoding="utf-8")
print(f"Wrote index.html ({len(HTML):,} bytes) · {len(DATA['cities'])} cities · {jun['brands']} partners")
