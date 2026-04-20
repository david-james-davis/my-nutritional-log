#!/usr/bin/env python3
"""Generate a static GitHub Pages site from nutritional log JSON entries."""

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
ENTRIES_DIR = ROOT / "data" / "entries"
OUTPUT_DIR = ROOT / "site"


def load_all_entries():
    entries = []
    for json_file in sorted(ENTRIES_DIR.rglob("*.json")):
        try:
            with open(json_file) as f:
                data = json.load(f)
            if data.get("date"):
                entries.append(data)
        except (json.JSONDecodeError, KeyError):
            pass
    entries.sort(key=lambda e: e["date"])
    return entries


def fmt_num(val, unit="g"):
    if val == 0:
        return "—"
    return f"{val:g}{unit}"


def meal_row(label, meal):
    name = meal.get("mealName", "")
    if not name:
        return ""
    return f"""
        <tr>
          <td class="meal-label">{label}</td>
          <td class="meal-name">{name}</td>
          <td>{fmt_num(meal.get('calories', 0), 'kcal')}</td>
          <td>{fmt_num(meal.get('protein', 0))}</td>
          <td>{fmt_num(meal.get('fat', 0))}</td>
          <td>{fmt_num(meal.get('carbohydrates', 0))}</td>
          <td>{fmt_num(meal.get('fiber', 0))}</td>
        </tr>"""


def macro_card(label, value, unit, color):
    return f"""
        <div class="macro-card" style="border-top: 4px solid {color}">
          <div class="macro-value">{value:g}<span class="macro-unit">{unit}</span></div>
          <div class="macro-label">{label}</div>
        </div>"""


def build_chart_data(entries):
    """Return JSON-serialisable dicts for daily and monthly charts."""
    daily = {
        "labels": [],
        "calories": [],
        "protein": [],
        "fat": [],
        "carbs": [],
        "fiber": [],
    }
    monthly_buckets = defaultdict(lambda: defaultdict(list))

    for e in entries:
        dt = e["date"]
        total = e.get("dailyTotal", {})
        cals = total.get("calories", 0)
        protein = total.get("protein", 0)
        fat = total.get("fat", 0)
        carbs = total.get("carbohydrates", 0)
        fiber = total.get("fiber", 0)

        daily["labels"].append(dt)
        daily["calories"].append(cals)
        daily["protein"].append(protein)
        daily["fat"].append(fat)
        daily["carbs"].append(carbs)
        daily["fiber"].append(fiber)

        # e.g. "2026-04" → human label "Apr 2026"
        year, month, *_ = dt.split("-")
        month_key = f"{year}-{month}"
        monthly_buckets[month_key]["calories"].append(cals)
        monthly_buckets[month_key]["protein"].append(protein)
        monthly_buckets[month_key]["fat"].append(fat)
        monthly_buckets[month_key]["carbs"].append(carbs)
        monthly_buckets[month_key]["fiber"].append(fiber)

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    monthly = {"labels": [], "calories": [], "protein": [], "fat": [], "carbs": [], "fiber": []}
    for key in sorted(monthly_buckets):
        year, month = key.split("-")
        monthly["labels"].append(f"{month_names[int(month)-1]} {year}")
        bucket = monthly_buckets[key]
        for macro in ("calories", "protein", "fat", "carbs", "fiber"):
            vals = bucket[macro]
            monthly[macro].append(round(sum(vals) / len(vals), 1))

    return daily, monthly


def render_today_tab(entry):
    dt = entry["date"]
    total = entry.get("dailyTotal", {})
    cals = total.get("calories", 0)
    protein = total.get("protein", 0)
    fat = total.get("fat", 0)
    carbs = total.get("carbohydrates", 0)
    fiber = total.get("fiber", 0)

    meal_rows = ""
    for label, key in [("Breakfast", "breakfast"), ("Lunch", "lunch"), ("Dinner", "dinner")]:
        meal = entry.get(key, {})
        if meal:
            meal_rows += meal_row(label, meal)
    for i, snack in enumerate(entry.get("snacks", []), 1):
        label = "Snack" if len(entry.get("snacks", [])) == 1 else f"Snack {i}"
        meal_rows += meal_row(label, snack)

    return f"""
      <div class="date-header">
        <h2>{dt}</h2>
        <span class="badge">Latest Entry</span>
      </div>
      <div class="macro-grid">
        {macro_card("Calories", cals, "kcal", "#e67e22")}
        {macro_card("Protein", protein, "g", "#2980b9")}
        {macro_card("Fat", fat, "g", "#8e44ad")}
        {macro_card("Carbs", carbs, "g", "#27ae60")}
        {macro_card("Fiber", fiber, "g", "#16a085")}
      </div>

      <h3>Meals</h3>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Meal</th><th>Description</th><th>Calories</th>
              <th>Protein</th><th>Fat</th><th>Carbs</th><th>Fiber</th>
            </tr>
          </thead>
          <tbody>
            {meal_rows}
            <tr class="total-row">
              <td colspan="2"><strong>Daily Total</strong></td>
              <td><strong>{fmt_num(cals, 'kcal')}</strong></td>
              <td><strong>{fmt_num(protein)}</strong></td>
              <td><strong>{fmt_num(fat)}</strong></td>
              <td><strong>{fmt_num(carbs)}</strong></td>
              <td><strong>{fmt_num(fiber)}</strong></td>
            </tr>
          </tbody>
        </table>
      </div>"""


def render_history_tab(entries):
    rows = ""
    for e in reversed(entries):
        dt = e["date"]
        total = e.get("dailyTotal", {})
        cals = total.get("calories", 0)
        protein = total.get("protein", 0)
        fat = total.get("fat", 0)
        carbs = total.get("carbohydrates", 0)
        fiber = total.get("fiber", 0)
        rows += f"""
          <tr>
            <td>{dt}</td>
            <td>{fmt_num(cals, 'kcal')}</td>
            <td>{fmt_num(protein)}</td>
            <td>{fmt_num(fat)}</td>
            <td>{fmt_num(carbs)}</td>
            <td>{fmt_num(fiber)}</td>
          </tr>"""

    return f"""
      <h2>Historical Data</h2>

      <div class="chart-section">
        <h3>Daily Trends</h3>
        <div class="chart-wrap"><canvas id="chartDaily"></canvas></div>
      </div>

      <div class="chart-section">
        <h3>Monthly Averages</h3>
        <div class="chart-wrap"><canvas id="chartMonthly"></canvas></div>
      </div>

      <h3 style="margin-top:2rem">All Entries</h3>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Date</th><th>Calories</th><th>Protein</th>
              <th>Fat</th><th>Carbs</th><th>Fiber</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
      </div>"""


def generate_html(entries):
    latest = entries[-1]
    today_content = render_today_tab(latest)
    history_content = render_history_tab(entries)
    daily, monthly = build_chart_data(entries)

    daily_json = json.dumps(daily)
    monthly_json = json.dumps(monthly)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Nutritional Log</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f7fa; color: #2c3e50; }}
    header {{ background: #2c3e50; color: #fff; padding: 1.25rem 2rem; }}
    header h1 {{ font-size: 1.5rem; font-weight: 600; }}
    header p {{ font-size: 0.85rem; opacity: 0.7; margin-top: 0.25rem; }}
    .tabs {{ display: flex; background: #fff; border-bottom: 2px solid #e0e0e0; padding: 0 2rem; }}
    .tab-btn {{ padding: 0.9rem 1.5rem; font-size: 0.95rem; font-weight: 500; border: none; background: none; cursor: pointer; color: #666; border-bottom: 3px solid transparent; margin-bottom: -2px; transition: color 0.2s, border-color 0.2s; }}
    .tab-btn.active {{ color: #2980b9; border-bottom-color: #2980b9; }}
    .tab-btn:hover {{ color: #2980b9; }}
    .tab-panel {{ display: none; padding: 2rem; max-width: 1100px; margin: 0 auto; }}
    .tab-panel.active {{ display: block; }}
    .date-header {{ display: flex; align-items: baseline; gap: 0.75rem; margin-bottom: 1.5rem; }}
    .date-header h2 {{ font-size: 1.4rem; line-height: 1; }}
    .badge {{ background: #27ae60; color: #fff; font-size: 0.7rem; padding: 0.2rem 0.55rem; border-radius: 999px; font-weight: 600; position: relative; top: -0.1em; }}
    .macro-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
    .macro-card {{ background: #fff; border-radius: 10px; padding: 1.25rem 1rem; text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
    .macro-value {{ font-size: 2rem; font-weight: 700; line-height: 1; }}
    .macro-unit {{ font-size: 0.8rem; font-weight: 400; margin-left: 2px; color: #888; }}
    .macro-label {{ font-size: 0.8rem; color: #888; margin-top: 0.4rem; text-transform: uppercase; letter-spacing: 0.05em; }}
    h2 {{ font-size: 1.4rem; margin-bottom: 1.5rem; }}
    h3 {{ font-size: 0.85rem; font-weight: 600; color: #555; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.75rem; }}
    .chart-section {{ background: #fff; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
    .chart-wrap {{ position: relative; height: 280px; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.08); font-size: 0.9rem; }}
    th {{ background: #f0f4f8; padding: 0.75rem 1rem; text-align: left; font-weight: 600; color: #555; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.04em; }}
    td {{ padding: 0.7rem 1rem; border-top: 1px solid #f0f0f0; }}
    tr:hover td {{ background: #fafcff; }}
    .meal-label {{ font-weight: 600; color: #555; white-space: nowrap; }}
    .meal-name {{ color: #444; max-width: 340px; }}
    .total-row td {{ background: #f7f9fc; font-weight: 600; border-top: 2px solid #e0e0e0; }}
  </style>
</head>
<body>
  <header>
    <h1>Nutritional Log</h1>
    <p>Personal daily nutrition tracker</p>
  </header>

  <div class="tabs">
    <button class="tab-btn active" onclick="showTab('today', this)">Today</button>
    <button class="tab-btn" onclick="showTab('history', this)">History</button>
  </div>

  <div id="tab-today" class="tab-panel active">
    {today_content}
  </div>

  <div id="tab-history" class="tab-panel">
    {history_content}
  </div>

  <script>
    const daily = {daily_json};
    const monthly = {monthly_json};

    const MACROS = [
      {{ key: 'calories', label: 'Calories (kcal)', color: '#e67e22' }},
      {{ key: 'protein',  label: 'Protein (g)',     color: '#2980b9' }},
      {{ key: 'fat',      label: 'Fat (g)',          color: '#8e44ad' }},
      {{ key: 'carbs',    label: 'Carbs (g)',        color: '#27ae60' }},
      {{ key: 'fiber',    label: 'Fiber (g)',        color: '#16a085' }},
    ];

    function dataset(macro, data, type) {{
      return {{
        label: macro.label,
        data: data[macro.key],
        borderColor: macro.color,
        backgroundColor: type === 'bar' ? macro.color + 'cc' : macro.color + '22',
        borderWidth: type === 'bar' ? 0 : 2,
        pointRadius: data.labels.length < 30 ? 4 : 2,
        tension: 0.3,
        fill: type === 'line',
      }};
    }}

    const sharedOptions = (yLabel) => ({{
      responsive: true,
      maintainAspectRatio: false,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{
        legend: {{ position: 'top', labels: {{ boxWidth: 12, font: {{ size: 12 }} }} }},
        tooltip: {{ callbacks: {{ label: ctx => ` ${{ctx.dataset.label}}: ${{ctx.parsed.y}}` }} }},
      }},
      scales: {{
        x: {{ grid: {{ color: '#f0f0f0' }}, ticks: {{ maxTicksLimit: 12, font: {{ size: 11 }} }} }},
        y: {{ grid: {{ color: '#f0f0f0' }}, beginAtZero: true, title: {{ display: false }} }},
      }},
    }});

    new Chart(document.getElementById('chartDaily'), {{
      type: 'line',
      data: {{
        labels: daily.labels,
        datasets: MACROS.map(m => dataset(m, daily, 'line')),
      }},
      options: sharedOptions('Value'),
    }});

    new Chart(document.getElementById('chartMonthly'), {{
      type: 'bar',
      data: {{
        labels: monthly.labels,
        datasets: MACROS.map(m => dataset(m, monthly, 'bar')),
      }},
      options: {{ ...sharedOptions('Avg value'), plugins: {{ ...sharedOptions().plugins, tooltip: {{ callbacks: {{ label: ctx => ` ${{ctx.dataset.label}}: ${{ctx.parsed.y}} avg` }} }} }} }},
    }});

    function showTab(name, btn) {{
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.getElementById('tab-' + name).classList.add('active');
      btn.classList.add('active');
    }}
  </script>
</body>
</html>"""


def main():
    entries = load_all_entries()
    if not entries:
        raise SystemExit("No entries found in data/entries/")

    OUTPUT_DIR.mkdir(exist_ok=True)
    html = generate_html(entries)
    output_file = OUTPUT_DIR / "index.html"
    output_file.write_text(html)
    print(f"Generated {output_file} ({len(entries)} entries, latest: {entries[-1]['date']})")


if __name__ == "__main__":
    main()
