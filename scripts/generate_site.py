#!/usr/bin/env python3
"""Generate a static GitHub Pages site from nutritional log JSON entries."""

import json
import struct
import zlib
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
    "protein": 209.0,
    "fat": 83.0,
    "carbs": 268.0,
}

WEIGHT_LBS = 209

BODY_STATS = {
    "current_weight_lbs": 209,
    "current_bf_pct": 22,
    "goal_weight_lbs": 185,
    "goal_bf_pct": 12,
    "start_weight_lbs": 209,  # update if you want progress bar to reflect a higher starting point
}

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def calc_water_oz(entry):
    """Base 0.5 oz/lb + 16 oz per 30 min of exercise logged."""
    base = WEIGHT_LBS * 0.5
    total_minutes = sum(a.get("durationMinutes", 0) for a in entry.get("exercise", []))
    bonus = (total_minutes / 30) * 16
    return round(base + bonus)


def build_chart_data(entries):
    """Return all_days dict for the history line chart."""
    all_days = {"labels": [], "calories": [], "protein": [], "fat": [], "carbs": [], "fiber": [], "burned": [], "net": []}
    for e in entries:
        total = e.get("dailyTotal", {})
        cals = total.get("calories", 0)
        burned = e.get("exerciseTotal", {}).get("caloriesBurned", 0)
        all_days["labels"].append(e["date"])
        all_days["calories"].append(cals)
        all_days["protein"].append(total.get("protein", 0))
        all_days["fat"].append(total.get("fat", 0))
        all_days["carbs"].append(total.get("carbohydrates", 0))
        all_days["fiber"].append(total.get("fiber", 0))
        all_days["burned"].append(burned)
        all_days["net"].append(cals - burned)
    return all_days


def exercise_rows(activities):
    rows = ""
    for a in activities:
        name = a.get("activity", "")
        if not name:
            continue
        rows += f"""
        <tr>
          <td class="meal-label">{name.title()}</td>
          <td>{a.get('durationMinutes', 0)} min</td>
          <td>{fmt_num(a.get('caloriesBurned', 0), 'kcal')}</td>
        </tr>"""
    return rows


def render_today_tab(entry, is_today):
    dt = entry["date"]
    total = entry.get("dailyTotal", {})
    cals = total.get("calories", 0)
    protein = total.get("protein", 0)
    fat = total.get("fat", 0)
    carbs = total.get("carbohydrates", 0)
    fiber = total.get("fiber", 0)

    activities = entry.get("exercise", [])
    burned = entry.get("exerciseTotal", {}).get("caloriesBurned", 0)
    net = cals - burned

    meal_rows = ""
    for label, key in [("Breakfast", "breakfast"), ("Lunch", "lunch"), ("Dinner", "dinner")]:
        meal = entry.get(key, {})
        if meal:
            meal_rows += meal_row(label, meal)
    for i, snack in enumerate(entry.get("snacks", []), 1):
        label = "Snack" if len(entry.get("snacks", [])) == 1 else f"Snack {i}"
        meal_rows += meal_row(label, snack)

    net_color = "#27ae60" if net <= GOALS["calories"] else "#e74c3c"

    recommended_oz = calc_water_oz(entry)
    recommended_l = round(recommended_oz * 0.0296, 1)
    logged_oz = entry.get("waterOz")
    if logged_oz:
        water_pct = min(round(logged_oz / recommended_oz * 100), 100)
        water_status = f"{logged_oz} oz of {recommended_oz} oz ({water_pct}%)"
        water_bar = f"""
        <div class="water-bar-track">
          <div class="water-bar-fill" style="width:{water_pct}%"></div>
        </div>"""
    else:
        water_status = f"Target: {recommended_oz} oz ({recommended_l} L)"
        water_bar = ""

    water_card = f"""
      <div class="water-card">
        <span class="water-icon">~</span>
        <div class="water-info">
          <div class="water-title">Water Intake</div>
          <div class="water-status">{water_status}</div>
          {water_bar}
        </div>
      </div>"""

    exercise_section = ""
    if activities:
        ex_rows = exercise_rows(activities)
        exercise_section = f"""
      <h3>Exercise</h3>
      <div class="table-wrap" style="margin-bottom:1.5rem">
        <table>
          <thead>
            <tr><th>Activity</th><th>Duration</th><th>Calories Burned</th></tr>
          </thead>
          <tbody>
            {ex_rows}
            <tr class="total-row">
              <td colspan="2"><strong>Total Burned</strong></td>
              <td><strong>{fmt_num(burned, 'kcal')}</strong></td>
            </tr>
          </tbody>
        </table>
      </div>"""

    return f"""
      <div class="date-header">
        <h2>{dt}</h2>
        {'<span class="badge">Today</span>' if is_today else f'<span class="badge badge-stale">Last logged: {dt}</span>'}
      </div>
      <div class="macro-grid">
        {macro_card("Calories In", cals, "kcal", "#e67e22")}
        {macro_card("Protein", protein, "g", "#2980b9")}
        {macro_card("Fat", fat, "g", "#8e44ad")}
        {macro_card("Carbs", carbs, "g", "#27ae60")}
        {macro_card("Fiber", fiber, "g", "#16a085")}
        <div class="net-cal-card" style="background:{net_color}; color:#fff">
          <div class="net-cal-label">Net Calories</div>
          <div class="net-cal-value">{net:g}<span class="net-cal-unit">kcal</span></div>
          <div class="net-cal-sub">{fmt_num(cals, 'kcal')} in &minus; {fmt_num(burned, 'kcal')} burned</div>
        </div>

      </div>

      {water_card}

      <div class="chart-section">
        <h3>Progress Toward Daily Goals</h3>
        <div class="chart-wrap" style="height:200px"><canvas id="chartGoals"></canvas></div>
      </div>

      <h3>Meals</h3>
      <div class="table-wrap" style="margin-bottom:1.5rem">
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
      </div>
      {exercise_section}"""


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
        burned = e.get("exerciseTotal", {}).get("caloriesBurned", 0)
        net = cals - burned
        rows += f"""
          <tr>
            <td>{dt}</td>
            <td>{fmt_num(cals, 'kcal')}</td>
            <td>{fmt_num(burned, 'kcal')}</td>
            <td>{fmt_num(net, 'kcal')}</td>
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
              <th>Date</th><th>Calories In</th><th>Burned</th><th>Net</th>
              <th>Protein</th><th>Fat</th><th>Carbs</th><th>Fiber</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
      </div>"""


def render_goals_tab():
    cw = BODY_STATS["current_weight_lbs"]
    cbf = BODY_STATS["current_bf_pct"]
    gw = BODY_STATS["goal_weight_lbs"]
    gbf = BODY_STATS["goal_bf_pct"]
    sw = BODY_STATS["start_weight_lbs"]

    c_fat = round(cw * cbf / 100)
    c_lean = cw - c_fat
    g_fat = round(gw * gbf / 100)
    g_lean = gw - g_fat

    lbs_to_go = cw - gw
    weight_progress = max(0, min(100, round((sw - cw) / (sw - gw) * 100))) if sw != gw else 100
    progress_color = "#27ae60" if weight_progress >= 50 else "#e67e22"

    water_oz = round(WEIGHT_LBS * 0.5)

    def stat_card(label, value, sub="", color="#2c3e50"):
        sub_html = f'<div class="goals-stat-sub">{sub}</div>' if sub else ""
        return f"""
        <div class="goals-stat-card" style="border-top: 4px solid {color}">
          <div class="goals-stat-value">{value}</div>
          <div class="goals-stat-label">{label}</div>
          {sub_html}
        </div>"""

    return f"""
      <h2>My Goals</h2>

      <div class="chart-section">
        <h3>Body Composition</h3>
        <div class="goals-two-col">
          <div>
            <div class="goals-col-heading">Current</div>
            <div class="goals-stat-grid">
              {stat_card("Weight", f"{cw} lbs", color="#e67e22")}
              {stat_card("Body Fat", f"{cbf}%", f"{c_fat} lbs fat", color="#e74c3c")}
              {stat_card("Lean Mass", f"{c_lean} lbs", color="#2980b9")}
            </div>
          </div>
          <div>
            <div class="goals-col-heading">Goal</div>
            <div class="goals-stat-grid">
              {stat_card("Weight", f"{gw} lbs", color="#27ae60")}
              {stat_card("Body Fat", f"{gbf}%", f"{g_fat} lbs fat", color="#27ae60")}
              {stat_card("Lean Mass", f"{g_lean} lbs", color="#2980b9")}
            </div>
          </div>
        </div>

        <div class="goals-progress-section">
          <div class="goals-progress-label">
            <span>Weight Progress</span>
            <span>{cw} lbs &rarr; {gw} lbs &nbsp;&bull;&nbsp; {lbs_to_go} lbs to go</span>
          </div>
          <div class="goals-progress-track">
            <div class="goals-progress-fill" style="width:{weight_progress}%; background:{progress_color}"></div>
          </div>
          <div class="goals-progress-pct">{weight_progress}% of the way there</div>
        </div>
      </div>

      <div class="chart-section">
        <h3>Daily Nutrition Targets</h3>
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th>Macro</th><th>Daily Goal</th><th>Notes</th></tr>
            </thead>
            <tbody>
              <tr><td class="meal-label">Calories</td><td>{GOALS['calories']:g} kcal</td><td>Moderate deficit for recomp</td></tr>
              <tr><td class="meal-label">Protein</td><td>{GOALS['protein']:g} g</td><td>1 g per lb of bodyweight</td></tr>
              <tr><td class="meal-label">Fat</td><td>{GOALS['fat']:g} g</td><td>~30% of calories</td></tr>
              <tr><td class="meal-label">Carbohydrates</td><td>{GOALS['carbs']:g} g</td><td>~43% of calories</td></tr>
              <tr><td class="meal-label">Water</td><td>{water_oz} oz ({round(water_oz * 0.0296, 1)} L)</td><td>~0.5 oz per lb of bodyweight</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="chart-section">
        <h3>Approach</h3>
        <ul class="goals-approach-list">
          <li>Body recomposition — losing fat while preserving and building muscle</li>
          <li>Resistance training + creatine supplementation</li>
          <li>High protein intake (1 g/lb) to protect lean mass during deficit</li>
          <li>Target: {gbf}% body fat at {gw} lbs (athletic range for age 43)</li>
        </ul>
      </div>"""


def generate_html(entries):
    featured, is_today = load_featured_entry(entries)
    today_content = render_today_tab(featured, is_today)
    history_content = render_history_tab(entries)
    goals_content = render_goals_tab()
    all_days = build_chart_data(entries)
    all_days_json = json.dumps(all_days)
    goals_json = json.dumps(GOALS)

    ft = featured.get("dailyTotal", {})
    burned = featured.get("exerciseTotal", {}).get("caloriesBurned", 0)
    featured_totals_json = json.dumps({
        "calories": ft.get("calories", 0),
        "protein":  ft.get("protein", 0),
        "fat":      ft.get("fat", 0),
        "carbs":    ft.get("carbohydrates", 0),
        "burned":   burned,
        "net":      ft.get("calories", 0) - burned,
    })

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>David's Nutritional Log</title>
  <link rel="manifest" href="manifest.json">
  <meta name="theme-color" content="#2c3e50">
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-title" content="Nutrition Log">
  <link rel="apple-touch-icon" href="icons/icon-192.png">
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
    .net-cal-card {{ border-radius: 10px; padding: 1.25rem 1rem; text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,0.12); }}
    .net-cal-label {{ font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem; opacity: 0.85; }}
    .net-cal-value {{ font-size: 2rem; font-weight: 800; line-height: 1; }}
    .net-cal-unit {{ font-size: 0.8rem; font-weight: 400; margin-left: 2px; opacity: 0.75; }}
    .net-cal-sub {{ font-size: 0.7rem; opacity: 0.7; margin-top: 0.35rem; }}
    .water-card {{ display: flex; align-items: center; gap: 1rem; background: #fff; border-radius: 10px; padding: 1rem 1.25rem; margin-bottom: 1.5rem; box-shadow: 0 1px 4px rgba(0,0,0,0.08); border-left: 4px solid #3498db; }}
    .water-icon {{ font-size: 1.5rem; color: #3498db; font-weight: 700; }}
    .water-title {{ font-size: 0.75rem; font-weight: 600; color: #555; text-transform: uppercase; letter-spacing: 0.06em; }}
    .water-status {{ font-size: 1rem; font-weight: 600; color: #2c3e50; margin-top: 0.2rem; }}
    .water-bar-track {{ height: 6px; background: #e0f0fb; border-radius: 999px; margin-top: 0.5rem; width: min(200px, 100%); }}
    @media (max-width: 600px) {{
      header {{ padding: 1rem; }}
      .tabs {{ padding: 0; overflow-x: auto; }}
      .tab-btn {{ padding: 0.75rem 1rem; font-size: 0.85rem; white-space: nowrap; }}
      .tab-panel {{ padding: 1rem; }}
      .macro-value {{ font-size: 1.5rem; }}
      .chart-wrap {{ height: 220px !important; }}
      .water-card {{ flex-direction: column; align-items: flex-start; gap: 0.5rem; }}
    }}
    .water-bar-fill {{ height: 100%; background: #3498db; border-radius: 999px; }}
    .goals-two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 1.5rem; }}
    .goals-col-heading {{ font-size: 0.8rem; font-weight: 700; color: #888; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.6rem; }}
    .goals-stat-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.75rem; }}
    .goals-stat-card {{ background: #f7f9fc; border-radius: 8px; padding: 0.9rem 0.75rem; text-align: center; }}
    .goals-stat-value {{ font-size: 1.4rem; font-weight: 700; line-height: 1; color: #2c3e50; }}
    .goals-stat-label {{ font-size: 0.7rem; color: #888; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 0.35rem; }}
    .goals-stat-sub {{ font-size: 0.7rem; color: #aaa; margin-top: 0.2rem; }}
    .goals-progress-section {{ margin-top: 0.5rem; }}
    .goals-progress-label {{ display: flex; justify-content: space-between; font-size: 0.8rem; color: #555; margin-bottom: 0.4rem; }}
    .goals-progress-track {{ height: 10px; background: #e0e0e0; border-radius: 999px; overflow: hidden; }}
    .goals-progress-fill {{ height: 100%; border-radius: 999px; transition: width 0.3s; }}
    .goals-progress-pct {{ font-size: 0.75rem; color: #888; margin-top: 0.35rem; text-align: right; }}
    .goals-approach-list {{ list-style: none; padding: 0; }}
    .goals-approach-list li {{ padding: 0.5rem 0; border-bottom: 1px solid #f0f0f0; font-size: 0.9rem; color: #444; padding-left: 1.2rem; position: relative; }}
    .goals-approach-list li::before {{ content: "→"; position: absolute; left: 0; color: #27ae60; font-weight: 700; }}
    .goals-approach-list li:last-child {{ border-bottom: none; }}
    @media (max-width: 600px) {{
      .goals-two-col {{ grid-template-columns: 1fr; gap: 1rem; }}
      .goals-stat-grid {{ grid-template-columns: repeat(3, 1fr); gap: 0.5rem; }}
      .goals-stat-value {{ font-size: 1.1rem; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>David's Nutritional Log</h1>
    <p>Personal daily nutrition tracker</p>
  </header>

  <div class="tabs">
    <button class="tab-btn active" onclick="showTab('today', this)">Today</button>
    <button class="tab-btn" onclick="showTab('history', this)">History</button>
    <button class="tab-btn" onclick="showTab('goals', this)">Goals</button>
  </div>

  <div id="tab-today" class="tab-panel active">
    {today_content}
  </div>

  <div id="tab-history" class="tab-panel">
    {history_content}
  </div>

  <div id="tab-goals" class="tab-panel">
    {goals_content}
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
                const lines = [
                  ` Protein: ${{allDays.protein[i]}}g`,
                  ` Fat: ${{allDays.fat[i]}}g`,
                  ` Carbs: ${{allDays.carbs[i]}}g`,
                  ` Fiber: ${{allDays.fiber[i]}}g`,
                ];
                if (allDays.burned[i]) {{
                  lines.push(``, ` Burned: ${{allDays.burned[i]}} kcal`, ` Net: ${{allDays.net[i]}} kcal`);
                }}
                return lines;
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
      {{ key: 'net',     label: 'Net Calories', unit: 'kcal', color: '#e67e22' }},
      {{ key: 'protein', label: 'Protein',       unit: 'g',    color: '#2980b9' }},
      {{ key: 'fat',     label: 'Fat',           unit: 'g',    color: '#8e44ad' }},
      {{ key: 'carbs',   label: 'Carbs',         unit: 'g',    color: '#27ae60' }},
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
        ctx.fillText('Goal', xPx, y.top + 14);
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
            const goalKey = m.key === 'net' ? 'calories' : m.key;
            const goal = GOALS[goalKey];
            return goal ? Math.round((featuredTotals[m.key] / goal) * 1000) / 10 : 0;
          }}),
          backgroundColor: goalItems.map(m => {{
            const goalKey = m.key === 'net' ? 'calories' : m.key;
            const pct = featuredTotals[m.key] / GOALS[goalKey] * 100;
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
                const goalKey = m.key === 'net' ? 'calories' : m.key;
                const goal = GOALS[goalKey];
                const suffix = m.key === 'net' ? ` (in: ${{featuredTotals.calories}}, burned: ${{featuredTotals.burned}})` : '';
                return ` ${{actual}}${{m.unit}} of ${{goal}}${{m.unit}} (${{ctx.parsed.x}}%)${{suffix}}`;
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

    if ('serviceWorker' in navigator) {{
      navigator.serviceWorker.register('./sw.js');
    }}
  </script>
</body>
</html>"""


def make_icon_png(size):
    BG = (39, 174, 96)   # #27ae60 green
    FG = (255, 255, 255)  # white

    # 5-wide × 7-tall bitmap for the letter "D"
    LETTER_D = [
        [1, 1, 1, 1, 0],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [1, 1, 1, 1, 0],
    ]

    scale = size // 12
    lw, lh = 5 * scale, 7 * scale
    ox, oy = (size - lw) // 2, (size - lh) // 2

    pixels = [[BG] * size for _ in range(size)]
    for ri, row in enumerate(LETTER_D):
        for ci, bit in enumerate(row):
            if bit:
                for dy in range(scale):
                    for dx in range(scale):
                        y, x = oy + ri * scale + dy, ox + ci * scale + dx
                        if 0 <= y < size and 0 <= x < size:
                            pixels[y][x] = FG

    raw = b"".join(b"\x00" + b"".join(bytes(p) for p in row) for row in pixels)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def make_manifest():
    return json.dumps({
        "name": "David's Nutritional Log",
        "short_name": "Nutrition Log",
        "description": "Personal daily nutrition and exercise tracker",
        "start_url": "./",
        "display": "standalone",
        "background_color": "#f5f7fa",
        "theme_color": "#2c3e50",
        "icons": [
            {"src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ],
    }, indent=2)


def make_sw():
    return """\
const CACHE = 'nutritional-log-v1';

self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ));
  self.clients.claim();
});

// Network-first: always try to fetch fresh, fall back to cache when offline
self.addEventListener('fetch', e => {
  e.respondWith(
    fetch(e.request)
      .then(response => {
        const copy = response.clone();
        caches.open(CACHE).then(c => c.put(e.request, copy));
        return response;
      })
      .catch(() => caches.match(e.request))
  );
});
"""


def main():
    entries = load_all_entries()
    if not entries:
        raise SystemExit("No entries found in data/entries/")

    OUTPUT_DIR.mkdir(exist_ok=True)

    # PWA assets
    icons_dir = OUTPUT_DIR / "icons"
    icons_dir.mkdir(exist_ok=True)
    (icons_dir / "icon-192.png").write_bytes(make_icon_png(192))
    (icons_dir / "icon-512.png").write_bytes(make_icon_png(512))
    (OUTPUT_DIR / "manifest.json").write_text(make_manifest())
    (OUTPUT_DIR / "sw.js").write_text(make_sw())

    html = generate_html(entries)
    output_file = OUTPUT_DIR / "index.html"
    output_file.write_text(html)
    print(f"Generated {output_file} ({len(entries)} entries, latest: {entries[-1]['date']})")


if __name__ == "__main__":
    main()
