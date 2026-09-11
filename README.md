# 3P Stores — City & Partner Analysis · Bolt Food UA

Аналіз вертикалі **3P Stores** (store_3p_ent + store_3p_mm_smb) на Bolt Food в Україні:
всі ключові метрики delivery-репорту в розрізі **міст** і **партнерів**, з поділом на
**Enterprise / Mid-market / SMB**.

**Живий звіт:** https://yuliianikolaieva.github.io/3p-stores-city-analysis/

## Що всередині
- KPI: GMV, Contribution Profit, CP margin, замовлення, кількість партнерів/міст.
- Growth & profitability по сегментах (GMV і CP по місяцях, Jan–Aug 2026).
- City ranking — фінанс і опс (GMV, частка, MoM, CP, CP margin, AOV, failed/late rate).
- **Commission tab** — рівень комісії %GMV + AOV (Jan–Aug), розріз ENT/SMB, топ-партнери, а також цільові метрики: Commission of New merchants (Top Brands) та (Other ENT) + калькулятор квартальних цілей.
- City deep-dive — спліт по сегментах і топ-партнери для топ-15 міст.
- Partner leaderboard (top-22 by GMV) + Movers (хто зростає / падає).

## Дані
Джерело: Databricks `ng_delivery_spark.fact_provider_monthly` + `dim_provider_v2`,
`country_code = 'ua'`, `delivery_vertical IN ('store_3p_ent','store_3p_mm_smb')`.
Період: січень–серпень 2026 (місячна гранулярність), останній повний місяць — серпень 2026. Сегмент = `business_segment_v2`.

## Оновлення
```bash
# 1) оновити threep_data.json (експорт з dbx)
# 2) перегенерувати HTML:
python3 generate_report.py
```
`index.html` — самодостатній (дані вбудовані, графіки через Chart.js CDN).
