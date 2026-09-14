#!/usr/bin/env python3
"""Refresh all dbx-driven data for the 3P Stores report.

Rebuilds (from Databricks main.ng_delivery):
  - threep_data.json        main dataset (cities / segments / brands / totals)
  - sim_data.json           per-brand aggregates for the profitability simulator
  - diag_data.json          per-order P&L diagnosis (numbers + templated narrative)
  - commission_actuals.json commission group series (actuals, TOP / ENT oth / SMB / MM)

The Q4 forecast (commission_forecast.json) is NOT touched here — it comes from the
FC Stores Forecast Excel and is refreshed manually when a new forecast is provided.

Connection via env vars (set as GitHub secrets in CI, or exported locally):
  DATABRICKS_HOST       default bolt-incentives.cloud.databricks.com
  DATABRICKS_HTTP_PATH  SQL warehouse / cluster HTTP path
  DATABRICKS_TOKEN      personal access token
"""
import os
import json
import warnings
from datetime import date
from pathlib import Path

warnings.filterwarnings("ignore")
import pandas as pd  # noqa: E402
from databricks import sql  # noqa: E402

HERE = Path(__file__).parent
HOST = os.environ.get("DATABRICKS_HOST", "bolt-incentives.cloud.databricks.com")
HTTP_PATH = os.environ["DATABRICKS_HTTP_PATH"]
TOKEN = os.environ["DATABRICKS_TOKEN"]
SCHEMA = os.environ.get("DBX_SCHEMA", "main.ng_delivery")
FACT = f"{SCHEMA}.fact_provider_monthly"
DIM = f"{SCHEMA}.dim_provider_v2"

MABBR = {1: "jan", 2: "feb", 3: "mar", 4: "apr", 5: "may", 6: "jun",
         7: "jul", 8: "aug", 9: "sep", 10: "oct", 11: "nov", 12: "dec"}
MLABEL = {"jan": "Jan", "feb": "Feb", "mar": "Mar", "apr": "Apr", "may": "May", "jun": "Jun",
          "jul": "Jul", "aug": "Aug", "sep": "Sep", "oct": "Oct", "nov": "Nov", "dec": "Dec"}
SEGS = ["Enterprise", "Mid-market", "SMB"]
FOCUS = ["LOKO", "KOPIYKA", "SANTIM", "VARUS", "RUKAVYCHKA", "TAISTRA", "KOPIYKA MINI"]
TOP_BRAND_SQL = (
    "UPPER(d.brand_name) LIKE '%VARUS%' OR UPPER(d.brand_name) LIKE '%LOKO%' "
    "OR UPPER(d.brand_name) LIKE '%RUKAV%' OR UPPER(d.brand_name) LIKE 'ATB%' "
    "OR UPPER(d.brand_name) LIKE '%АТБ%' OR UPPER(d.brand_name) LIKE '%FORA%' "
    "OR UPPER(d.brand_name) LIKE '%ФОРА%' OR UPPER(d.brand_name) LIKE '%AUCHAN%' "
    "OR UPPER(d.brand_name) LIKE '%АШАН%' OR d.brand_name LIKE '%Біле%' "
    "OR UPPER(d.brand_name) LIKE '%BILE%' OR UPPER(d.brand_name) LIKE '%SUKHE%'"
)
SEG_CASE = (
    "CASE WHEN d.business_segment_v2='Enterprise (AM Segment)' THEN 'Enterprise' "
    "WHEN d.business_segment_v2='Mid-market (AM Segment)' THEN 'Mid-market' "
    "WHEN d.business_segment_v2='SMB (AM Segment)' THEN 'SMB' ELSE 'Missing/Other' END"
)
VERT = "d.delivery_vertical IN ('store_3p_ent','store_3p_mm_smb')"


def q(sql_text):
    with sql.connect(server_hostname=HOST, http_path=HTTP_PATH, access_token=TOKEN) as conn:
        with conn.cursor() as cur:
            cur.execute(sql_text)
            cols = [c[0] for c in cur.description]
            return pd.DataFrame(cur.fetchall(), columns=cols)


def rnum(df, skip=("month", "city_name", "brand_name", "segment", "grp")):
    for c in df.columns:
        if c not in skip:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def month_list(latest_dt, n=8):
    """Return the last n complete months ending at latest_dt (list of 'YYYY-MM-01' and abbr)."""
    y, m = latest_dt.year, latest_dt.month
    seq = []
    for _ in range(n):
        seq.append(date(y, m, 1))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    seq.reverse()
    return seq


def latest_complete_month():
    today = date.today()
    fm = date(today.year, today.month, 1)  # first day of current (partial) month
    df = q(f"SELECT MAX(metric_timestamp_partition) mx FROM {FACT} "
           f"WHERE metric_timestamp_partition < DATE'{fm.isoformat()}'")
    v = df.iloc[0, 0]
    return v if isinstance(v, date) else pd.to_datetime(v).date()


def wavg(g, v, o="orders"):
    w = g[o]
    return (g[v] * w).sum() / w.sum() if w.sum() else None


# ────────────────────────────────────────────────────────────────────────────
def build_main(months, cur, prev):
    inmonths = ",".join(f"DATE'{d.isoformat()}'" for d in months)
    sqla = f"""
    WITH base AS (
      SELECT f.metric_timestamp_partition AS month, d.city_name, d.brand_name, {SEG_CASE} AS segment,
        f.total_gmv_before_discounts_eur gmv, f.total_contribution_profit_eur cp, f.total_gross_profit_eur gp,
        f.total_invoiced_provider_commission_eur commission, f.total_invoiced_demand_incentives_eur demand_inc,
        f.total_invoiced_supply_incentives_eur supply_inc, f.total_invoiced_refunds_eur refunds,
        f.total_invoiced_courier_costs_eur courier_costs, f.total_eater_fee_revenue_eur eater_fee,
        f.total_campaign_spend_bolt_eur camp_bolt, f.total_campaign_spend_provider_eur camp_prov,
        f.total_campaign_discount_eur camp_disc, f.campaign_orders_count camp_orders,
        f.delivered_orders_count orders, f.provider_churn_count churn,
        f.failed_order_rate_value fo_v, f.failed_order_rate_weight fo_w,
        f.late_delivery_order_rate_value late_v, f.late_delivery_order_rate_weight late_w,
        f.gmv_before_discounts_per_order_eur_value aov_v, f.gmv_before_discounts_per_order_eur_weight aov_w
      FROM {FACT} f JOIN {DIM} d ON f.provider_id=d.provider_id
      WHERE {VERT} AND d.country_code='ua' AND f.metric_timestamp_partition IN ({inmonths}))
    SELECT month, city_name, brand_name, segment,
      SUM(gmv) gmv, SUM(cp) cp, SUM(gp) gp, SUM(commission) commission,
      SUM(demand_inc) demand_inc, SUM(supply_inc) supply_inc, SUM(refunds) refunds,
      SUM(courier_costs) courier_costs, SUM(eater_fee) eater_fee,
      SUM(camp_bolt) camp_bolt, SUM(camp_prov) camp_prov, SUM(camp_disc) camp_disc, SUM(camp_orders) camp_orders,
      SUM(orders) orders, SUM(churn) churn,
      SUM(fo_v*fo_w)/NULLIF(SUM(fo_w),0) failed_rate, SUM(late_v*late_w)/NULLIF(SUM(late_w),0) late_rate,
      SUM(aov_v*aov_w)/NULLIF(SUM(aov_w),0) aov
    FROM base GROUP BY 1,2,3,4"""
    df = rnum(q(sqla))
    df["month"] = df["month"].astype(str)
    d2a = {d.isoformat(): MABBR[d.month] for d in months}
    df["m"] = df["month"].map(d2a)
    ALLM = [MABBR[d.month] for d in months]
    curm, prevm = MABBR[cur.month], MABBR[prev.month]
    SUM = ["gmv", "cp", "gp", "commission", "demand_inc", "supply_inc", "refunds", "courier_costs",
           "eater_fee", "camp_bolt", "camp_prov", "camp_disc", "camp_orders", "orders", "churn"]
    curdf = df[df.m == curm]
    prevdf = df[df.m == prevm]

    def cagg(s):
        d = {k: s[k].sum() for k in SUM}
        d.update({"failed_rate": wavg(s, "failed_rate"), "late_rate": wavg(s, "late_rate"),
                  "aov": wavg(s, "aov"), "brands": s.brand_name.nunique()})
        return pd.Series(d)

    cj = curdf.groupby("city_name").apply(cagg)
    cj["gmv_prev"] = prevdf.groupby("city_name").gmv.sum()
    cj = cj.sort_values("gmv", ascending=False).reset_index()
    segpiv = curdf.groupby(["city_name", "segment"]).agg(gmv=("gmv", "sum"), cp=("cp", "sum")).reset_index()

    def seg_for(c):
        s = segpiv[segpiv.city_name == c]
        return {r.segment: {"gmv": round(r.gmv), "cp": round(r.cp)} for r in s.itertuples()}

    bcj = curdf.groupby(["city_name", "brand_name", "segment"]).agg(
        gmv=("gmv", "sum"), cp=("cp", "sum"), orders=("orders", "sum"),
        eater_fee=("eater_fee", "sum"), courier_costs=("courier_costs", "sum"),
        camp_orders=("camp_orders", "sum")).reset_index()
    bcp = prevdf.groupby(["city_name", "brand_name"]).gmv.sum().rename("gmv_prev").reset_index()
    bc = bcj.merge(bcp, on=["city_name", "brand_name"], how="left")
    bc["pop"] = (bc.gmv / bc.gmv_prev - 1) * 100

    def topb(c, n=6):
        s = bc[bc.city_name == c].sort_values("gmv", ascending=False).head(n)
        out = []
        for r in s.itertuples():
            o = int(r.orders)
            out.append({"brand": r.brand_name, "seg": r.segment, "gmv": round(r.gmv), "cp": round(r.cp),
                        "orders": o, "pop": (None if pd.isna(r.pop) or r.pop in (float("inf"),) else round(r.pop, 1)),
                        "ef_pou": round(r.eater_fee / o, 2) if o else None,
                        "cpo": round(r.courier_costs / o, 2) if o else None,
                        "camp_share": round(r.camp_orders / o * 100, 1) if o else None})
        return out

    cities = []
    for r in cj.itertuples():
        o = int(r.orders); g = r.gmv
        cities.append({"city": r.city_name, "gmv": round(g), "cp": round(r.cp), "gp": round(r.gp),
                       "commission": round(r.commission), "demand_inc": round(r.demand_inc),
                       "supply_inc": round(r.supply_inc), "refunds": round(r.refunds),
                       "courier_costs": round(r.courier_costs), "eater_fee": round(r.eater_fee),
                       "camp_bolt": round(r.camp_bolt), "camp_prov": round(r.camp_prov),
                       "camp_disc": round(r.camp_disc), "camp_orders": int(r.camp_orders), "orders": o,
                       "churn": int(r.churn) if not pd.isna(r.churn) else 0,
                       "cp_margin": round(r.cp / g * 100, 1) if g else None,
                       "cpo": round(r.courier_costs / o, 2) if o else None,
                       "ef_pou": round(r.eater_fee / o, 2) if o else None,
                       "ef_pct": round(r.eater_fee / g * 100, 1) if g else None,
                       "camp_bolt_pct": round(r.camp_bolt / g * 100, 1) if g else None,
                       "camp_share": round(r.camp_orders / o * 100, 1) if o else None,
                       "failed_rate": round(r.failed_rate, 1) if r.failed_rate else None,
                       "late_rate": round(r.late_rate, 1) if r.late_rate else None,
                       "aov": round(r.aov, 1) if r.aov else None, "brands": int(r.brands),
                       "gmv_may": round(r.gmv_prev) if not pd.isna(r.gmv_prev) else None,
                       "pop": round((g / r.gmv_prev - 1) * 100, 1) if not pd.isna(r.gmv_prev) and r.gmv_prev else None,
                       "segments": seg_for(r.city_name), "top_brands": topb(r.city_name)})
    segtrend = []
    for m in ALLM:
        s = df[df.m == m].groupby("segment").agg(
            gmv=("gmv", "sum"), cp=("cp", "sum"), orders=("orders", "sum"), eater_fee=("eater_fee", "sum"),
            courier_costs=("courier_costs", "sum"), camp_bolt=("camp_bolt", "sum"), camp_prov=("camp_prov", "sum"),
            camp_disc=("camp_disc", "sum"), camp_orders=("camp_orders", "sum"), brands=("brand_name", "nunique"))
        for sg in s.index:
            row = s.loc[sg]
            segtrend.append({"month": m, "segment": sg, "gmv": round(row.gmv), "cp": round(row.cp),
                             "orders": int(row.orders), "eater_fee": round(row.eater_fee),
                             "courier_costs": round(row.courier_costs), "camp_bolt": round(row.camp_bolt),
                             "camp_prov": round(row.camp_prov), "camp_disc": round(row.camp_disc),
                             "camp_orders": int(row.camp_orders), "brands": int(row.brands)})

    def bagg(g):
        return pd.Series({k: g[k].sum() for k in ["gmv", "cp", "orders", "eater_fee", "courier_costs", "camp_bolt", "camp_orders"]})

    bj = curdf.groupby("brand_name").apply(bagg)
    bp = prevdf.groupby("brand_name").agg(gmv_prev=("gmv", "sum"))
    segm = curdf.sort_values("gmv", ascending=False).groupby("brand_name").first()[["segment"]]
    cmain = curdf.groupby(["brand_name", "city_name"]).gmv.sum().reset_index().sort_values(
        "gmv", ascending=False).groupby("brand_name").first()["city_name"]
    nci = curdf.groupby("brand_name").city_name.nunique()
    b = bj.join(bp).join(segm).reset_index()
    b["pop"] = (b.gmv / b.gmv_prev - 1) * 100
    b["main_city"] = b.brand_name.map(cmain); b["ncities"] = b.brand_name.map(nci)
    b = b.sort_values("gmv", ascending=False)
    brands = []
    for r in b.head(22).itertuples():
        o = int(r.orders)
        brands.append({"brand": r.brand_name, "seg": r.segment, "gmv": round(r.gmv), "cp": round(r.cp), "orders": o,
                       "gmv_may": round(r.gmv_prev) if not pd.isna(r.gmv_prev) else None,
                       "pop": (None if pd.isna(r.pop) else round(r.pop, 1)),
                       "cp_margin": round(r.cp / r.gmv * 100, 1) if r.gmv else None,
                       "eater_fee": round(r.eater_fee), "ef_pou": round(r.eater_fee / o, 2) if o else None,
                       "cpo": round(r.courier_costs / o, 2) if o else None, "camp_bolt": round(r.camp_bolt),
                       "camp_share": round(r.camp_orders / o * 100, 1) if o else None,
                       "main_city": r.main_city, "ncities": int(r.ncities)})

    def tot(m):
        s = df[df.m == m]; o = int(s.orders.sum()); g = s.gmv.sum()
        return {"gmv": round(g), "cp": round(s.cp.sum()), "orders": o, "commission": round(s.commission.sum()),
                "eater_fee": round(s.eater_fee.sum()), "courier_costs": round(s.courier_costs.sum()),
                "camp_bolt": round(s.camp_bolt.sum()), "camp_prov": round(s.camp_prov.sum()),
                "camp_disc": round(s.camp_disc.sum()), "camp_orders": int(s.camp_orders.sum()),
                "cpo": round(s.courier_costs.sum() / o, 2), "ef_pou": round(s.eater_fee.sum() / o, 2),
                "ef_pct": round(s.eater_fee.sum() / g * 100, 1), "camp_bolt_pct": round(s.camp_bolt.sum() / g * 100, 1),
                "camp_share": round(s.camp_orders.sum() / o * 100, 1), "gp": round(s.gp.sum()),
                "brands": int(s.brand_name.nunique()), "cities": int(s.city_name.nunique())}

    cities = [c for c in cities if c["gmv"] > 0]
    tg = sum(c["gmv"] for c in cities)
    for c in cities:
        c["share"] = round(c["gmv"] / tg * 100, 1)
        c["top_brands"] = [x for x in c["top_brands"] if x["gmv"] > 0][:5]
    period = f"{MLABEL[ALLM[0]]}–{MLABEL[curm]} 2026"
    out = {"meta": {"country": "Ukraine", "vertical": "3P Stores (store_3p_ent + store_3p_mm_smb)",
                    "months": ALLM, "cur": curm, "prev": prevm, "latest": f"{MLABEL[curm]} 2026",
                    "period": period, "source": f"{FACT} + dim_provider_v2 (dbx)"},
           "totals": {m: tot(m) for m in ALLM}, "cities": cities, "segments": segtrend, "brands": brands}
    return out


# ────────────────────────────────────────────────────────────────────────────
def build_diag_sim(cur, prev):
    inlist = "','".join(FOCUS)
    cols = ("f.total_gmv_before_discounts_eur gmv, f.total_contribution_profit_eur cp, "
            "f.total_invoiced_provider_commission_eur commission, f.total_eater_fee_revenue_eur eater_fee, "
            "f.total_invoiced_courier_costs_eur courier_costs, f.total_invoiced_demand_incentives_eur demand_inc, "
            "f.total_invoiced_supply_incentives_eur supply_inc, f.total_invoiced_demand_refunds_eur dem_ref, "
            "f.total_invoiced_supply_refunds_eur sup_ref, f.total_campaign_spend_bolt_eur camp_bolt, "
            "f.campaign_orders_count camp_orders, f.delivered_orders_count orders, "
            "f.courier_delivered_orders_count cour_orders")
    b = rnum(q(f"SELECT d.brand_name,{cols} FROM {FACT} f JOIN {DIM} d ON f.provider_id=d.provider_id "
               f"WHERE d.country_code='ua' AND {VERT} AND f.metric_timestamp_partition=DATE'{cur.isoformat()}' "
               f"AND UPPER(d.brand_name) IN ('{inlist}')"), skip=("brand_name",))
    c = rnum(q(f"SELECT d.brand_name,d.city_name,{cols} FROM {FACT} f JOIN {DIM} d ON f.provider_id=d.provider_id "
               f"WHERE d.country_code='ua' AND {VERT} AND f.metric_timestamp_partition=DATE'{cur.isoformat()}' "
               f"AND UPPER(d.brand_name) IN ('{inlist}')"), skip=("brand_name", "city_name"))

    def per(df, keys):
        g = df.groupby(keys).sum(numeric_only=True).reset_index(); o = g.orders
        g["aov"] = g.gmv / o; g["own"] = (1 - g.cour_orders / o) * 100
        g["comm_pct"] = g.commission / g.gmv * 100; g["comm_ord"] = g.commission / o
        g["ef_ord"] = g.eater_fee / o; g["cpo"] = g.courier_costs / o
        g["inc_ord"] = (g.demand_inc + g.supply_inc) / o; g["ref_ord"] = (g.dem_ref + g.sup_ref) / o
        g["camp_ord_e"] = g.camp_bolt / o; g["camp_share"] = g.camp_orders / o * 100
        g["cp_ord"] = g.cp / o; g["margin"] = g.cp / g.gmv * 100
        return g

    pb = per(b, ["brand_name"]).set_index("brand_name")
    pc = per(c, ["brand_name", "city_name"])
    ml = MLABEL[MABBR[cur.month]]

    def why(r):
        if r["own"] >= 95:
            return (f"Власна доставка (CPO=0). Комісія {r['comm_pct']:.1f}% (€{r['comm_ord']:.2f}/зам) — "
                    f"головний важіль; промо {r['camp_share']:.0f}% замовлень.")
        drivers = []
        if r["cpo"] >= 1.8:
            drivers.append(f"CPO €{r['cpo']:.2f}")
        if r["camp_share"] >= 50 or r["inc_ord"] >= 0.8:
            drivers.append(f"промо ({r['camp_share']:.0f}% замовлень, incentives €{r['inc_ord']:.2f}/зам)")
        if r["ref_ord"] >= 0.6:
            drivers.append(f"refunds €{r['ref_ord']:.2f}/зам")
        if r["comm_pct"] < 6:
            drivers.append(f"низька комісія {r['comm_pct']:.1f}%")
        head = "Прибуткова" if r["margin"] >= 0 else "Збиткова"
        return f"{head} ({r['margin']:.1f}%). Драйвери: " + (", ".join(drivers) if drivers else f"CPO €{r['cpo']:.2f}") + f". AOV €{r['aov']:.1f}."

    def reco(r):
        out = []
        if r["own"] >= 95:
            out.append(f"Комісія {r['comm_pct']:.1f}% → підняти (own-delivery, Bolt не несе курʼєрки).")
            out.append("Контроль Bolt-промо / cost-share на партнера.")
        else:
            if r["camp_share"] >= 50 or r["inc_ord"] >= 0.8:
                out.append(f"Промо ({r['camp_share']:.0f}% замовлень) — зрізати глибину/охоплення, partner cost-share, таргет ELC/churn.")
            if r["cpo"] >= 1.8:
                out.append(f"CPO €{r['cpo']:.2f} — батчинг, MOV↑, звузити зони.")
            if r["ref_ord"] >= 0.6:
                out.append(f"Refunds €{r['ref_ord']:.2f}/зам — availability, збірка, disputes.")
            if r["comm_pct"] < 6:
                out.append(f"Комісія {r['comm_pct']:.1f}% → 8%.")
        if not out:
            out.append("Тримати дисципліну по промо та CPO.")
        return out

    order = pb.assign(tot_cp=lambda x: x.cp).sort_values("cp").index.tolist()
    DIAG = []
    for br in order:
        r = pb.loc[br]
        DIAG.append({"brand": br, "aov": round(r["aov"], 2), "own": int(round(r["own"])),
                     "comm_pct": round(r["comm_pct"], 1), "comm": round(r["comm_ord"], 2),
                     "ef": round(r["ef_ord"], 2), "cpo": round(r["cpo"], 2), "inc": round(r["inc_ord"], 2),
                     "refund": round(r["ref_ord"], 2), "camp": round(r["camp_ord_e"], 2),
                     "camp_ord": int(round(r["camp_share"])), "cpo_ord": round(r["cp_ord"], 2),
                     "margin": round(r["margin"], 1), "why": why(r), "reco": reco(r)})
    CITYWORST = []
    for br in FOCUS:
        s = pc[(pc.brand_name == br) & (pc.gmv > 0)].sort_values("cp")
        if len(s) == 0:
            continue
        r = s.iloc[0]
        note = ""
        if len(s) > 1:
            r2 = s.iloc[1]
            note = f"Далі {r2['city_name']} ({round(r2['cp']):.0f}€, {r2['margin']:.1f}%)."
        CITYWORST.append([br, r["city_name"], int(r["orders"]), round(r["cp"]), round(r["margin"], 1),
                          round(r["cpo"], 2), int(round(r["camp_share"])), round(r["ref_ord"], 2), note])
    diag = {"month_label": ml, "DIAG": DIAG, "CITYWORST": CITYWORST}
    sim = {}
    for br in pb.index:
        r = pb.loc[br]
        sim[br.upper()] = {"gmv": round(r["gmv"]), "orders": int(r["orders"]), "cp": round(r["cp"]),
                           "commission": round(r["commission"]), "camp_bolt": round(r["camp_bolt"]),
                           "demand_inc": round(r["demand_inc"]), "refunds": round(r["dem_ref"] + r["sup_ref"]),
                           "comm_pct": round(r["comm_pct"], 1), "margin": round(r["margin"], 1),
                           "own": int(round(r["own"])), "cpo": round(r["cpo"], 2)}
    return diag, sim


# ────────────────────────────────────────────────────────────────────────────
def build_commission_actuals(months):
    inmonths = ",".join(f"DATE'{d.isoformat()}'" for d in months)
    grp_case = (f"CASE WHEN {TOP_BRAND_SQL} THEN 'TOP' "
                "WHEN d.business_segment_v2='Enterprise (AM Segment)' THEN 'ENT_OTH' "
                "WHEN d.business_segment_v2='SMB (AM Segment)' THEN 'SMB' "
                "WHEN d.business_segment_v2='Mid-market (AM Segment)' THEN 'MM' ELSE 'OTHER' END")
    sqlg = f"""SELECT f.metric_timestamp_partition month, {grp_case} grp,
        SUM(f.total_gmv_before_discounts_eur) gmv,
        SUM(f.total_provider_price_before_discounts_eur) mprice,
        SUM(f.total_invoiced_provider_commission_eur) comm,
        SUM(f.delivered_orders_count) orders
      FROM {FACT} f JOIN {DIM} d ON f.provider_id=d.provider_id
      WHERE d.country_code='ua' AND {VERT} AND f.metric_timestamp_partition IN ({inmonths})
      GROUP BY 1,2"""
    df = rnum(q(sqlg))
    df["month"] = df["month"].astype(str)
    d2a = {d.isoformat(): MLABEL[MABBR[d.month]] for d in months}
    df["ml"] = df["month"].map(d2a)
    labels = [MLABEL[MABBR[d.month]] for d in months]
    GRP = ["TOTAL", "TOP", "ENT_OTH", "SMB", "MM"]
    series = {}
    for grp in GRP:
        arr = []
        for lab in labels:
            if grp == "TOTAL":
                s = df[df.ml == lab]
            else:
                s = df[(df.ml == lab) & (df.grp == grp)]
            gmv = s.gmv.sum(); mp = s.mprice.sum(); comm = s.comm.sum(); o = s.orders.sum()
            arr.append({"m": lab, "comm": round(comm), "gmv": round(gmv), "orders": int(o),
                        "comm_pct": round(comm / gmv * 100, 1) if gmv else None,
                        "comm_aov": round(comm / mp * 100, 1) if mp else None,
                        "aov": round(gmv / o, 2) if o else None})
        series[grp] = arr
    # partner list ENT other (latest month)
    latest = months[-1]
    pdf = rnum(q(f"""SELECT d.brand_name, {SEG_CASE} segment, {grp_case} grp,
        SUM(f.total_invoiced_provider_commission_eur) comm, SUM(f.total_gmv_before_discounts_eur) gmv,
        SUM(f.total_provider_price_before_discounts_eur) mprice, SUM(f.delivered_orders_count) orders
      FROM {FACT} f JOIN {DIM} d ON f.provider_id=d.provider_id
      WHERE d.country_code='ua' AND {VERT} AND f.metric_timestamp_partition=DATE'{latest.isoformat()}'
      GROUP BY 1,2,3"""), skip=("brand_name", "segment", "grp"))
    ent = pdf[pdf.grp == "ENT_OTH"].sort_values("comm", ascending=False).head(15)
    partners_ent_oth = [{"brand": r.brand_name, "seg": r.segment, "comm": round(r.comm),
                         "comm_pct": round(r.comm / r.gmv * 100, 1) if r.gmv else 0,
                         "comm_aov": round(r.comm / r.mprice * 100, 1) if r.mprice else 0,
                         "aov": round(r.gmv / r.orders, 2) if r.orders else None} for r in ent.itertuples()]
    return {"months": labels, "actual_series": series, "partners_ent_oth": partners_ent_oth,
            "latest_label": labels[-1]}


def main():
    latest = latest_complete_month()
    months = month_list(latest, 8)
    prev = months[-2]
    print(f"Latest complete month: {latest} | window: {months[0]}..{latest}")
    main_out = build_main(months, latest, prev)
    (HERE / "threep_data.json").write_text(json.dumps(main_out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"threep_data.json: {len(main_out['cities'])} cities, {len(main_out['brands'])} brands")
    diag, sim = build_diag_sim(latest, prev)
    (HERE / "diag_data.json").write_text(json.dumps(diag, ensure_ascii=False), encoding="utf-8")
    (HERE / "sim_data.json").write_text(json.dumps(sim, ensure_ascii=False), encoding="utf-8")
    print(f"diag_data.json: {len(diag['DIAG'])} brands | sim_data.json: {len(sim)} brands")
    comm = build_commission_actuals(months)
    (HERE / "commission_actuals.json").write_text(json.dumps(comm, ensure_ascii=False), encoding="utf-8")
    print(f"commission_actuals.json: {len(comm['months'])} months")
    print("Refresh complete.")


if __name__ == "__main__":
    main()
