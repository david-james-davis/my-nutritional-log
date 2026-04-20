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
    """Return all_days dict for the history line chart."""
    all_days = {"labels": [], "calories": [], "protein": [], "fat": [], "carbs": [], "fiber": []}
    for e in entries:
        total = e.get("dailyTotal", {})
        all_days["labels"].append(e["date"])
        all_days["calories"].append(total.get("calories", 0))
        all_days["protein"].append(total.get("protein", 0))
        all_days["fat"].append(total.get("fat", 0))
        all_days["carbs"].append(total.get("carbohydrates", 0))
        all_days["fiber"].append(total.get("fiber", 0))
    return all_days


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

      <div class="chart-section">
        <h3>Progress Toward Daily Goals</h3>
        <div class="chart-wrap" style="height:200px"><canvas id="chartGoals"></canvas></div>
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
        <h3>Daily Calories</h3>
        <div class="chart-wrap" style="height:300px"><canvas id="chartHistory"></canvas></div>
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
    all_days = build_chart_data(entries)
    all_days_json = json.dumps(all_days)
    goals_json = json.dumps(GOALS)

    ft = featured.get("dailyTotal", {})
    featured_totals_json = json.dumps({
        "calories": ft.get("calories", 0),
        "protein":  ft.get("protein", 0),
        "fat":      ft.get("fat", 0),
        "carbs":    ft.get("carbohydrates", 0),
    })

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
    const featuredTotals = {featured_totals_json};
    const allDays = {all_days_json};
    const GOALS = {goals_json};

    // History: daily calories line chart
    const histGoalLinePlugin = {{
      id: 'histGoalLine',
      afterDraw(chart) {{
        const {{ ctx, scales: {{ x, y }} }} = chart;
        const yPx = y.getPixelForValue(GOALS.calories);
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(x.left, yPx);
        ctx.lineTo(x.right, yPx);
        ctx.strokeStyle = '#e74c3c';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([6, 4]);
        ctx.stroke();
        ctx.font = '11px system-ui';
        ctx.fillStyle = '#e74c3c';
        ctx.textAlign = 'right';
        ctx.fillText(`Goal ${{GOALS.calories}} kcal`, x.right - 4, yPx - 5);
        ctx.restore();
      }},
    }};

    new Chart(document.getElementById('chartHistory'), {{
      type: 'line',
      plugins: [histGoalLinePlugin],
      data: {{
        labels: allDays.labels,
        datasets: [{{
          label: 'Calories',
          data: allDays.calories,
          borderColor: '#e67e22',
          backgroundColor: '#e67e2220',
          borderWidth: 2,
          pointRadius: 5,
          pointHoverRadius: 8,
          pointBackgroundColor: '#e67e22',
          tension: 0.2,
          fill: true,
        }}],
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        interaction: {{ mode: 'index', intersect: false }},
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{
            callbacks: {{
              title: ([ctx]) => allDays.labels[ctx.dataIndex],
              label: ctx => ` Calories: ${{ctx.parsed.y}} kcal`,
              afterBody: (items) => {{
                const i = items[0].dataIndex;
                return [
                  ` Protein: ${{allDays.protein[i]}}g`,
                  ` Fat: ${{allDays.fat[i]}}g`,
                  ` Carbs: ${{allDays.carbs[i]}}g`,
                  ` Fiber: ${{allDays.fiber[i]}}g`,
                ];
              }},
            }},
          }},
        }},
        scales: {{
          x: {{ grid: {{ color: '#f0f0f0' }}, ticks: {{ maxTicksLimit: 15, font: {{ size: 11 }} }} }},
          y: {{
            grid: {{ color: '#f0f0f0' }},
            beginAtZero: false,
            title: {{ display: true, text: 'Calories (kcal)', font: {{ size: 11 }}, color: '#888' }},
          }},
        }},
      }},
    }});

    // Goal progress chart (Today tab)
    const goalItems = [
      {{ key: 'calories', label: 'Calories', unit: 'kcal', color: '#e67e22' }},
      {{ key: 'protein',  label: 'Protein',  unit: 'g',    color: '#2980b9' }},
      {{ key: 'fat',      label: 'Fat',      unit: 'g',    color: '#8e44ad' }},
      {{ key: 'carbs',    label: 'Carbs',    unit: 'g',    color: '#27ae60' }},
    ];

    const goalLinePlugin = {{
      id: 'goalLine',
      afterDraw(chart) {{
        const {{ ctx, scales: {{ x, y }} }} = chart;
        const xPx = x.getPixelForValue(100);
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(xPx, y.top);
        ctx.lineTo(xPx, y.bottom);
        ctx.strokeStyle = '#e74c3c';
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 4]);
        ctx.stroke();
        ctx.font = '11px system-ui';
        ctx.fillStyle = '#e74c3c';
        ctx.textAlign = 'center';
        ctx.fillText('Goal', xPx, y.top - 6);
        ctx.restore();
      }},
    }};

    new Chart(document.getElementById('chartGoals'), {{
      type: 'bar',
      plugins: [goalLinePlugin],
      data: {{
        labels: goalItems.map(m => m.label),
        datasets: [{{
          data: goalItems.map(m => {{
            const goal = GOALS[m.key];
            return goal ? Math.round((featuredTotals[m.key] / goal) * 1000) / 10 : 0;
          }}),
          backgroundColor: goalItems.map(m => {{
            const pct = featuredTotals[m.key] / GOALS[m.key] * 100;
            return pct > 100 ? '#e74c3ccc' : m.color + 'cc';
          }}),
          borderRadius: 4,
          borderSkipped: false,
        }}],
      }},
      options: {{
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{
            callbacks: {{
              label: ctx => {{
                const m = goalItems[ctx.dataIndex];
                const actual = featuredTotals[m.key];
                const goal = GOALS[m.key];
                return ` ${{actual}}${{m.unit}} of ${{goal}}${{m.unit}} (${{ctx.parsed.x}}%)`;
              }},
            }},
          }},
        }},
        scales: {{
          x: {{
            min: 0,
            max: 130,
            grid: {{ color: '#f0f0f0' }},
            ticks: {{ callback: v => v + '%', font: {{ size: 11 }} }},
          }},
          y: {{
            grid: {{ display: false }},
            ticks: {{ font: {{ size: 12 }}, color: '#444' }},
          }},
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
