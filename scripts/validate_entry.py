#!/usr/bin/env python3
"""Validate daily nutrition log entries.

Checks that a file matches the entry schema documented in tasks/plan.md and
docs/logging-workflow.md, and that dailyTotal equals breakfast + lunch +
dinner + snacks within 0.1 on each macro.

Usage:
  python3 scripts/validate_entry.py [PATH ...]

With no PATH, validates every JSON file under data/entries/. A PATH may be
a file or a directory. Exits 0 when every file passes, and 1 with a message
on stderr when any file fails. Does not modify files.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENTRIES_DIR = ROOT / "data" / "entries"

MACRO_KEYS = ("calories", "fat", "protein", "carbohydrates", "fiber")
MEAL_KEYS = ("mealName",) + MACRO_KEYS
REQUIRED_TOP = (
    "date",
    "timezone",
    "breakfast",
    "lunch",
    "dinner",
    "snacks",
    "updatedAt",
    "dailyTotal",
)
OPTIONAL_TOP = ("exercise", "exerciseTotal", "waterOz")
TOLERANCE = 0.1
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ENTRY_PATH_RE = re.compile(r"(\d{4})/(\d{2})/(\d{2})\.json$")


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def fmt_num(value):
    rounded = round(value)
    if abs(value - rounded) < 1e-9:
        return str(int(rounded))
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text


def at_most_one_decimal(value):
    return abs(value * 10 - round(value * 10)) < 1e-6


def is_whole(value):
    return abs(value - round(value)) < 1e-6


def parse_iso(value):
    if not isinstance(value, str) or not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def rel_path(path):
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def check_macro_value(value, key, label, errors):
    if not is_number(value):
        errors.append(f"{label}.{key} must be a number")
        return
    if value < 0:
        errors.append(f"{label}.{key} must be >= 0")
        return
    if key == "calories":
        if not is_whole(value):
            errors.append(f"{label}.calories must be a whole number (got {fmt_num(value)})")
    elif not at_most_one_decimal(value):
        errors.append(f"{label}.{key} must have at most 1 decimal place (got {fmt_num(value)})")


def check_meal(meal, label, errors):
    if not isinstance(meal, dict):
        errors.append(f"{label} must be an object")
        return False
    extra = sorted(set(meal) - set(MEAL_KEYS))
    if extra:
        errors.append(f"{label} has unexpected keys: {', '.join(extra)}")
    if "mealName" not in meal or not isinstance(meal.get("mealName"), str):
        errors.append(f"{label}.mealName must be a string")
    ok = True
    for key in MACRO_KEYS:
        if key not in meal:
            errors.append(f"{label}.{key} is required")
            ok = False
        else:
            before = len(errors)
            check_macro_value(meal[key], key, label, errors)
            if len(errors) != before:
                ok = False
    return ok


def check_exercise_item(item, label, errors):
    if not isinstance(item, dict):
        errors.append(f"{label} must be an object")
        return
    activity = item.get("activity", item.get("activityName"))
    if not isinstance(activity, str):
        errors.append(f"{label} needs activity or activityName as a string")
    if "durationMinutes" in item:
        duration = item["durationMinutes"]
    elif "durationMin" in item:
        duration = item["durationMin"]
    else:
        duration = None
    if not is_number(duration):
        errors.append(f"{label} needs durationMinutes or durationMin as a number")
    elif duration < 0:
        errors.append(f"{label} duration must be >= 0")
    burned = item.get("caloriesBurned")
    if not is_number(burned):
        errors.append(f"{label}.caloriesBurned must be a number")
    elif burned < 0:
        errors.append(f"{label}.caloriesBurned must be >= 0")


def check_totals(data, errors):
    """Append an error when dailyTotal disagrees with the sum of meals and snacks."""
    meals_ok = all(isinstance(data.get(name), dict) for name in ("breakfast", "lunch", "dinner"))
    snacks = data.get("snacks")
    snacks_ok = isinstance(snacks, list) and all(isinstance(item, dict) for item in snacks)
    total = data.get("dailyTotal")
    total_ok = isinstance(total, dict)
    if not (meals_ok and snacks_ok and total_ok):
        return
    for key in MACRO_KEYS:
        parts = [data["breakfast"], data["lunch"], data["dinner"], *snacks]
        if any(not is_number(part.get(key)) for part in parts):
            continue
        if not is_number(total.get(key)):
            continue
        expected = sum(float(part[key]) for part in parts)
        actual = float(total[key])
        # 1e-6 absorbs binary float noise so a true 0.1 gap still passes.
        if abs(actual - expected) > TOLERANCE + 1e-6:
            errors.append(
                f"dailyTotal.{key} is {fmt_num(actual)} but breakfast + lunch + dinner "
                f"+ snacks sum to {fmt_num(expected)} "
                f"(difference {fmt_num(abs(actual - expected))}, tolerance {fmt_num(TOLERANCE)})"
            )


def validate_entry(data, path):
    errors = []
    if not isinstance(data, dict):
        return ["entry must be a JSON object"]

    missing = [key for key in REQUIRED_TOP if key not in data]
    if missing:
        errors.append("missing keys: " + ", ".join(missing))
    extra = sorted(set(data) - set(REQUIRED_TOP) - set(OPTIONAL_TOP))
    if extra:
        errors.append("unexpected keys: " + ", ".join(extra))

    date = data.get("date")
    if not isinstance(date, str) or not DATE_RE.match(date or ""):
        errors.append("date must be YYYY-MM-DD")
    else:
        match = ENTRY_PATH_RE.search(path.as_posix())
        if match:
            expected = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
            if date != expected:
                errors.append(f"date is {date} but path is {expected}")

    if data.get("timezone") != "America/Los_Angeles":
        errors.append('timezone must be "America/Los_Angeles"')

    for name in ("breakfast", "lunch", "dinner"):
        if name in data:
            check_meal(data[name], name, errors)

    snacks = data.get("snacks")
    if "snacks" in data:
        if not isinstance(snacks, list):
            errors.append("snacks must be an array")
        else:
            for index, snack in enumerate(snacks):
                check_meal(snack, f"snacks[{index}]", errors)

    if "dailyTotal" in data:
        total = data["dailyTotal"]
        if not isinstance(total, dict):
            errors.append("dailyTotal must be an object")
        else:
            extra_total = sorted(set(total) - set(MACRO_KEYS))
            if extra_total:
                errors.append("dailyTotal has unexpected keys: " + ", ".join(extra_total))
            for key in MACRO_KEYS:
                if key not in total:
                    errors.append(f"dailyTotal.{key} is required")
                else:
                    check_macro_value(total[key], key, "dailyTotal", errors)

    if "updatedAt" in data and not parse_iso(data.get("updatedAt")):
        errors.append("updatedAt must be an ISO 8601 timestamp")

    if "waterOz" in data:
        water = data["waterOz"]
        if not is_number(water):
            errors.append("waterOz must be a number")
        elif water < 0:
            errors.append("waterOz must be >= 0")

    if "exercise" in data:
        exercise = data["exercise"]
        if not isinstance(exercise, list):
            errors.append("exercise must be an array")
        else:
            for index, item in enumerate(exercise):
                check_exercise_item(item, f"exercise[{index}]", errors)

    if "exerciseTotal" in data:
        exercise_total = data["exerciseTotal"]
        if not isinstance(exercise_total, dict):
            errors.append("exerciseTotal must be an object")
        else:
            burned = exercise_total.get("caloriesBurned")
            if not is_number(burned):
                errors.append("exerciseTotal.caloriesBurned must be a number")
            elif burned < 0:
                errors.append("exerciseTotal.caloriesBurned must be >= 0")

    check_totals(data, errors)
    return errors


def load_entry(path):
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle), None
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"
    except OSError as exc:
        return None, f"could not read file: {exc}"


def collect_paths(args):
    """Return (files, setup_errors)."""
    if not args:
        if not ENTRIES_DIR.is_dir():
            return [], [f"entries directory not found: {ENTRIES_DIR}"]
        files = sorted(ENTRIES_DIR.rglob("*.json"))
        if not files:
            return [], [f"no JSON files under {rel_path(ENTRIES_DIR)}"]
        return files, []

    files = []
    errors = []
    for raw in args:
        path = Path(raw)
        if not path.is_absolute():
            path = Path.cwd() / path
        if path.is_dir():
            found = sorted(path.rglob("*.json"))
            if not found:
                errors.append(f"no JSON files under {raw}")
            files.extend(found)
        elif path.is_file():
            files.append(path)
        else:
            errors.append(f"path not found: {raw}")
    return files, errors


def main(argv):
    files, setup_errors = collect_paths(argv)
    failures = list(setup_errors)
    passed = 0

    for path in files:
        data, load_error = load_entry(path)
        if load_error:
            failures.append(f"{rel_path(path)}: {load_error}")
            continue
        errors = validate_entry(data, path)
        if errors:
            details = "\n".join(f"  {error}" for error in errors)
            failures.append(f"{rel_path(path)}:\n{details}")
        else:
            passed += 1

    if failures:
        summary = f"{len(failures)} failed, {passed} passed"
        print("\n".join(failures), file=sys.stderr)
        print(summary, file=sys.stderr)
        return 1

    print(f"{passed} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
