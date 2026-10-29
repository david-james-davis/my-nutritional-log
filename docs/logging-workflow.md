# Conversational food-logging workflow

Newt (and any other assistant logging meals in this repo) follows this workflow so daily entries stay consistent. This document describes how to log food. It does not change `scripts/generate_site.py` or existing entry files.

The live site is published from these entries: [https://david-james-davis.github.io/my-nutritional-log/](https://david-james-davis.github.io/my-nutritional-log/).

## Flow

1. The user says what they ate for **breakfast**, **lunch**, **snacks**, or **dinner**.
2. The assistant looks up **calories**, **fat**, **protein**, **carbohydrates**, and **fiber** for that food, using the source order below.
3. The assistant tells the user the source (what was used, and the portion assumption if any).
4. The assistant upserts that day's entry file and commits it.

Log only the meal the user described. Do not invent the other meals.

## Sources of truth

Use the first source that applies. Scale the published values to the portion the user described, and say the assumption in the reply (for example, "large egg = 50 g").

1. **Branded or packaged foods.** Use the brand's official nutrition facts label or the manufacturer site. Examples: Inked Keto bread, Wilde protein chips. Multiply the labeled serving by the number of servings eaten. Do not substitute a generic USDA match for a named packaged product.
2. **Generic whole foods.** Use [USDA FoodData Central](https://fdc.nal.usda.gov/). The search API is [`https://api.nal.usda.gov/fdc/v1/foods/search`](https://api.nal.usda.gov/fdc/v1/foods/search). Prefer **Foundation** data, then **SR Legacy**. When the result is per 100 g, multiply by `portion_grams / 100`. Name the food description and data type you used.
3. **Restaurant meals.** Use the restaurant's published nutrition info for the item as ordered. If the published entry depends on a size or modifier the user did not give, state the assumption (or ask) before writing the file.

If the preferred source is unavailable, say so and ask before using a lower-priority source. Do not copy numbers from the examples in this document; look them up.

Worked scaling only: a source lists values per 100 g, and the portion is one large egg at 50 g. Each macro logged for that egg is `published_per_100g * 50 / 100`, then rounded as below.

## Where the file lives

Path: `data/entries/YYYY/MM/DD.json`

`YYYY-MM-DD` is the calendar date in **America/Los_Angeles**, not UTC. A meal eaten at 11 pm Pacific still belongs to that Pacific date.

```text
data/entries/2026/10/29.json    ← date "2026-10-29"
```

## Schema

The field definitions and an example entry are in [tasks/plan.md](../tasks/plan.md) under **Daily Entry JSON Schema**.

Recent entries also include `waterOz` (fluid ounces of water). The plan example does not show it. It is written by an external flow, like `exercise` and `exerciseTotal`. Preserve it on update. On a brand-new file, initialize it to `0`.

Meal objects (`breakfast`, `lunch`, `dinner`, and each snack) use:

| Field | Meaning |
|---|---|
| `mealName` | What was eaten. Empty string if that slot has no food yet. |
| `calories` | Kilocalories, whole number. |
| `fat` | Grams. |
| `protein` | Grams. |
| `carbohydrates` | Grams. |
| `fiber` | Grams. |

`breakfast`, `lunch`, and `dinner` are single objects. `snacks` is an array of those objects (empty when there are no snacks).

`dailyTotal` has the same five macro fields and is the sum of breakfast, lunch, dinner, and every snack. It does not subtract exercise.

## Empty file

If `data/entries/YYYY/MM/DD.json` does not exist, create it from this empty template (the plan's sample exercise is an example of shape, not the contents of a new day):

```json
{
  "date": "YYYY-MM-DD",
  "timezone": "America/Los_Angeles",
  "breakfast": { "mealName": "", "calories": 0, "fat": 0, "protein": 0, "carbohydrates": 0, "fiber": 0 },
  "lunch": { "mealName": "", "calories": 0, "fat": 0, "protein": 0, "carbohydrates": 0, "fiber": 0 },
  "dinner": { "mealName": "", "calories": 0, "fat": 0, "protein": 0, "carbohydrates": 0, "fiber": 0 },
  "snacks": [],
  "exercise": [],
  "exerciseTotal": { "caloriesBurned": 0 },
  "updatedAt": "YYYY-MM-DDTHH:MM:SS-07:00",
  "dailyTotal": { "calories": 0, "fat": 0, "protein": 0, "carbohydrates": 0, "fiber": 0 },
  "waterOz": 0
}
```

Write JSON with a 2-space indent and a trailing newline, in the key order above. Inside a meal, use `mealName`, `calories`, `fat`, `protein`, `carbohydrates`, `fiber`.

If the file already exists and is missing `exercise`, `exerciseTotal`, or `waterOz` (the 2026-04-20 entry is like this), do not add them while logging food. Leave those keys absent.

## Upsert rules

Apply these on every food update:

- **Breakfast, lunch, and dinner** are one object each. When more food is added to a meal that already has a name, append `, ` and the new description to `mealName`, then add the new macros onto the existing ones. If `mealName` is still empty, set it to the new description with no leading comma.
- **Snacks** are an array. Append one new object per snack. Do not merge a new snack into an earlier snack object.
- If the user is correcting a slot rather than adding food, replace that meal object, or the matching snack object, instead of appending. Then recompute the total. Say which entry you replaced.
- **Do not modify `exercise`, `exerciseTotal`, or `waterOz`.** Those are written by an external flow. Copy them through unchanged, including key names (`activity` / `durationMinutes` and the alternate `activityName` / `durationMin` both already appear in the log).
- Recompute `dailyTotal` as the sum of `breakfast`, `lunch`, `dinner`, and every object in `snacks`, after those slots have been updated. Empty meals contribute zeros.
- Set `updatedAt` to the current America/Los_Angeles time as an ISO 8601 timestamp with a numeric Pacific offset: **-07:00** during PDT, **-08:00** during PST. Do not write a `Z` (UTC) suffix on a new update.

```python
from datetime import datetime
from zoneinfo import ZoneInfo

now = datetime.now(ZoneInfo("America/Los_Angeles"))
updated_at = now.isoformat(timespec="seconds")  # 2026-10-29T21:15:00-07:00
log_date = now.date().isoformat()
```

PDT (UTC−07:00) runs from the second Sunday in March until the first Sunday in November. PST (UTC−08:00) is the rest of the year. `ZoneInfo("America/Los_Angeles")` picks the offset.

### Rounding

After adding macros, store:

- **calories** rounded half-up to a whole number (write `490`, not `490.0`)
- **fat, protein, carbohydrates, and fiber** rounded half-up to 1 decimal place (write `6` when the value is whole, otherwise one decimal such as `9.3`)

Use half-up, not banker's rounding, so a trailing 5 rounds away from zero.

```python
from decimal import Decimal, ROUND_HALF_UP

def round_macro(value, places):
    quantum = Decimal("1") if places == 0 else Decimal("0.1")
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))
```

Round the meal or snack you just wrote, then set `dailyTotal` from the sum of the stored meal values and round that sum the same way. The stored total must match the sum of breakfast, lunch, dinner, and snacks within 0.1 on every macro.

## Commit message

Commit the entry file only (`site/` is generated and gitignored).

```text
log: 2026-10-29 breakfast
```

Use the Pacific date, then the slot: `breakfast`, `lunch`, `dinner`, or `snack`. When one commit updates several slots, list them: `log: 2026-10-29 breakfast, snack`.

## Check the file

`scripts/validate_entry.py` is a stdlib-only check. It confirms an entry matches this schema and that `dailyTotal` equals breakfast + lunch + dinner + snacks within 0.1 on each macro. It does not modify files.

```bash
python3 scripts/validate_entry.py                          # every file in data/entries
python3 scripts/validate_entry.py data/entries/2026/10/02.json
python3 scripts/validate_entry.py data/entries/2026/10     # a directory
```

The script exits `0` when every selected file passes. On failure it prints the path and the reason to stderr and exits `1`.

It requires `date` (`YYYY-MM-DD`, matching the path when the path is `.../YYYY/MM/DD.json`), `timezone` (`America/Los_Angeles`), breakfast/lunch/dinner objects, a `snacks` array, `updatedAt` (ISO 8601), and `dailyTotal`. Calories must be whole numbers. Other macros must be within one decimal place. `exercise`, `exerciseTotal`, and `waterOz` are optional; when present they must be the right types. Exercise items may use either `activity` + `durationMinutes` or `activityName` + `durationMin`, plus `caloriesBurned`.
