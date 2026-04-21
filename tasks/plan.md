# Project Plan — David's Nutritional Log

## What This Project Is

A GitHub Pages site generated from daily JSON nutrition logs. A Python script
(`scripts/generate_site.py`) reads all entries and produces a static `site/index.html`,
which is deployed by a GitHub Actions workflow on every push to main.

---

## Architecture

```
data/entries/YYYY/MM/DD.json   ← daily logs (nutrition + exercise)
scripts/generate_site.py       ← builds site/index.html from all entries
.github/workflows/deploy-pages.yml  ← CI: runs generate_site.py, deploys to Pages
```

`site/` is gitignored — it is generated at deploy time, never committed.

---

## Daily Entry JSON Schema

```json
{
  "date": "2026-04-21",
  "timezone": "America/Los_Angeles",
  "breakfast": { "mealName": "", "calories": 0, "fat": 0, "protein": 0, "carbohydrates": 0, "fiber": 0 },
  "lunch":     { "mealName": "", "calories": 0, "fat": 0, "protein": 0, "carbohydrates": 0, "fiber": 0 },
  "dinner":    { "mealName": "", "calories": 0, "fat": 0, "protein": 0, "carbohydrates": 0, "fiber": 0 },
  "snacks": [
    { "mealName": "", "calories": 0, "fat": 0, "protein": 0, "carbohydrates": 0, "fiber": 0 }
  ],
  "exercise": [
    { "activity": "brisk walking", "durationMinutes": 35, "caloriesBurned": 194 }
  ],
  "exerciseTotal": { "caloriesBurned": 194 },
  "updatedAt": "2026-04-21T00:00:00Z",
  "dailyTotal": { "calories": 0, "fat": 0, "protein": 0, "carbohydrates": 0, "fiber": 0 }
}
```

**Exercise entries are written by an external OpenAI flow** — not by any script in this
repo. `generate_site.py` reads `exercise[]` and `exerciseTotal.caloriesBurned` directly.

---

## Daily Goals (David, 209 lbs / 5'7")

| Macro | Goal |
|---|---|
| Calories | 2487.1 kcal |
| Protein | 167.2 g |
| Fat | 83.0 g |
| Carbs | 268.0 g |

These are hardcoded in `generate_site.py` in the `GOALS` dict.

---

## Site Features

**Today tab**
- Macro summary cards (Calories In, Protein, Fat, Carbs, Fiber, Net Calories)
- Progress Toward Daily Goals — horizontal bar chart, % of goal, dashed goal line at 100%
- Meals table (Breakfast, Lunch, Dinner, Snacks)
- Exercise table (only rendered if `exercise[]` is non-empty)

**History tab**
- Daily Calories line chart — all entries, dots per day, hover shows all macros + burned/net
- Dashed red goal line at 2487.1 kcal
- All Entries table (Date, Calories In, Burned, Net, Protein, Fat, Carbs, Fiber)

---

## GitHub Actions

Triggers: push to main, `workflow_dispatch`, nightly cron at 06:00 UTC (11 PM PT).
Requires: GitHub Pages source set to "GitHub Actions" in repo settings.
No secrets needed — `generate_site.py` uses only stdlib.
