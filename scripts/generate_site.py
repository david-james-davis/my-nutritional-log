#!/usr/bin/env python3
"""Generate a static GitHub Pages site from nutritional log JSON entries."""

import json
from collections import defaultdict
from datetime import date
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


def load_featured_entry(entries):
    """Return (entry, is_today). Prefers today's file by path; falls back to most recent."""
    today = date.today()
    today_path = ENTRIES_DIR / str(today.year) / f"{today.month:02d}" / f"{today.day:02d}.json"
    if today_path.exists():
        with open(today_path) as f:
            return json.load(f), True
    return entries[-1], False


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


GOALS = {
    "calories": 2487.1,
    "protein": 167.2,
    "fat": 83.0,
    "carbs": 268.0,
}

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def build_chart_data(entries):
    """Return (current_month, monthly) JSON-serialisable dicts for charts."""
    today = date.today()
    current_month_key = f"{today.year}-{today.month:02d}"
    current_month_label = f"{MONTH_NAMES[today.month - 1]} {today.year}"

    current_month = {"label": current_month_label, "labels": [],
                     "calories": [], "protein": [], "fat": [], "carbs": [], "fiber": []}
    monthly_buckets = defaultdict(lambda: defaultdict(list))

    for e in entries:
        dt = e["date"]
        total = e.get("dailyTotal", {})
        cals = total.get("calories", 0)
        protein = total.get("protein", 0)
        fat = total.get("fat", 0)
        carbs = total.get("carbohydrates", 0)
        fiber = total.get("fiber", 0)

        year, month, *_ = dt.split("-")
        month_key = f"{year}-{month}"

        if month_key == current_month_key:
            current_month["labels"].append(dt)
            current_month["calories"].append(cals)
            current_month["protein"].append(protein)
            current_month["fat"].append(fat)
            current_month["carbs"].append(carbs)
            current_month["fiber"].append(fiber)

        monthly_buckets[month_key]["calories"].append(cals)
        monthly_buckets[month_key]["protein"].append(protein)
        monthly_buckets[month_key]["fat"].append(fat)
        monthly_buckets[month_key]["carbs"].append(carbs)
        monthly_buckets[month_key]["fiber"].append(fiber)

    monthly = {"labels": [], "calories": [], "protein": [], "fat": [], "carbs": [], "fiber": []}
    for key in sorted(monthly_buckets):
        year, month = key.split("-")
        monthly["labels"].append(f"{MONTH_NAMES[int(month)-1]} {year}")
        bucket = monthly_buckets[key]
        for macro in ("calories", "protein", "fat", "carbs", "fiber"):
            vals = bucket[macro]
            monthly[macro].append(round(sum(vals) / len(vals), 1))

    return current_month, monthly


def render_today_tab(entry, is_today):
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
        {'<span class="badge">Today</span>' if is_today else f'<span class="badge badge-stale">Last logged: {dt}</span>'}
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
        <h3>Daily Trends — <span id="chartDailyMonth"></span></h3>
        <div class="chart-wrap" style="height:320px"><canvas id="chartDaily"></canvas></div>
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
    featured, is_today = load_featured_entry(entries)
    today_content = render_today_tab(featured, is_today)
    history_content = render_history_tab(entries)
    current_month, monthly = build_chart_data(entries)

    current_month_json = json.dumps(current_month)
    monthly_json = json.dumps(monthly)
    goals_json = json.dumps(GOALS)

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
    .badge-stale {{ background: #e67e22; }}
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
    const currentMonth = {current_month_json};
    const monthly = {monthly_json};
    const GOALS = {goals_json};

    const MACROS = [
      {{ key: 'calories', label: 'Calories', unit: 'kcal', color: '#e67e22', axis: 'y'  }},
      {{ key: 'protein',  label: 'Protein',  unit: 'g',    color: '#2980b9', axis: 'y1' }},
      {{ key: 'fat',      label: 'Fat',      unit: 'g',    color: '#8e44ad', axis: 'y1' }},
      {{ key: 'carbs',    label: 'Carbs',    unit: 'g',    color: '#27ae60', axis: 'y1' }},
      {{ key: 'fiber',    label: 'Fiber',    unit: 'g',    color: '#16a085', axis: 'y1' }},
    ];

    function actualDataset(macro, data) {{
      const n = data.labels.length;
      return {{
        label: `${{macro.label}} (${{macro.unit}})`,
        data: data[macro.key],
        borderColor: macro.color,
        backgroundColor: macro.color + '18',
        borderWidth: 2,
        pointRadius: n <= 15 ? 4 : 2,
        pointHoverRadius: 6,
        tension: 0.35,
        fill: false,
        yAxisID: macro.axis,
      }};
    }}

    function goalDataset(macro, n) {{
      if (!(macro.key in GOALS)) return null;
      return {{
        label: `${{macro.label}} goal (${{GOALS[macro.key]}}${{macro.unit}})`,
        data: Array(n).fill(GOALS[macro.key]),
        borderColor: macro.color,
        backgroundColor: 'transparent',
        borderWidth: 1.5,
        borderDash: [6, 4],
        pointRadius: 0,
        pointHoverRadius: 0,
        tension: 0,
        fill: false,
        yAxisID: macro.axis,
      }};
    }}

    document.getElementById('chartDailyMonth').textContent = currentMonth.label;

    const n = currentMonth.labels.length;
    const dailyDatasets = [];
    for (const m of MACROS) {{
      dailyDatasets.push(actualDataset(m, currentMonth));
      const g = goalDataset(m, n);
      if (g) dailyDatasets.push(g);
    }}

    new Chart(document.getElementById('chartDaily'), {{
      type: 'line',
      data: {{ labels: currentMonth.labels, datasets: dailyDatasets }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        interaction: {{ mode: 'index', intersect: false }},
        plugins: {{
          legend: {{
            position: 'top',
            labels: {{
              boxWidth: 20,
              font: {{ size: 11 }},
              generateLabels(chart) {{
                return Chart.defaults.plugins.legend.labels.generateLabels(chart).map(item => {{
                  if (chart.data.datasets[item.datasetIndex].borderDash) {{
                    item.lineDash = [6, 4];
                  }}
                  return item;
                }});
              }},
            }},
          }},
          tooltip: {{
            callbacks: {{
              label: ctx => ` ${{ctx.dataset.label}}: ${{ctx.parsed.y}}`,
            }},
          }},
        }},
        scales: {{
          x: {{ grid: {{ color: '#f0f0f0' }}, ticks: {{ font: {{ size: 11 }} }} }},
          y: {{
            position: 'left',
            grid: {{ color: '#f0f0f0' }},
            beginAtZero: false,
            title: {{ display: true, text: 'Calories (kcal)', font: {{ size: 11 }}, color: '#e67e22' }},
          }},
          y1: {{
            position: 'right',
            grid: {{ drawOnChartArea: false }},
            beginAtZero: true,
            title: {{ display: true, text: 'Grams (g)', font: {{ size: 11 }}, color: '#555' }},
          }},
        }},
      }},
    }});

    // Monthly averages bar chart
    const MACROS_BAR = [
      {{ key: 'calories', label: 'Calories (kcal)', color: '#e67e22' }},
      {{ key: 'protein',  label: 'Protein (g)',     color: '#2980b9' }},
      {{ key: 'fat',      label: 'Fat (g)',          color: '#8e44ad' }},
      {{ key: 'carbs',    label: 'Carbs (g)',        color: '#27ae60' }},
      {{ key: 'fiber',    label: 'Fiber (g)',        color: '#16a085' }},
    ];

    new Chart(document.getElementById('chartMonthly'), {{
      type: 'bar',
      data: {{
        labels: monthly.labels,
        datasets: MACROS_BAR.map(m => ({{
          label: m.label,
          data: monthly[m.key],
          backgroundColor: m.color + 'cc',
          borderWidth: 0,
          borderRadius: 4,
        }})),
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        interaction: {{ mode: 'index', intersect: false }},
        plugins: {{
          legend: {{ position: 'top', labels: {{ boxWidth: 12, font: {{ size: 11 }} }} }},
          tooltip: {{ callbacks: {{ label: ctx => ` ${{ctx.dataset.label}}: ${{ctx.parsed.y}} avg` }} }},
        }},
        scales: {{
          x: {{ grid: {{ color: '#f0f0f0' }}, ticks: {{ font: {{ size: 11 }} }} }},
          y: {{ grid: {{ color: '#f0f0f0' }}, beginAtZero: true }},
        }},
      }},
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
