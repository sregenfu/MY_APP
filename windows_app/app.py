import base64
import json
from datetime import date, datetime, timedelta
from pathlib import Path
import math
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

import pandas as pd
import streamlit as st

APP_TITLE = "MeinTagebuch"
DATA_DIR = Path(__file__).parent / "data"
DATA_FILE = DATA_DIR / "store.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_PROFILE = {
    "name": "",
    "gender": "Weiblich",
    "birth_date": "1996-01-01",
    "height": 170.0,
    "start_weight": 80.0,
    "current_weight": 80.0,
    "goal_weight": 70.0,
    "activity_level": "Wenig Bewegung",
    "weight_goal": "Abnehmen",
    "plan": "Ausgewogen",
    "weigh_day": "Montag",
    "activity_extra_mode": "Erst Wochenextra und dann Aktivitätspunkte",
}

ALLOWED_GENDERS = ["Weiblich", "Männlich"]
ALLOWED_ACTIVITY_LEVELS = ["Kaum Bewegung", "Wenig Bewegung", "Viel Bewegung", "Täglich viel Bewegung"]
ALLOWED_WEIGHT_GOALS = ["Abnehmen", "Gewicht halten"]
ALLOWED_PLANS = ["Restriktiv", "Ausgewogen", "Liberal"]
ALLOWED_ACTIVITY_EXTRA_MODES = [
    "Erst Wochenextra und dann Aktivitätspunkte",
    "Aktivitätspunkte nicht benutzen",
]


def sanitize_profile_data(raw: dict) -> dict:
    """Validiert importierte Profildaten und setzt fehlende/ungültige Werte auf Defaults."""
    if not isinstance(raw, dict):
        raw = {}

    profile = DEFAULT_PROFILE.copy()

    profile["name"] = str(raw.get("name", profile["name"]))[:120]

    gender = str(raw.get("gender", profile["gender"]))
    profile["gender"] = gender if gender in ALLOWED_GENDERS else DEFAULT_PROFILE["gender"]

    birth_date = str(raw.get("birth_date", profile["birth_date"]))
    try:
        datetime.strptime(birth_date, "%Y-%m-%d")
        profile["birth_date"] = birth_date
    except ValueError:
        profile["birth_date"] = DEFAULT_PROFILE["birth_date"]

    def _bounded_float(value, default_value: float, min_value: float, max_value: float) -> float:
        try:
            fval = float(value)
        except (TypeError, ValueError):
            fval = default_value
        return max(min_value, min(max_value, fval))

    profile["height"] = _bounded_float(raw.get("height", profile["height"]), DEFAULT_PROFILE["height"], 120.0, 230.0)
    profile["start_weight"] = _bounded_float(raw.get("start_weight", profile["start_weight"]), DEFAULT_PROFILE["start_weight"], 30.0, 300.0)
    profile["current_weight"] = _bounded_float(raw.get("current_weight", profile["current_weight"]), DEFAULT_PROFILE["current_weight"], 30.0, 300.0)
    profile["goal_weight"] = _bounded_float(raw.get("goal_weight", profile["goal_weight"]), DEFAULT_PROFILE["goal_weight"], 30.0, 300.0)

    activity_level = str(raw.get("activity_level", profile["activity_level"]))
    profile["activity_level"] = activity_level if activity_level in ALLOWED_ACTIVITY_LEVELS else DEFAULT_PROFILE["activity_level"]

    weight_goal = str(raw.get("weight_goal", profile["weight_goal"]))
    profile["weight_goal"] = weight_goal if weight_goal in ALLOWED_WEIGHT_GOALS else DEFAULT_PROFILE["weight_goal"]

    plan = str(raw.get("plan", profile["plan"]))
    profile["plan"] = plan if plan in ALLOWED_PLANS else DEFAULT_PROFILE["plan"]

    weigh_day = str(raw.get("weigh_day", profile["weigh_day"]))
    profile["weigh_day"] = weigh_day if weigh_day in WEIGH_DAYS else DEFAULT_PROFILE["weigh_day"]

    activity_extra_mode = str(raw.get("activity_extra_mode", profile["activity_extra_mode"]))
    profile["activity_extra_mode"] = (
        activity_extra_mode
        if activity_extra_mode in ALLOWED_ACTIVITY_EXTRA_MODES
        else DEFAULT_PROFILE["activity_extra_mode"]
    )

    return profile


def load_foods_from_file() -> list:
    """Parse ww_vorlage.txt to load all foods with estimated nutrition data."""
    try:
        # Try multiple paths to find ww_vorlage.txt
        possible_paths = [
            Path(__file__).parent.parent / "ww_vorlage.txt",
            Path(r"c:\Users\A302711\Github Copilot Test\MY_APP\ww_vorlage.txt"),
            Path.cwd().parent / "ww_vorlage.txt",
        ]
        
        vorlage_path = None
        for path in possible_paths:
            if path.exists():
                vorlage_path = path
                break
        
        if vorlage_path is None:
            return list(DEFAULT_FOODS_HARDCODED)
        
        foods = []
        with open(vorlage_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Categories with their nutrition profiles (kcal, fat, sugar, protein per 100g)
        cat_profiles = {
            "Obst": (50, 0.3, 12, 0.5),
            "Gemüse": (30, 0.2, 3, 2),
            "Hülsenfrüchte": (100, 0.5, 0, 8),
            "Kartoffeln": (77, 0.1, 1.7, 2),
            "Getreide": (350, 1.5, 70, 12),
            "Brot": (230, 2, 4, 8),
            "Nüsse": (600, 60, 10, 20),
            "Öle": (900, 100, 0, 0),
            "Milch": (65, 1, 5, 3),
            "Joghurt": (75, 1.5, 4, 3),
            "Käse": (350, 25, 1, 25),
            "Eier": (150, 11, 1, 13),
            "Fleisch": (165, 6, 0, 26),
            "Geflügel": (120, 2, 0, 24),
            "Fisch": (150, 5, 0, 22),
            "Meeresfrüchte": (90, 0.5, 0, 18),
            "Vegetarische": (150, 3, 2, 15),
            "Getränke": (30, 0, 7, 0),
            "Gewürze": (200, 5, 10, 6),
        }
        
        # Parse lines with format: "Kategorie: item1, item2, ..."
        for line in content.split("\n"):
            line = line.strip()
            if not line or ":" not in line:
                continue
            
            parts = line.split(":", 1)
            if len(parts) != 2:
                continue
            
            cat_raw = parts[0].strip()
            items_str = parts[1].strip()
            
            # Simplify category name (remove extra descriptions)
            category = cat_raw.split("(")[0].strip() if "(" in cat_raw else cat_raw
            if not category:
                continue
            
            # Find matching profile
            profile = None
            for key in cat_profiles:
                if key.lower() in cat_raw.lower():
                    profile = cat_profiles[key]
                    break
            if not profile:
                profile = (50, 0.3, 5, 2)  # default
            
            kcal, fat, sugar, protein = profile
            items = [item.strip() for item in items_str.split(",") if item.strip()]
            
            for item_name in items:
                pts = math.ceil((kcal * 0.0305 + fat * 0.275 + sugar * 0.12 - protein * 0.098) * 2) / 2
                foods.append({
                    "name": item_name,
                    "category": category,
                    "portion_g": 100.0,
                    "kcal": float(kcal),
                    "fat": float(fat),
                    "sat_fat": float(fat * 0.4),
                    "sugar": float(sugar),
                    "protein": float(protein),
                    "points": float(max(0, pts)),
                    "zr": kcal < 80,
                    "zb": kcal < 100,
                    "zl": True,
                })
        
        return foods if foods else list(DEFAULT_FOODS_HARDCODED)
    except Exception:
        return list(DEFAULT_FOODS_HARDCODED)


DEFAULT_FOODS_HARDCODED = [
    {"name": "Apfel", "category": "Obst", "portion_g": 100.0, "kcal": 52.0, "fat": 0.2, "sat_fat": 0.0, "sugar": 10.0, "protein": 0.3, "points": 1.0, "zr": True, "zb": True, "zl": True},
    {"name": "Banane", "category": "Obst", "portion_g": 100.0, "kcal": 89.0, "fat": 0.3, "sat_fat": 0.1, "sugar": 12.0, "protein": 1.1, "points": 2.0, "zr": True, "zb": True, "zl": True},
    {"name": "Naturjoghurt 1.5%", "category": "Milchprodukte", "portion_g": 150.0, "kcal": 92.0, "fat": 2.3, "sat_fat": 1.5, "sugar": 7.0, "protein": 8.0, "points": 2.0, "zr": False, "zb": False, "zl": False},
    {"name": "Hähnchenbrust", "category": "Geflügel", "portion_g": 100.0, "kcal": 110.0, "fat": 1.5, "sat_fat": 0.4, "sugar": 0.0, "protein": 23.0, "points": 0.0, "zr": False, "zb": True, "zl": True},
    {"name": "Ei", "category": "Eier", "portion_g": 60.0, "kcal": 80.0, "fat": 5.5, "sat_fat": 1.6, "sugar": 0.2, "protein": 7.0, "points": 2.0, "zr": False, "zb": True, "zl": True},
    {"name": "Kartoffeln gekocht", "category": "Kartoffeln", "portion_g": 150.0, "kcal": 117.0, "fat": 0.1, "sat_fat": 0.0, "sugar": 1.7, "protein": 3.0, "points": 2.0, "zr": False, "zb": False, "zl": True},
    {"name": "Vollkornbrot", "category": "Brot", "portion_g": 50.0, "kcal": 115.0, "fat": 1.3, "sat_fat": 0.2, "sugar": 2.0, "protein": 4.0, "points": 3.0, "zr": False, "zb": False, "zl": True},
]

DEFAULT_FOODS = load_foods_from_file()

SUPPLEMENTAL_FOODS = [
    {"name": "Tomate", "category": "Gemuese", "portion_g": 100.0, "kcal": 18.0, "fat": 0.2, "sat_fat": 0.0, "sugar": 2.6, "protein": 0.9, "points": 0.0, "zr": True, "zb": True, "zl": True},
    {"name": "Tomaten", "category": "Gemuese", "portion_g": 100.0, "kcal": 18.0, "fat": 0.2, "sat_fat": 0.0, "sugar": 2.6, "protein": 0.9, "points": 0.0, "zr": True, "zb": True, "zl": True},
    {"name": "Karotte", "category": "Gemuese", "portion_g": 100.0, "kcal": 41.0, "fat": 0.2, "sat_fat": 0.0, "sugar": 4.7, "protein": 0.9, "points": 0.0, "zr": True, "zb": True, "zl": True},
    {"name": "Karotten", "category": "Gemuese", "portion_g": 100.0, "kcal": 41.0, "fat": 0.2, "sat_fat": 0.0, "sugar": 4.7, "protein": 0.9, "points": 0.0, "zr": True, "zb": True, "zl": True},
    {"name": "Zucchini", "category": "Gemuese", "portion_g": 100.0, "kcal": 17.0, "fat": 0.3, "sat_fat": 0.0, "sugar": 2.5, "protein": 1.2, "points": 0.0, "zr": True, "zb": True, "zl": True},
    {"name": "Paprika", "category": "Gemuese", "portion_g": 100.0, "kcal": 31.0, "fat": 0.3, "sat_fat": 0.0, "sugar": 4.2, "protein": 1.0, "points": 0.0, "zr": True, "zb": True, "zl": True},
    {"name": "Paprika rot", "category": "Gemuese", "portion_g": 100.0, "kcal": 31.0, "fat": 0.3, "sat_fat": 0.0, "sugar": 4.2, "protein": 1.0, "points": 0.0, "zr": True, "zb": True, "zl": True},
    {"name": "Paprika gelb", "category": "Gemuese", "portion_g": 100.0, "kcal": 28.0, "fat": 0.2, "sat_fat": 0.0, "sugar": 3.8, "protein": 1.0, "points": 0.0, "zr": True, "zb": True, "zl": True},
    {"name": "Paprika gruen", "category": "Gemuese", "portion_g": 100.0, "kcal": 24.0, "fat": 0.2, "sat_fat": 0.0, "sugar": 2.4, "protein": 1.0, "points": 0.0, "zr": True, "zb": True, "zl": True},
    {"name": "Gurke", "category": "Gemuese", "portion_g": 100.0, "kcal": 12.0, "fat": 0.2, "sat_fat": 0.0, "sugar": 1.7, "protein": 0.6, "points": 0.0, "zr": True, "zb": True, "zl": True},
    {"name": "Salat", "category": "Gemuese", "portion_g": 100.0, "kcal": 15.0, "fat": 0.2, "sat_fat": 0.0, "sugar": 1.5, "protein": 1.4, "points": 0.0, "zr": True, "zb": True, "zl": True},
    {"name": "Salate", "category": "Gemuese", "portion_g": 100.0, "kcal": 15.0, "fat": 0.2, "sat_fat": 0.0, "sugar": 1.5, "protein": 1.4, "points": 0.0, "zr": True, "zb": True, "zl": True},
    {"name": "Nudeln gekocht", "category": "Getreide", "portion_g": 150.0, "kcal": 210.0, "fat": 1.2, "sat_fat": 0.2, "sugar": 2.0, "protein": 7.0, "points": 3.0, "zr": False, "zb": False, "zl": False},
    {"name": "Nudeln", "category": "Getreide", "portion_g": 150.0, "kcal": 210.0, "fat": 1.2, "sat_fat": 0.2, "sugar": 2.0, "protein": 7.0, "points": 3.0, "zr": False, "zb": False, "zl": False},
    {"name": "Reis gekocht", "category": "Getreide", "portion_g": 150.0, "kcal": 195.0, "fat": 0.4, "sat_fat": 0.1, "sugar": 0.1, "protein": 3.5, "points": 3.0, "zr": False, "zb": False, "zl": False},
    {"name": "Reis", "category": "Getreide", "portion_g": 150.0, "kcal": 195.0, "fat": 0.4, "sat_fat": 0.1, "sugar": 0.1, "protein": 3.5, "points": 3.0, "zr": False, "zb": False, "zl": False},
    {"name": "Milchkaffee", "category": "Milch", "portion_g": 200.0, "kcal": 45.0, "fat": 1.5, "sat_fat": 1.0, "sugar": 4.8, "protein": 3.0, "points": 1.0, "zr": False, "zb": False, "zl": False},
    {"name": "Kondensmilch", "category": "Milch", "portion_g": 300.0, "kcal": 330.0, "fat": 12.0, "sat_fat": 4.8, "sugar": 34.8, "protein": 20.4, "points": 13.5, "zr": False, "zb": False, "zl": False},
    {"name": "Kidneybohnen", "category": "Huelsenfruechte", "portion_g": 130.0, "kcal": 165.0, "fat": 0.8, "sat_fat": 0.1, "sugar": 0.4, "protein": 11.0, "points": 0.0, "zr": False, "zb": True, "zl": True},
    {"name": "Kichererbsen", "category": "Huelsenfruechte", "portion_g": 130.0, "kcal": 200.0, "fat": 3.0, "sat_fat": 0.3, "sugar": 4.8, "protein": 10.5, "points": 0.0, "zr": False, "zb": True, "zl": True},
    {"name": "Mais", "category": "Gemuese", "portion_g": 100.0, "kcal": 86.0, "fat": 1.4, "sat_fat": 0.2, "sugar": 6.3, "protein": 3.3, "points": 1.0, "zr": False, "zb": True, "zl": True},
    {"name": "Mais aus der Dose", "category": "Gemuese", "portion_g": 100.0, "kcal": 95.0, "fat": 1.8, "sat_fat": 0.2, "sugar": 5.0, "protein": 3.4, "points": 1.5, "zr": False, "zb": True, "zl": True},
    {"name": "Bohnen", "category": "Huelsenfruechte", "portion_g": 130.0, "kcal": 155.0, "fat": 0.7, "sat_fat": 0.1, "sugar": 0.5, "protein": 10.0, "points": 0.0, "zr": False, "zb": True, "zl": True},
    {"name": "Rote Bohnen", "category": "Huelsenfruechte", "portion_g": 130.0, "kcal": 160.0, "fat": 0.8, "sat_fat": 0.1, "sugar": 0.4, "protein": 10.8, "points": 0.0, "zr": False, "zb": True, "zl": True},
    {"name": "Weisse Bohnen", "category": "Huelsenfruechte", "portion_g": 130.0, "kcal": 150.0, "fat": 0.6, "sat_fat": 0.1, "sugar": 0.6, "protein": 10.0, "points": 0.0, "zr": False, "zb": True, "zl": True},
    {"name": "Shrimps", "category": "Meeresfruechte", "portion_g": 100.0, "kcal": 85.0, "fat": 0.5, "sat_fat": 0.1, "sugar": 0.0, "protein": 20.0, "points": 0.0, "zr": False, "zb": True, "zl": True},
    {"name": "Garnelen", "category": "Meeresfruechte", "portion_g": 100.0, "kcal": 85.0, "fat": 0.5, "sat_fat": 0.1, "sugar": 0.0, "protein": 20.0, "points": 0.0, "zr": False, "zb": True, "zl": True},
    {"name": "Meeresfruechte", "category": "Meeresfruechte", "portion_g": 100.0, "kcal": 90.0, "fat": 1.5, "sat_fat": 0.3, "sugar": 0.0, "protein": 17.0, "points": 1.0, "zr": False, "zb": True, "zl": True},
    {"name": "Lachs", "category": "Fisch", "portion_g": 125.0, "kcal": 244.0, "fat": 14.0, "sat_fat": 3.0, "sugar": 0.0, "protein": 28.0, "points": 3.0, "zr": False, "zb": False, "zl": True},
    {"name": "Thunfisch", "category": "Fisch", "portion_g": 100.0, "kcal": 116.0, "fat": 1.0, "sat_fat": 0.2, "sugar": 0.0, "protein": 26.0, "points": 0.0, "zr": False, "zb": True, "zl": True},
]


def default_store() -> dict:
    return {
        "profile": DEFAULT_PROFILE.copy(),
        "foods": list(DEFAULT_FOODS),
        "combos": [],
        "favorites": [],
        "logs": [],
        "weights": [],
        "measurements": [],
    }


def food_name_key(name: str) -> str:
    """Vergleichsschluessel fuer Lebensmittelnamen."""
    return str(name).strip().casefold()


def ensure_default_foods_present(data: dict) -> bool:
    """Ergaenzt fehlende Standard-Lebensmittel in bestehenden Daten."""
    foods = data.get("foods", [])
    existing = {food_name_key(f.get("name", "")) for f in foods}
    changed = False

    for default_food in list(DEFAULT_FOODS) + list(SUPPLEMENTAL_FOODS):
        key = food_name_key(default_food.get("name", ""))
        if not key or key in existing:
            continue
        foods.append(dict(default_food))
        existing.add(key)
        changed = True

    # Plural/Singular-Helfer fuer bessere Suche
    if "tomate" in existing and "tomaten" not in existing:
        tomato = next((f for f in foods if food_name_key(f.get("name", "")) == "tomate"), None)
        if tomato is not None:
            tomato_plural = dict(tomato)
            tomato_plural["name"] = "Tomaten"
            foods.append(tomato_plural)
            changed = True

    data["foods"] = foods
    return changed


def normalize_known_foods(data: dict) -> bool:
    """Korrigiert bekannte problematische Lebensmittelwerte in bestehenden Daten."""
    foods = data.get("foods", [])
    changed = False

    corrections = {
        "milchkaffee": {
            "category": "Milch",
            "portion_g": 200.0,
            "kcal": 45.0,
            "fat": 1.5,
            "sat_fat": 1.0,
            "sugar": 4.8,
            "protein": 3.0,
            "points": 1.0,
            "zr": False,
            "zb": False,
            "zl": False,
        },
        "kondensmilch": {
            "category": "Milch",
            "portion_g": 300.0,
            "kcal": 330.0,
            "fat": 12.0,
            "sat_fat": 4.8,
            "sugar": 34.8,
            "protein": 20.4,
            "points": 13.5,
            "zr": False,
            "zb": False,
            "zl": False,
        },
    }

    # Auch Varianten treffen (z. B. "Milchkaffee,", "gezuckerte Kondensmilch")
    token_to_key = {
        "milchkaffee": "milchkaffee",
        "kondensmilch": "kondensmilch",
    }

    for food in foods:
        key = food_name_key(food.get("name", ""))
        target = None
        if key in corrections:
            target = corrections[key]
        else:
            for token, corr_key in token_to_key.items():
                if token in key:
                    target = corrections[corr_key]
                    break

        if target is None:
            continue

        for field, value in target.items():
            if food.get(field) != value:
                food[field] = value
                changed = True

    return changed


def load_store() -> dict:
    if not DATA_FILE.exists():
        data = default_store()
        save_store(data)
        return data
    with DATA_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # Vorwärtskompatibel: fehlende Felder in älteren store.json ergänzen
    data.setdefault("profile", DEFAULT_PROFILE.copy())
    data.setdefault("foods", list(DEFAULT_FOODS))
    data.setdefault("combos", [])
    data.setdefault("favorites", [])
    data.setdefault("logs", [])
    data.setdefault("weights", [])
    data.setdefault("measurements", [])

    has_changes = False

    sanitized_profile = sanitize_profile_data(data.get("profile", {}))
    if data.get("profile") != sanitized_profile:
        data["profile"] = sanitized_profile
        has_changes = True

    if ensure_default_foods_present(data):
        has_changes = True

    if normalize_known_foods(data):
        has_changes = True

    if recalculate_old_log_points(data):
        has_changes = True

    if has_changes:
        save_store(data)

    return data


def save_store(data: dict) -> None:
    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def age_from_birthdate(birth_date: date) -> int:
    today = date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def daily_points_breakdown(profile: dict) -> tuple[list[dict], int, int]:
    age = age_from_birthdate(datetime.strptime(profile["birth_date"], "%Y-%m-%d").date())

    base_points = 7 if profile["gender"] == "Weiblich" else 15

    if 18 <= age <= 20:
        age_points = 5
    elif 21 <= age <= 35:
        age_points = 4
    elif 36 <= age <= 50:
        age_points = 3
    elif 51 <= age <= 65:
        age_points = 2
    elif age >= 66:
        age_points = 1
    else:
        age_points = 0

    height_points = 1 if float(profile["height"]) < 160 else 2
    weight_points = int(float(profile["current_weight"]) / 10)

    activity_map = {
        "Kaum Bewegung": 0,
        "Wenig Bewegung": 2,
        "Viel Bewegung": 4,
        "Täglich viel Bewegung": 6,
    }
    activity_points = activity_map.get(profile["activity_level"], 2)
    goal_points = 4 if profile["weight_goal"] == "Gewicht halten" else 0

    rows = [
        {"Faktor": "Geschlecht", "Wert": profile["gender"], "Punkte": base_points},
        {"Faktor": "Alter", "Wert": f"{age} Jahre", "Punkte": age_points},
        {"Faktor": "Größe", "Wert": f"{float(profile['height']):.1f} cm", "Punkte": height_points},
        {"Faktor": "Gewicht", "Wert": f"{float(profile['current_weight']):.1f} kg", "Punkte": weight_points},
        {"Faktor": "Aktivität", "Wert": profile["activity_level"], "Punkte": activity_points},
        {"Faktor": "Ziel", "Wert": profile["weight_goal"], "Punkte": goal_points},
    ]
    total = sum(int(r["Punkte"]) for r in rows)
    return rows, total, age


def daily_points(profile: dict) -> int:
    _, total, _ = daily_points_breakdown(profile)
    return total


def calc_food_points(kcal: float, fat: float, sat_fat: float, sugar: float, protein: float) -> float:
    sat = sat_fat if sat_fat >= 0 else fat * 0.4
    raw = kcal * 0.0305 + sat * 0.275 + sugar * 0.12 - protein * 0.098
    # Aufrunden auf 0.5er Schritte
    rounded = math.ceil(raw * 2) / 2
    return max(0.0, rounded)


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@st.cache_data(show_spinner=False, ttl=3600)
def search_foods_online(query: str, page_size: int = 12) -> list[dict]:
    q = str(query or "").strip()
    if not q:
        return []

    size = max(1, min(int(page_size), 30))
    url = (
        "https://world.openfoodfacts.org/cgi/search.pl"
        f"?search_terms={quote_plus(q)}"
        "&search_simple=1&action=process&json=1"
        f"&page_size={size}"
        "&fields=product_name,brands,categories,nutriments"
    )

    try:
        req = Request(url, headers={"User-Agent": "MeinTagebuch/1.0"})
        with urlopen(req, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8", errors="ignore"))
    except Exception:
        return []

    out = []
    seen = set()
    for product in payload.get("products", []):
        if not isinstance(product, dict):
            continue

        name = str(product.get("product_name") or "").strip()
        if not name:
            continue

        nutriments = product.get("nutriments") if isinstance(product.get("nutriments"), dict) else {}

        kcal = _to_float(nutriments.get("energy-kcal_100g"), 0.0)
        if kcal <= 0.0:
            kcal_from_kj = _to_float(nutriments.get("energy_100g"), 0.0)
            if kcal_from_kj > 0.0:
                kcal = kcal_from_kj / 4.184

        fat = _to_float(nutriments.get("fat_100g"), 0.0)
        sat_fat = _to_float(nutriments.get("saturated-fat_100g"), fat * 0.4)
        sugar = _to_float(nutriments.get("sugars_100g"), 0.0)
        protein = _to_float(nutriments.get("proteins_100g"), 0.0)

        brand = str(product.get("brands") or "").split(",")[0].strip()
        category = str(product.get("categories") or "").split(",")[0].strip() or "Internet-Import"
        display_name = f"{name} ({brand})" if brand else name
        key = food_name_key(display_name)
        if key in seen:
            continue
        seen.add(key)

        out.append(
            {
                "name": display_name,
                "category": category,
                "portion_g": 100.0,
                "kcal": max(0.0, kcal),
                "fat": max(0.0, fat),
                "sat_fat": max(0.0, sat_fat),
                "sugar": max(0.0, sugar),
                "protein": max(0.0, protein),
                "points": calc_food_points(kcal, fat, sat_fat, sugar, protein),
                "zr": False,
                "zb": False,
                "zl": False,
            }
        )

        if len(out) >= size:
            break

    return out


def food_points_for_plan(food: dict, plan: str) -> float:
    if plan == "Restriktiv" and food.get("zr", False):
        return 0.0
    if plan == "Ausgewogen" and food.get("zb", False):
        return 0.0
    if plan == "Liberal" and food.get("zl", False):
        return 0.0

    stored_points = float(food.get("points", 0.0) or 0.0)

    # Fallback: falls gespeicherte Punkte fehlen/0 sind, aus Nährwerten berechnen.
    kcal = float(food.get("kcal", 0.0) or 0.0)
    fat = float(food.get("fat", 0.0) or 0.0)
    sat_fat = float(food.get("sat_fat", fat * 0.4) or 0.0)
    sugar = float(food.get("sugar", 0.0) or 0.0)
    protein = float(food.get("protein", 0.0) or 0.0)
    calculated_points = calc_food_points(kcal, fat, sat_fat, sugar, protein)

    if stored_points <= 0.0 and calculated_points > 0.0:
        return calculated_points

    return stored_points


def recalculate_old_log_points(data: dict) -> bool:
    """Korrigiert alte Log-Einträge mit 0 Punkten, wenn eine Berechnung möglich ist."""
    changed = False
    foods = data.get("foods", [])
    combos = data.get("combos", [])
    logs = data.get("logs", [])
    plan = data.get("profile", {}).get("plan", "Ausgewogen")

    food_by_name = {food_name_key(f.get("name", "")): f for f in foods}
    combo_by_name = {food_name_key(c.get("name", "")): c for c in combos}
    force_recalc_tokens = {"kondensmilch", "milchkaffee"}

    for log in logs:
        for entry in log.get("entries", []):
            old_points = float(entry.get("points", 0.0) or 0.0)
            name_key = food_name_key(entry.get("name", ""))
            force_recalc = any(token in name_key for token in force_recalc_tokens)
            if old_points > 0.0 and not force_recalc:
                continue

            amount = float(entry.get("amount", 0.0) or 0.0)
            new_points = old_points

            if bool(entry.get("is_combo", False)):
                combo = combo_by_name.get(name_key)
                if combo is not None:
                    factor = amount if amount > 0 else 1.0
                    new_points = math.ceil(combo_points_for_plan(combo, foods, plan) * factor * 10) / 10
            else:
                food = food_by_name.get(name_key)
                if food is not None:
                    portion = max(1.0, float(food.get("portion_g", 100.0) or 100.0))
                    factor = (amount / portion) if amount > 0 else 1.0
                    new_points = math.ceil(food_points_for_plan(food, plan) * factor * 10) / 10

            if new_points > 0.0 and abs(new_points - old_points) > 0.01:
                entry["points"] = new_points
                changed = True

    return changed


def todays_log(logs: list, day_str: str) -> dict:
    for log in logs:
        if log["date"] == day_str:
            return log
    new_log = {"date": day_str, "entries": [], "water_l": 0.0, "bonus": 0}
    logs.append(new_log)
    return new_log


def week_avg_points(logs: list) -> float:
    if not logs:
        return 0.0
    totals = [sum(float(e["points"]) for e in l.get("entries", [])) for l in logs]
    return sum(totals) / len(totals)


def stars_earned(start_weight: float, current_weight: float) -> int:
    lost = start_weight - current_weight
    return max(0, int(lost // 5))


WEIGH_DAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def set_profile_form_state(profile_data: dict) -> None:
    """Setzt die Profil-Form-Felder in der Session auf gegebene Profildaten."""
    p = sanitize_profile_data(profile_data)
    st.session_state["p_name"] = p["name"]
    st.session_state["p_gender"] = p["gender"]
    st.session_state["p_birth"] = datetime.strptime(p["birth_date"], "%Y-%m-%d").date()
    st.session_state["p_height"] = float(p["height"])
    st.session_state["p_startw"] = float(p["start_weight"])
    st.session_state["p_curw"] = float(p["current_weight"])
    st.session_state["p_goalw"] = float(p["goal_weight"])
    st.session_state["p_activity"] = p["activity_level"]
    st.session_state["p_goal"] = p["weight_goal"]
    st.session_state["p_plan"] = p["plan"]
    st.session_state["p_weigh_day"] = p["weigh_day"]
    st.session_state["p_activity_extra_mode"] = p["activity_extra_mode"]


def sanitize_food_item(raw: dict) -> dict | None:
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name", "")).strip()
    if not name:
        return None
    fat = max(0.0, _safe_float(raw.get("fat", 0.0)))
    sat_fat = max(0.0, _safe_float(raw.get("sat_fat", fat * 0.4)))
    kcal = max(0.0, _safe_float(raw.get("kcal", 0.0)))
    sugar = max(0.0, _safe_float(raw.get("sugar", 0.0)))
    protein = max(0.0, _safe_float(raw.get("protein", 0.0)))
    points = max(0.0, _safe_float(raw.get("points", calc_food_points(kcal, fat, sat_fat, sugar, protein))))
    return {
        "name": name,
        "category": str(raw.get("category", "Sonstiges")).strip() or "Sonstiges",
        "portion_g": max(1.0, _safe_float(raw.get("portion_g", 100.0), 100.0)),
        "kcal": kcal,
        "fat": fat,
        "sat_fat": sat_fat,
        "sugar": sugar,
        "protein": protein,
        "points": points,
        "zr": bool(raw.get("zr", False)),
        "zb": bool(raw.get("zb", False)),
        "zl": bool(raw.get("zl", False)),
    }


def sanitize_combo_item(raw: dict) -> dict | None:
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name", "")).strip()
    if not name:
        return None
    items = []
    for item in raw.get("items", []):
        if not isinstance(item, dict):
            continue
        food_name = str(item.get("food_name", "")).strip()
        if not food_name:
            continue
        items.append({
            "food_name": food_name,
            "amount_g": max(0.0, _safe_float(item.get("amount_g", 0.0))),
        })
    return {"name": name, "items": items}


def sanitize_log_item(raw: dict) -> dict | None:
    if not isinstance(raw, dict):
        return None
    raw_date = str(raw.get("date", "")).strip()
    try:
        parsed_date = date.fromisoformat(raw_date)
        log_date = parsed_date.isoformat()
    except ValueError:
        return None

    entries = []
    for entry in raw.get("entries", []):
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()
        if not name:
            continue
        entries.append({
            "name": name,
            "amount": max(0.0, _safe_float(entry.get("amount", 0.0))),
            "meal": str(entry.get("meal", "Snack")).strip() or "Snack",
            "points": max(0.0, _safe_float(entry.get("points", 0.0))),
            "time": str(entry.get("time", "")).strip() or f"{log_date}T00:00:00",
            "is_combo": bool(entry.get("is_combo", False)),
        })

    activities = []
    for activity in raw.get("activities", []):
        if not isinstance(activity, dict):
            continue
        activity_name = str(activity.get("name", "")).strip()
        if not activity_name:
            continue
        activities.append({
            "name": activity_name,
            "intensity": str(activity.get("intensity", "")).strip(),
            "duration": int(max(0, _safe_float(activity.get("duration", 0)))),
            "points": max(0.0, _safe_float(activity.get("points", 0.0))),
            "weight_at_entry": max(0.0, _safe_float(activity.get("weight_at_entry", 0.0))),
        })

    return {
        "date": log_date,
        "entries": entries,
        "bonus": int(max(0, _safe_float(raw.get("bonus", 0)))),
        "steps": int(max(0, _safe_float(raw.get("steps", 0)))),
        "activities": activities,
        "daily_pts_snapshot": int(max(0, _safe_float(raw.get("daily_pts_snapshot", 0)))),
    }


def sanitize_weight_item(raw: dict) -> dict | None:
    if not isinstance(raw, dict):
        return None
    raw_date = str(raw.get("date", "")).strip()
    try:
        parsed_date = date.fromisoformat(raw_date)
        weight_date = parsed_date.isoformat()
    except ValueError:
        return None
    return {
        "date": weight_date,
        "weight": max(30.0, min(300.0, _safe_float(raw.get("weight", 80.0), 80.0))),
        "note": str(raw.get("note", ""))[:300],
    }


def sanitize_backup_data(raw: dict) -> dict:
    """Validiert Komplett-Backup und liefert sichere App-Datenstruktur."""
    data = default_store()
    if not isinstance(raw, dict):
        return data

    data["profile"] = sanitize_profile_data(raw.get("profile", {}))

    foods = [sanitize_food_item(f) for f in raw.get("foods", []) if isinstance(f, dict)]
    data["foods"] = [f for f in foods if f is not None]

    combos = [sanitize_combo_item(c) for c in raw.get("combos", []) if isinstance(c, dict)]
    data["combos"] = [c for c in combos if c is not None]

    favorites = []
    for fav in raw.get("favorites", []):
        fav_text = str(fav).strip()
        if fav_text:
            favorites.append(fav_text)
    data["favorites"] = favorites

    logs = [sanitize_log_item(l) for l in raw.get("logs", []) if isinstance(l, dict)]
    data["logs"] = [l for l in logs if l is not None]

    weights = [sanitize_weight_item(w) for w in raw.get("weights", []) if isinstance(w, dict)]
    data["weights"] = [w for w in weights if w is not None]

    raw_measurements = raw.get("measurements", [])
    if isinstance(raw_measurements, list):
        safe_measurements = []
        for m in raw_measurements:
            if not isinstance(m, dict):
                continue
            entry = {"date": str(m.get("date", ""))[:10]}
            for field in ["oberarm_links", "oberarm_rechts", "brust", "taille", "huefte", "oberschenkel_links", "oberschenkel_rechts"]:
                try:
                    val = float(m.get(field, 0.0))
                    entry[field] = max(0.0, min(300.0, val))
                except (TypeError, ValueError):
                    entry[field] = 0.0
            entry["note"] = str(m.get("note", ""))[:200]
            safe_measurements.append(entry)
        data["measurements"] = safe_measurements

    ensure_default_foods_present(data)
    normalize_known_foods(data)
    recalculate_old_log_points(data)
    return data


def build_backup_payload(data: dict) -> dict:
    """Erstellt ein JSON-Backup mit allen relevanten App-Daten."""
    payload = {
        "app": APP_TITLE,
        "format": "meintagebuch-backup-v1",
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "profile": data.get("profile", DEFAULT_PROFILE),
        "foods": data.get("foods", []),
        "combos": data.get("combos", []),
        "favorites": data.get("favorites", []),
        "logs": data.get("logs", []),
        "weights": data.get("weights", []),
        "measurements": data.get("measurements", []),
    }
    # Tiefenkopie via JSON, damit der Export keine Referenzen auf Live-Daten enthält.
    return json.loads(json.dumps(payload, ensure_ascii=False))


def weekly_extra_points(profile: dict) -> int:
    """100 kg = 35, je 10 kg darunter minus 5, Minimum 15."""
    weight = float(profile["current_weight"])
    below_100_steps = max(0, int((100 - weight) // 10))
    raw = 35 - (below_100_steps * 5)
    return max(15, min(35, raw))


def activity_points_enabled(profile: dict) -> bool:
    mode = str(profile.get("activity_extra_mode", DEFAULT_PROFILE["activity_extra_mode"]))
    if mode not in ALLOWED_ACTIVITY_EXTRA_MODES:
        mode = DEFAULT_PROFILE["activity_extra_mode"]
    return mode == "Erst Wochenextra und dann Aktivitätspunkte"


def log_daily_base_points(log: dict, profile: dict | None = None) -> float:
    snapshot = float(log.get("daily_pts_snapshot", 0.0) or 0.0)
    if snapshot > 0:
        return snapshot
    if profile is None:
        return 0.0
    return float(daily_points(profile))


def current_weigh_week_start(profile: dict) -> date:
    """Datum des letzten Wiegetags (Wochenbeginn für Extrapunkte)."""
    weigh_day_name = profile.get("weigh_day", "Montag")
    day_idx = WEIGH_DAYS.index(weigh_day_name)  # 0=Mo, 6=So
    today = date.today()
    days_since = (today.weekday() - day_idx) % 7
    return today - timedelta(days=days_since)


def weekly_extra_used(logs: list, week_start: date, profile: dict | None = None, as_of: date | None = None) -> float:
    """Summe aller verbrauchten Wochenextra-Punkte innerhalb der aktuellen Wiege-Woche."""
    period_end = as_of or date.today()
    used = 0.0
    for log in logs:
        try:
            log_date = date.fromisoformat(log["date"])
        except (KeyError, ValueError):
            continue
        if log_date < week_start or log_date > period_end:
            continue
        day_profile_pts = log_daily_base_points(log, profile)
        day_total = sum(float(e["points"]) for e in log.get("entries", []))
        overflow = day_total - day_profile_pts
        if overflow > 0:
            used += overflow
    return math.ceil(used * 10) / 10


def day_budget_status(log: dict, profile: dict, week_extra_left_before_day: float) -> dict:
    """Berechnet Tagesstatus mit Reihenfolge: Tagespunkte -> Wochenextra -> Aktivitätspunkte."""
    daily_base = log_daily_base_points(log, profile)
    total_points = sum(float(e.get("points", 0.0)) for e in log.get("entries", []))
    day_over_base = max(0.0, total_points - daily_base)
    weekly_used_today = min(day_over_base, max(0.0, week_extra_left_before_day))
    after_weekly = max(0.0, day_over_base - weekly_used_today)

    available_activity = int(log.get("bonus", 0)) if activity_points_enabled(profile) else 0
    activity_used_today = min(after_weekly, float(available_activity))
    deficit_after_all = max(0.0, after_weekly - activity_used_today)

    return {
        "daily_base": daily_base,
        "total_points": total_points,
        "weekly_used_today": weekly_used_today,
        "activity_available": float(available_activity),
        "activity_used_today": activity_used_today,
        "deficit": deficit_after_all,
        "daily_remaining": max(0.0, daily_base - total_points),
    }


def weekly_strip_nav(date_key: str, profile: dict, store: dict) -> date:
    """7-Tage Wochen-Streifen: Vergangene Tage grün, heute magenta, Zukunft grau (nicht klickbar)."""
    today = date.today()
    week_start = current_weigh_week_start(profile)

    # Gewählten Tag aus Query-Param lesen (Link-Navigation)
    try:
        raw_day = st.query_params.get("day", today.isoformat())
        selected = date.fromisoformat(str(raw_day))
    except (ValueError, AttributeError):
        selected = today
    # Clamp: kein zukünftiger Tag, kein Tag vor dieser Woche
    selected = max(week_start, min(today, selected))
    st.session_state[date_key] = selected

    # Wochennummer berechnen
    all_dates = []
    for _log in store.get("logs", []):
        try:
            all_dates.append(date.fromisoformat(_log["date"]))
        except (KeyError, ValueError):
            pass
    for _w in store.get("weights", []):
        try:
            all_dates.append(date.fromisoformat(_w["date"]))
        except (KeyError, ValueError):
            pass
    week_num = 1
    if all_dates:
        earliest = min(all_dates)
        _day_idx = WEIGH_DAYS.index(profile.get("weigh_day", "Montag"))
        _days_back = (earliest.weekday() - _day_idx) % 7
        earliest_week_start = earliest - timedelta(days=_days_back)
        week_num = max(1, (week_start - earliest_week_start).days // 7 + 1)

    days_of_week = [week_start + timedelta(days=i) for i in range(7)]
    day_abbrevs = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    current_nav = str(st.query_params.get("nav", "mahlz"))

    buttons_html = []
    for _day in days_of_week:
        _abbr = day_abbrevs[_day.weekday()]
        _day_str = _day.isoformat()
        _label = f"<strong>{_abbr}</strong><br/><span style='font-size:0.65rem'>{_day.strftime('%d.%m')}</span>"
        _is_sel = _day == selected
        _sel_ring = "box-shadow:0 0 0 2.5px #333 inset;" if _is_sel else ""

        if _day > today:
            buttons_html.append(
                f'<div style="flex:1;text-align:center;padding:7px 2px;border-radius:8px;'
                f'font-size:0.72rem;background:#f0f0f0;color:#bbb;border:1px solid #e0e0e0;'
                f'cursor:not-allowed;min-width:0;">{_label}</div>'
            )
        elif _day == today:
            buttons_html.append(
                f'<a href="?nav={current_nav}&day={_day_str}" style="flex:1;text-align:center;'
                f'text-decoration:none;padding:7px 2px;border-radius:8px;font-size:0.72rem;'
                f'display:block;background:#e91e8c;color:white;border:2px solid #c2185b;'
                f'font-weight:bold;min-width:0;{_sel_ring}">{_label}</a>'
            )
        else:
            buttons_html.append(
                f'<a href="?nav={current_nav}&day={_day_str}" style="flex:1;text-align:center;'
                f'text-decoration:none;padding:7px 2px;border-radius:8px;font-size:0.72rem;'
                f'display:block;background:#e8f5e9;color:#2e7d32;border:1px solid #a5d6a7;'
                f'min-width:0;{_sel_ring}">{_label}</a>'
            )

    week_end = week_start + timedelta(days=6)
    week_label = (
        f"Woche {week_num} &nbsp;·&nbsp; "
        f"{week_start.strftime('%d.%m.')} – {week_end.strftime('%d.%m.')}"
    )
    st.markdown(
        f'<div style="font-size:0.7rem;color:#888;margin-bottom:4px;">{week_label}</div>'
        f'<div style="display:flex;gap:3px;margin-bottom:10px;">{" ".join(buttons_html)}</div>',
        unsafe_allow_html=True,
    )
    return selected


def usage_scores_from_logs(logs: list) -> dict[str, float]:
    """Bewertet Lebensmittel nach Nutzung: heute/gestern/häufig bekommen höhere Priorität."""
    scores: dict[str, float] = {}
    today = date.today()

    for log in logs:
        try:
            log_date = date.fromisoformat(log.get("date", ""))
        except ValueError:
            continue

        days_ago = (today - log_date).days
        if days_ago < 0:
            continue

        if days_ago == 0:
            base = 140.0
        elif days_ago == 1:
            base = 110.0
        elif days_ago <= 7:
            base = 40.0
        elif days_ago <= 30:
            base = 12.0
        else:
            base = 2.0

        for entry in log.get("entries", []):
            name = str(entry.get("name", "")).strip()
            if not name:
                continue
            scores[name] = scores.get(name, 0.0) + base

    return scores


def sort_foods_by_usage(foods: list[dict], logs: list) -> list[dict]:
    """Sortiert Lebensmittel so, dass oft/zuletzt genutzte oben erscheinen."""
    scores = usage_scores_from_logs(logs)
    return sorted(foods, key=lambda f: (-scores.get(f.get("name", ""), 0.0), f.get("name", "").lower()))


def combo_points_for_plan(combo: dict, foods: list[dict], plan: str) -> float:
    """Berechnet Punkte einer gespeicherten Kombi aus den enthaltenen Lebensmitteln."""
    food_by_name = {f.get("name", ""): f for f in foods}
    total = 0.0

    for item in combo.get("items", []):
        fname = item.get("food_name", "")
        amount = float(item.get("amount_g", 0.0))
        food = food_by_name.get(fname)
        if not food:
            continue

        portion_g = max(1.0, float(food.get("portion_g", 100.0)))
        factor = amount / portion_g
        total += food_points_for_plan(food, plan) * factor

    return math.ceil(total * 10) / 10


def recent_log_entries(logs: list, limit: int = 10) -> list[dict]:
    """Liefert die letzten Log-Einträge über alle Tage, neueste zuerst."""
    flat: list[dict] = []

    for log in logs:
        log_date = str(log.get("date", ""))
        for entry in log.get("entries", []):
            timestamp = str(entry.get("time", "")) or f"{log_date}T00:00:00"
            flat.append(
                {
                    "name": str(entry.get("name", "")).strip(),
                    "amount": float(entry.get("amount", 0.0)),
                    "meal": str(entry.get("meal", "Snack")),
                    "points": float(entry.get("points", 0.0)),
                    "is_combo": bool(entry.get("is_combo", False)),
                    "timestamp": timestamp,
                }
            )

    flat = [e for e in flat if e["name"]]
    flat.sort(key=lambda e: e["timestamp"], reverse=True)
    return flat[:limit]


ACTIVITIES = {
    "Spaziergang": {"leicht": 2.8, "moderat": 3.5},
    "Gehen": {"leicht": 2.0, "moderat": 3.5},
    "Dehnübungen": {"leicht": 2.3},
    "Yoga": {"leicht": 2.5},
    "Tanzen": {"moderat": 4.5, "anstrengend": 6.0},
    "Schwimmen": {"moderat": 4.8, "anstrengend": 7.0},
    "Fahrradfahren": {"moderat": 5.8, "anstrengend": 8.3},
    "Fitnesstraining": {"moderat": 3.8, "anstrengend": 6.0, "sehr anstrengend": 9.0},
    "Laufen": {"anstrengend": 6.0, "sehr anstrengend": 9.8},
    "Joggen": {"anstrengend": 8.0, "sehr anstrengend": 10.0},
    "Treppensteigen": {"anstrengend": 8.8},
    "HIIT": {"sehr anstrengend": 12.0},
}

INTENSITY_LABELS = {
    "leicht": "Leicht (z.B. Spaziergang, Yoga)",
    "moderat": "Moderat (z.B. Schwimmen, Fahrradfahren)",
    "anstrengend": "Anstrengend (z.B. Joggen, Treppensteigen)",
    "sehr anstrengend": "Sehr anstrengend (z.B. Laufen, HIIT)",
}

ACTIVITY_CATEGORIES = {
    "leicht": "Leichte Aktivitäten (Spazieren, Yoga)",
    "moderat": "Moderate Aktivitäten (Schwimmen, Fahrradfahren)",
    "anstrengend": "Anstrengende Aktivitäten (Joggen, Treppensteigen)",
    "sehr anstrengend": "Sehr anstrengende Aktivitäten (Laufen, HIIT)",
}


def activity_points(activity_name: str, intensity: str, duration_minutes: int, body_weight_kg: float) -> float:
    """Berechnet Punkte für Aktivität basierend auf MET, Dauer und Körpergewicht.
    Formel: Kalorien = (MET × Gewicht in kg × Minuten) / 60
    Punkte = Kalorien × 0.0305
    Kaufmännisches Runden: ab 0,5 aufrunden, sonst abrunden.
    """
    if activity_name not in ACTIVITIES:
        return 0.0
    
    activity = ACTIVITIES[activity_name]
    if intensity not in activity:
        return 0.0
    
    met = activity[intensity]
    
    # Kalorien berechnen
    calories = (met * body_weight_kg * duration_minutes) / 60.0
    
    # In Weight Watchers Punkte konvertieren
    points = calories * 0.0305
    
    # Kaufmännisches Runden: ab 0,5 aufrunden, sonst abrunden
    points = math.floor(points + 0.5)
    
    return max(0.0, float(points))


def steps_to_points(steps: int, body_weight_kg: float = None) -> float:
    """Konvertiert Schritte zu Weight Watchers Punkten.
    Formel: 
    - Erste 2000 Schritte: 0 Punkte
    - Ab 2000 Schritte: (Schritte - 2000) / 1000 = 1 Punkt pro 1000er Block
    Beispiel: 8000 Schritte = (8000 - 2000) / 1000 = 6 Punkte
    """
    if steps < 2000:
        return 0.0
    
    # Für jeden vollen 1000er Block nach den ersten 2000 Schritten: 1 Punkt
    points = (steps - 2000) // 1000
    
    return float(max(0, points))


def favorite_key(kind: str, name: str) -> str:
    """Eindeutiger Schlüssel für fixierte Einträge."""
    return f"{kind}:{name.strip().lower()}"


st.set_page_config(page_title=APP_TITLE, layout="wide", initial_sidebar_state="collapsed")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@500;600;700;800&display=swap');

    :root {
        --app-magenta: #cc1188;
        --app-magenta-strong: #a10d6d;
        --app-bg: #f4f4f7;
        --app-card: #ffffff;
        --app-soft: #ececf1;
        --app-text: #22232a;
    }

    .stApp {
        background: linear-gradient(180deg, #fbfbfd 0%, var(--app-bg) 100%);
        color: var(--app-text);
    }

    .stApp {
        font-family: 'Manrope', 'Segoe UI', sans-serif;
    }

    .main .block-container {
        max-width: 980px;
        padding-top: 1.1rem;
        padding-bottom: 2rem;
    }

    [data-testid="stSidebar"] {
        background: #f8f8fb;
        border-right: 1px solid #ececf2;
    }

    .dashboard-wrap {
        background: var(--app-card);
        border: 1px solid var(--app-soft);
        border-radius: 20px;
        padding: 18px 20px;
        box-shadow: 0 8px 24px rgba(20, 20, 30, 0.06);
        margin-bottom: 14px;
    }

    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #ececf2;
        border-radius: 14px;
        padding: 10px 12px;
        box-shadow: 0 6px 16px rgba(25, 20, 40, 0.04);
    }

    [data-testid="stMetricLabel"] {
        color: #6d7080;
        font-weight: 600;
    }

    [data-testid="stMetricValue"] {
        color: #2a2d36;
    }

    .dashboard-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: var(--app-text);
        margin: 0 0 10px 0;
    }

    .dashboard-top {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
    }

    .top-icons {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
    }

    .top-icon-pill {
        background: #fff;
        border: 1px solid #e8e9f0;
        color: #505564;
        border-radius: 999px;
        padding: 6px 10px;
        font-size: 0.76rem;
        font-weight: 700;
        white-space: nowrap;
    }

    .dashboard-sub {
        margin: 2px 0 0 0;
        font-size: 0.88rem;
        color: #666a76;
    }

    .hero-grid {
        display: grid;
        grid-template-columns: 220px 1fr;
        grid-template-areas:
            "ring card1"
            "ring card2"
            "quick quick";
        gap: 12px;
        margin-top: 8px;
        align-items: stretch;
    }

    .hero-ring {
        grid-area: ring;
        background: #fbfbfd;
        border: 1px solid #ececf2;
        border-radius: 16px;
        display: grid;
        place-items: center;
        padding: 10px;
    }

    .hero-card-a { grid-area: card1; }
    .hero-card-b { grid-area: card2; }

    .hero-quick {
        grid-area: quick;
        background: #f9f9fc;
        border: 1px solid #ececf2;
        border-radius: 14px;
        padding: 10px 12px;
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
    }

    .quick-pill {
        background: #ffffff;
        border: 1px solid #e8e9f0;
        color: #555b68;
        border-radius: 999px;
        padding: 6px 10px;
        font-size: 0.76rem;
        font-weight: 700;
    }

    .quick-buttons-anchor + div[data-testid="stHorizontalBlock"] [data-testid="stButton"] > button {
        width: 100%;
        min-height: 44px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        padding: 0 10px;
        font-size: 0.82rem;
    }

    .ring {
        --size: 150px;
        width: var(--size);
        height: var(--size);
        border-radius: 50%;
        background: conic-gradient(var(--app-magenta) calc(var(--p) * 1%), #ececf1 0);
        display: grid;
        place-items: center;
        margin: 0 auto;
    }

    .ring-inner {
        width: calc(var(--size) - 22px);
        height: calc(var(--size) - 22px);
        border-radius: 50%;
        background: #fff;
        display: grid;
        place-items: center;
        text-align: center;
        border: 1px solid #f0f0f3;
    }

    .ring-value {
        font-size: 2rem;
        line-height: 1;
        font-weight: 800;
        color: var(--app-magenta-strong);
    }

    .ring-label {
        font-size: 0.78rem;
        color: #6d7080;
        margin-top: 3px;
    }

    .sidebar-hero {
        background: #fbfbfd;
        border: 1px solid #ececf2;
        border-radius: 14px;
        padding: 12px;
        margin-bottom: 10px;
    }

    .sidebar-title {
        font-size: 1rem;
        font-weight: 800;
        color: var(--app-text);
        margin: 0;
    }

    .sidebar-sub {
        font-size: 0.76rem;
        color: #666a76;
        margin: 6px 0 10px;
    }

    .sidebar-ring .ring {
        --size: 120px;
    }

    .kpi-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
    }

    .kpi-card {
        background: #f9f9fc;
        border: 1px solid #ececf2;
        border-radius: 14px;
        padding: 10px 12px;
    }

    .kpi-title {
        font-size: 0.78rem;
        color: #696d79;
        margin-bottom: 4px;
    }

    .kpi-value {
        font-size: 1.22rem;
        font-weight: 700;
        color: var(--app-text);
    }

    .kpi-foot {
        font-size: 0.75rem;
        color: #7a7e8d;
        margin-top: 2px;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: #f3f3f7;
        border-radius: 12px;
        padding: 5px;
        border: 1px solid #ececf2;
    }

    .stRadio > div {
        background: #f3f3f7;
        border: 1px solid #ececf2;
        border-radius: 12px;
        padding: 6px;
    }

    .stRadio [role="radiogroup"] {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
    }

    .stRadio [role="radio"] {
        background: #ffffff;
        border: 1px solid #ececf2;
        border-radius: 10px;
        padding: 6px 10px;
    }

    .stRadio [role="radio"][aria-checked="true"] {
        background: var(--app-magenta);
        color: #ffffff;
        border-color: var(--app-magenta);
        box-shadow: 0 8px 16px rgba(161, 13, 109, 0.22);
    }

    .app-bottom-nav {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 10px;
        background: #f3f3f7;
        border: 1px solid #ececf2;
        border-radius: 14px;
        padding: 8px;
        margin-bottom: 10px;
    }

    .app-top-nav {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        align-items: center;
        gap: 10px;
        width: 100%;
        margin-bottom: 10px;
    }

    .app-top-ring {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 100%;
    }

    .app-top-ring .ring {
        --size: 66px;
    }

    .app-top-ring .ring-value {
        font-size: 1.25rem;
    }

    .app-top-ring .ring-label {
        font-size: 0.62rem;
        margin-top: 2px;
    }

    .app-top-stars {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        background: #ffffff;
        border: 1px solid #ececf2;
        border-radius: 12px;
        padding: 8px 10px;
        min-height: 46px;
        width: 100%;
    }

    .app-top-stars-icon {
        color: #d4a400;
        font-size: 0.95rem;
        line-height: 1;
    }

    .app-top-stars-value {
        color: #2a2d36;
        font-size: 1rem;
        font-weight: 800;
        line-height: 1;
    }

    .app-top-nav-item {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        text-decoration: none !important;
        background: #f1f3f6;
        color: #111318 !important;
        border: 1px solid #e1e5ea;
        border-radius: 12px;
        padding: 7px 10px;
        width: 100%;
        font-size: 0.88rem;
        font-weight: 700;
        box-shadow: 0 6px 12px rgba(30, 38, 56, 0.08);
        transition: transform 0.16s ease, box-shadow 0.16s ease, background 0.16s ease;
    }

    .app-top-nav-item:hover,
    .app-top-nav-item:active,
    .app-top-nav-item:visited {
        text-decoration: none !important;
        color: #111318 !important;
        background: #e9edf2;
        transform: translateY(-1px);
        box-shadow: 0 8px 16px rgba(30, 38, 56, 0.12);
    }

    .app-top-nav-item .app-top-nav-icon {
        font-size: 1rem;
        line-height: 1;
    }

    .app-top-nav-item .app-top-nav-text {
        line-height: 1;
    }

    .app-mid-nav-mobile {
        display: none;
        gap: 7px;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        margin: 4px 0 10px;
    }

    .app-mid-nav-item {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 5px;
        min-height: 38px;
        border-radius: 10px;
        border: 1px solid #e5e6ef;
        background: #ffffff;
        color: #4f5363 !important;
        text-decoration: none !important;
        font-size: 0.8rem;
        font-weight: 700;
    }

    .app-mid-nav-item.is-active {
        background: #f9e8f3;
        border-color: #e3bad3;
        color: #8f0f60 !important;
    }

    .app-mid-nav-icon {
        font-size: 1.15rem;
        line-height: 1;
    }

    .mobile-magenta-dashboard {
        display: none;
        background: linear-gradient(140deg, #cc1188 0%, #a10d6d 100%);
        color: #ffffff;
        border-radius: 14px;
        border: 1px solid rgba(255, 255, 255, 0.22);
        padding: 10px;
        margin-bottom: 10px;
        box-shadow: 0 10px 22px rgba(128, 16, 93, 0.24);
    }

    .mobile-magenta-title {
        font-size: 0.92rem;
        font-weight: 800;
        margin: 0 0 7px 0;
        letter-spacing: 0.1px;
    }

    .mobile-magenta-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 6px;
    }

    .mobile-magenta-pill {
        background: rgba(255, 255, 255, 0.16);
        border: 1px solid rgba(255, 255, 255, 0.26);
        border-radius: 10px;
        padding: 6px 7px;
        text-align: center;
    }

    .mobile-pill-icon {
        font-size: 0.95rem;
        line-height: 1;
        opacity: 0.95;
    }

    .mobile-pill-value {
        font-size: 0.94rem;
        font-weight: 800;
        line-height: 1.15;
        margin-top: 2px;
    }

    .mobile-pill-label {
        font-size: 0.66rem;
        opacity: 0.9;
        margin-top: 2px;
    }

    .summary-strip {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 8px;
        margin: 6px 0 10px;
    }

    .summary-card {
        background: #ffffff;
        border: 1px solid #ececf2;
        border-radius: 12px;
        padding: 8px 10px;
        box-shadow: 0 6px 14px rgba(25, 20, 40, 0.04);
    }

    .summary-label {
        font-size: 0.74rem;
        color: #6d7080;
        font-weight: 700;
        margin-bottom: 2px;
    }

    .summary-value {
        font-size: 1.02rem;
        font-weight: 800;
        color: #2a2d36;
        line-height: 1.1;
    }

    .summary-foot {
        margin-top: 2px;
        font-size: 0.67rem;
        color: #7a7e8d;
    }

    .app-nav-item {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        min-height: 54px;
        text-decoration: none !important;
        background: #ffffff;
        border: 1px solid #ececf2;
        border-radius: 12px;
        color: #505564;
        font-size: 1rem;
        font-weight: 700;
        transition: transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease, background 0.16s ease;
    }

    .app-nav-item:hover,
    .app-nav-item:active,
    .app-nav-item:visited {
        text-decoration: none !important;
        transform: translateY(-1px);
        border-color: #d8d9e6;
        box-shadow: 0 8px 18px rgba(35, 24, 56, 0.12);
    }

    .app-nav-item.is-active {
        background: var(--app-magenta);
        color: #ffffff;
        border-color: var(--app-magenta);
        box-shadow: 0 8px 16px rgba(161, 13, 109, 0.22);
    }

    .app-nav-icon {
        font-size: 2.2rem;
        line-height: 1;
    }

    .app-nav-text {
        display: none;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 10px;
        font-weight: 600;
        color: #5e6170;
        background: transparent;
    }

    .stTabs [aria-selected="true"] {
        background: #ffffff;
        color: var(--app-magenta-strong);
        border: 1px solid #ececf2;
    }

    .stTextInput > div > div,
    .stNumberInput > div > div,
    .stSelectbox > div > div,
    .stDateInput > div > div,
    .stMultiSelect > div > div,
    .stTextArea > div > div {
        border-radius: 11px;
        border: 1px solid #e8e9f0;
        background: #fff;
    }

    .stTextInput > div > div:focus-within,
    .stNumberInput > div > div:focus-within,
    .stSelectbox > div > div:focus-within,
    .stDateInput > div > div:focus-within,
    .stMultiSelect > div > div:focus-within,
    .stTextArea > div > div:focus-within {
        border-color: var(--app-magenta);
        box-shadow: 0 0 0 0.08rem rgba(204, 17, 136, 0.2);
    }

    .stTextInput input,
    .stTextInput input::placeholder,
    .stNumberInput input,
    .stNumberInput input::placeholder,
    .stTextArea textarea,
    .stTextArea textarea::placeholder,
    .stSelectbox [data-baseweb="select"] > div,
    .stMultiSelect [data-baseweb="select"] > div,
    .stSelectbox [data-baseweb="select"] input,
    .stMultiSelect [data-baseweb="select"] input {
        color: #22232a !important;
        -webkit-text-fill-color: #22232a !important;
        opacity: 1 !important;
        background: #ffffff !important;
    }

    .stDateInput input,
    .stDateInput input::placeholder {
        color: #22232a !important;
        -webkit-text-fill-color: #22232a !important;
        opacity: 1 !important;
    }

    .stDateInput label,
    .stNumberInput label,
    .stTextInput label,
    .stSelectbox label {
        color: #5b6170 !important;
        opacity: 1 !important;
        font-weight: 700 !important;
    }

    [data-testid="stWidgetLabel"] p {
        color: #5b6170 !important;
        opacity: 1 !important;
    }

    .stDateInput svg {
        fill: #5e6170 !important;
    }

    /* Gewicht: Datum + Gewicht kompakt in einer Zeile */
    .weight-row-anchor + div[data-testid="stHorizontalBlock"] {
        width: 100%;
        max-width: 360px;
        gap: 8px;
        align-items: flex-end;
    }

    .weight-row-anchor + div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
        min-width: 0;
    }

    .weight-input-row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
        max-width: 340px;
        margin-bottom: 12px;
    }

    .measure-figure-desktop {
        display: flex;
        justify-content: center;
        width: 100%;
    }

    .measure-figure-desktop img {
        display: block;
        width: 120px;
        max-width: 100%;
        height: auto;
    }

    @media (max-width: 900px) {
        .weight-input-row {
            max-width: 100%;
        }

        .measure-figure-desktop {
            display: none !important;
        }
    }

    [data-testid="stDataFrame"] {
        border: 1px solid #ececf2;
        border-radius: 14px;
        overflow: hidden;
        background: #fff;
    }

    div.stExpander {
        border: 1px solid #ececf2;
        border-radius: 12px;
        background: #fff;
    }

    div.stButton > button {
        background: var(--app-magenta);
        color: #fff;
        border: none;
        border-radius: 10px;
        font-weight: 600;
        box-shadow: 0 8px 16px rgba(161, 13, 109, 0.18);
    }

    div.stButton > button:hover {
        background: var(--app-magenta-strong);
        color: #fff;
    }

    html[data-theme="dark"] .stApp,
    body[data-theme="dark"] .stApp {
        background: linear-gradient(180deg, #071021 0%, #0b1730 100%) !important;
        color: #eef4ff !important;
    }

    html[data-theme="dark"] .dashboard-wrap,
    body[data-theme="dark"] .dashboard-wrap,
    html[data-theme="dark"] [data-testid="stMetric"],
    body[data-theme="dark"] [data-testid="stMetric"],
    html[data-theme="dark"] .summary-card,
    body[data-theme="dark"] .summary-card,
    html[data-theme="dark"] .app-top-stars,
    body[data-theme="dark"] .app-top-stars,
    html[data-theme="dark"] .hero-ring,
    body[data-theme="dark"] .hero-ring,
    html[data-theme="dark"] .hero-quick,
    body[data-theme="dark"] .hero-quick,
    html[data-theme="dark"] [data-testid="stDataFrame"],
    body[data-theme="dark"] [data-testid="stDataFrame"],
    html[data-theme="dark"] div.stExpander,
    body[data-theme="dark"] div.stExpander {
        background: #121f38 !important;
        border-color: #2a3f69 !important;
        color: #eef4ff !important;
    }

    html[data-theme="dark"] [data-testid="stMetricLabel"],
    body[data-theme="dark"] [data-testid="stMetricLabel"],
    html[data-theme="dark"] [data-testid="stWidgetLabel"] p,
    body[data-theme="dark"] [data-testid="stWidgetLabel"] p,
    html[data-theme="dark"] .summary-label,
    body[data-theme="dark"] .summary-label,
    html[data-theme="dark"] .summary-foot,
    body[data-theme="dark"] .summary-foot,
    html[data-theme="dark"] .dashboard-sub,
    body[data-theme="dark"] .dashboard-sub,
    html[data-theme="dark"] .ring-label,
    body[data-theme="dark"] .ring-label {
        color: #b9c9ea !important;
    }

    html[data-theme="dark"] [data-testid="stMetricValue"],
    body[data-theme="dark"] [data-testid="stMetricValue"],
    html[data-theme="dark"] .summary-value,
    body[data-theme="dark"] .summary-value,
    html[data-theme="dark"] .dashboard-title,
    body[data-theme="dark"] .dashboard-title,
    html[data-theme="dark"] .app-top-stars-value,
    body[data-theme="dark"] .app-top-stars-value {
        color: #eef4ff !important;
    }

    html[data-theme="dark"] .stTextInput > div > div,
    body[data-theme="dark"] .stTextInput > div > div,
    html[data-theme="dark"] .stNumberInput > div > div,
    body[data-theme="dark"] .stNumberInput > div > div,
    html[data-theme="dark"] .stSelectbox > div > div,
    body[data-theme="dark"] .stSelectbox > div > div,
    html[data-theme="dark"] .stDateInput > div > div,
    body[data-theme="dark"] .stDateInput > div > div,
    html[data-theme="dark"] .stMultiSelect > div > div,
    body[data-theme="dark"] .stMultiSelect > div > div,
    html[data-theme="dark"] .stTextArea > div > div,
    body[data-theme="dark"] .stTextArea > div > div,
    html[data-theme="dark"] .stSelectbox [data-baseweb="select"] > div,
    body[data-theme="dark"] .stSelectbox [data-baseweb="select"] > div,
    html[data-theme="dark"] .stMultiSelect [data-baseweb="select"] > div,
    body[data-theme="dark"] .stMultiSelect [data-baseweb="select"] > div {
        background: #1f3154 !important;
        border-color: #355282 !important;
    }

    html[data-theme="dark"] .stTextInput input,
    html[data-theme="dark"] .stTextInput input::placeholder,
    html[data-theme="dark"] .stNumberInput input,
    html[data-theme="dark"] .stNumberInput input::placeholder,
    html[data-theme="dark"] .stDateInput input,
    html[data-theme="dark"] .stDateInput input::placeholder,
    html[data-theme="dark"] .stTextArea textarea,
    html[data-theme="dark"] .stTextArea textarea::placeholder,
    html[data-theme="dark"] .stSelectbox [data-baseweb="select"] input,
    html[data-theme="dark"] .stMultiSelect [data-baseweb="select"] input,
    html[data-theme="dark"] .stSelectbox [data-baseweb="select"] span,
    html[data-theme="dark"] .stMultiSelect [data-baseweb="select"] span {
        color: #f6f9ff !important;
        -webkit-text-fill-color: #f6f9ff !important;
    }

    html[data-theme="dark"] .app-top-nav-item,
    body[data-theme="dark"] .app-top-nav-item,
    html[data-theme="dark"] .app-top-nav-item:hover,
    body[data-theme="dark"] .app-top-nav-item:hover,
    html[data-theme="dark"] .app-top-nav-item:active,
    body[data-theme="dark"] .app-top-nav-item:active,
    html[data-theme="dark"] .app-top-nav-item:visited,
    body[data-theme="dark"] .app-top-nav-item:visited {
        background: #27406c !important;
        color: #f6f9ff !important;
        border-color: #3e5f97 !important;
        box-shadow: 0 8px 16px rgba(10, 18, 36, 0.35) !important;
    }

    html[data-theme="dark"] div.stButton > button,
    body[data-theme="dark"] div.stButton > button {
        background: #27406c !important;
        color: #f6f9ff !important;
        border: 1px solid #3e5f97 !important;
        box-shadow: 0 8px 16px rgba(10, 18, 36, 0.35) !important;
    }

    html[data-theme="dark"] div.stButton > button:hover,
    body[data-theme="dark"] div.stButton > button:hover {
        background: #335286 !important;
        color: #ffffff !important;
        border-color: #5073af !important;
    }

    html[data-theme="dark"] [data-testid="stToolbar"] button,
    body[data-theme="dark"] [data-testid="stToolbar"] button,
    html[data-theme="dark"] [data-testid="stToolbar"] svg,
    body[data-theme="dark"] [data-testid="stToolbar"] svg {
        color: #e6ebf5 !important;
        fill: #e6ebf5 !important;
        stroke: #e6ebf5 !important;
    }

    html[data-theme="light"] .stApp,
    body[data-theme="light"] .stApp {
        background: linear-gradient(180deg, #fbfbfd 0%, #f4f4f7 100%) !important;
        color: #22232a !important;
    }

    html[data-theme="light"] .dashboard-wrap,
    body[data-theme="light"] .dashboard-wrap,
    html[data-theme="light"] [data-testid="stMetric"],
    body[data-theme="light"] [data-testid="stMetric"],
    html[data-theme="light"] .summary-card,
    body[data-theme="light"] .summary-card,
    html[data-theme="light"] .app-top-stars,
    body[data-theme="light"] .app-top-stars,
    html[data-theme="light"] .hero-ring,
    body[data-theme="light"] .hero-ring,
    html[data-theme="light"] .hero-quick,
    body[data-theme="light"] .hero-quick,
    html[data-theme="light"] [data-testid="stDataFrame"],
    body[data-theme="light"] [data-testid="stDataFrame"],
    html[data-theme="light"] div.stExpander,
    body[data-theme="light"] div.stExpander {
        background: #ffffff !important;
        border-color: #ececf2 !important;
        color: #22232a !important;
    }

    html[data-theme="light"] .stTextInput > div > div,
    body[data-theme="light"] .stTextInput > div > div,
    html[data-theme="light"] .stNumberInput > div > div,
    body[data-theme="light"] .stNumberInput > div > div,
    html[data-theme="light"] .stSelectbox > div > div,
    body[data-theme="light"] .stSelectbox > div > div,
    html[data-theme="light"] .stDateInput > div > div,
    body[data-theme="light"] .stDateInput > div > div,
    html[data-theme="light"] .stMultiSelect > div > div,
    body[data-theme="light"] .stMultiSelect > div > div,
    html[data-theme="light"] .stTextArea > div > div,
    body[data-theme="light"] .stTextArea > div > div,
    html[data-theme="light"] .stSelectbox [data-baseweb="select"] > div,
    body[data-theme="light"] .stSelectbox [data-baseweb="select"] > div,
    html[data-theme="light"] .stMultiSelect [data-baseweb="select"] > div,
    body[data-theme="light"] .stMultiSelect [data-baseweb="select"] > div {
        background: #f3f5f8 !important;
        border-color: #e8e9f0 !important;
    }

    html[data-theme="light"] .stTextInput input,
    html[data-theme="light"] .stTextInput input::placeholder,
    html[data-theme="light"] .stNumberInput input,
    html[data-theme="light"] .stNumberInput input::placeholder,
    html[data-theme="light"] .stDateInput input,
    html[data-theme="light"] .stDateInput input::placeholder,
    html[data-theme="light"] .stTextArea textarea,
    html[data-theme="light"] .stTextArea textarea::placeholder,
    html[data-theme="light"] .stSelectbox [data-baseweb="select"] input,
    html[data-theme="light"] .stMultiSelect [data-baseweb="select"] input,
    html[data-theme="light"] .stSelectbox [data-baseweb="select"] span,
    html[data-theme="light"] .stMultiSelect [data-baseweb="select"] span {
        color: #22232a !important;
        -webkit-text-fill-color: #22232a !important;
    }

    @media (max-width: 900px) {
        .main .block-container {
            padding-top: 0.8rem;
            padding-left: 0.75rem;
            padding-right: 0.75rem;
            padding-bottom: 2rem;
        }

        .app-top-nav {
            gap: 8px;
            flex-wrap: wrap;
        }

        .app-top-nav-item {
            min-height: 42px;
            padding: 8px 10px;
        }

        .mobile-magenta-dashboard {
            display: block;
        }

        [data-testid="stSidebar"] {
            display: none;
        }

        .sidebar-ring .ring {
            --size: 108px;
        }

        .hero-grid {
            grid-template-columns: 1fr;
            grid-template-areas:
                "ring"
                "card1"
                "card2"
                "quick";
        }

        .kpi-grid {
            grid-template-columns: 1fr 1fr;
        }

        .app-bottom-nav {
            display: none !important;
        }

        .app-mid-nav-mobile {
            display: grid;
        }

        [data-baseweb="popover"],
        [role="dialog"] {
            z-index: 1200 !important;
        }

        .app-bottom-nav {
            gap: 6px;
            grid-template-columns: repeat(5, minmax(0, 1fr));
        }

        .app-nav-item {
            min-height: 44px;
            font-size: 0.78rem;
            border-radius: 12px;
            gap: 6px;
        }

        .app-nav-icon {
            font-size: 1.8rem;
        }
    }

    @media (max-width: 560px) {
        .main .block-container {
            padding-left: 0.55rem;
            padding-right: 0.55rem;
            padding-bottom: 1.2rem;
        }

        [data-testid="stMetric"] {
            padding: 8px 10px;
        }

        .app-top-nav {
            display: grid;
            grid-template-columns: 1fr 1fr;
            width: 100%;
        }

        .app-top-nav-item {
            justify-content: center;
            width: 100%;
            border-radius: 11px;
            font-size: 0.82rem;
            min-height: 44px;
            padding: 8px;
            gap: 0;
        }

        .app-top-nav-item .app-top-nav-text {
            display: none;
        }

        .app-top-nav-item .app-top-nav-icon {
            font-size: 1.15rem;
        }

        /* Nur der Gewichts-Row: Datum + Gewicht nebeneinander, gleiche Breite wie Top-Buttons */
        .weight-inline-anchor + div[data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            gap: 8px !important;
            width: 100% !important;
            max-width: 100% !important;
            align-items: flex-end !important;
        }

        .weight-inline-anchor + div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
            min-width: 0 !important;
        }

        .weight-inline-anchor + div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(1) {
            flex: 0 0 calc(50% - 4px) !important;
            width: calc(50% - 4px) !important;
            min-width: calc(50% - 4px) !important;
        }

        .weight-inline-anchor + div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(2) {
            flex: 0 0 calc(50% - 4px) !important;
            width: calc(50% - 4px) !important;
            min-width: calc(50% - 4px) !important;
        }

        .weight-inline-anchor + div[data-testid="stHorizontalBlock"] [data-testid="stDateInput"],
        .weight-inline-anchor + div[data-testid="stHorizontalBlock"] [data-testid="stNumberInput"] {
            width: 100% !important;
        }

        .mobile-magenta-title {
            font-size: 0.84rem;
            margin-bottom: 6px;
        }

        .mobile-magenta-grid {
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 4px;
        }

        .mobile-magenta-pill {
            padding: 4px 3px;
            border-radius: 8px;
        }

        .mobile-pill-icon {
            font-size: 0.82rem;
        }

        .mobile-pill-value {
            font-size: 0.85rem;
            margin-top: 1px;
        }

        .mobile-pill-label {
            font-size: 0.60rem;
            margin-top: 1px;
        }

        .summary-strip {
            gap: 5px;
            margin: 4px 0 8px;
        }

        .summary-card {
            padding: 6px 6px;
            border-radius: 10px;
        }

        .summary-label {
            font-size: 0.62rem;
            margin-bottom: 1px;
        }

        .summary-value {
            font-size: 0.88rem;
        }

        .summary-foot {
            font-size: 0.56rem;
            margin-top: 1px;
        }

        .app-nav-item {
            min-height: 48px;
        }

        .app-mid-nav-mobile {
            gap: 6px;
        }

        .app-mid-nav-item {
            min-height: 36px;
            font-size: 0.72rem;
            gap: 0;
        }

        .app-mid-nav-item .app-mid-nav-text {
            display: none;
        }

        .app-mid-nav-icon {
            font-size: 1.25rem;
        }

        .stMarkdown p,
        .stCaption {
            font-size: 0.78rem;
        }

        [data-testid="stMetricLabel"] {
            font-size: 0.72rem;
        }

        [data-testid="stMetricValue"] {
            font-size: 1.05rem;
        }

        .dashboard-top {
            align-items: flex-start;
            flex-direction: column;
        }

        .kpi-grid {
            grid-template-columns: 1fr;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

store = load_store()
profile = store["profile"]

# Linke Navigation und Kopfzähler auf Live-Eingaben beziehen (nicht erst nach Speichern)
live_profile = dict(profile)
if "p_gender" in st.session_state:
    live_profile["gender"] = st.session_state["p_gender"]
if "p_birth" in st.session_state:
    live_profile["birth_date"] = st.session_state["p_birth"].isoformat()
if "p_height" in st.session_state:
    live_profile["height"] = float(st.session_state["p_height"])
if "p_startw" in st.session_state:
    live_profile["start_weight"] = float(st.session_state["p_startw"])
if "p_curw" in st.session_state:
    live_profile["current_weight"] = float(st.session_state["p_curw"])
if "p_goalw" in st.session_state:
    live_profile["goal_weight"] = float(st.session_state["p_goalw"])
if "p_activity" in st.session_state:
    live_profile["activity_level"] = st.session_state["p_activity"]
if "p_goal" in st.session_state:
    live_profile["weight_goal"] = st.session_state["p_goal"]
if "p_weigh_day" in st.session_state:
    live_profile["weigh_day"] = st.session_state["p_weigh_day"]
if "p_activity_extra_mode" in st.session_state:
    live_profile["activity_extra_mode"] = st.session_state["p_activity_extra_mode"]

# Permanente Zähler direkt auf der Seite
d_points = daily_points(live_profile)
w_extra = weekly_extra_points(live_profile)
week_start = current_weigh_week_start(live_profile)
w_used = weekly_extra_used(store["logs"], week_start, live_profile, date.today())
w_remaining = max(0.0, w_extra - w_used)

today_key = date.today().isoformat()
today_log = next((l for l in store["logs"] if l.get("date") == today_key), None)
today_used = 0.0 if not today_log else sum(float(e["points"]) for e in today_log.get("entries", []))
today_bonus = 0 if (not today_log or not activity_points_enabled(live_profile)) else int(today_log.get("bonus", 0))
today_target = d_points + today_bonus
today_remaining = max(0.0, today_target - today_used)

day_progress_pct = 0.0 if today_target <= 0 else max(0.0, min(100.0, (today_used / today_target) * 100.0))
goal_total = max(0.1, float(live_profile["start_weight"]) - float(live_profile["goal_weight"]))
goal_done = max(0.0, float(live_profile["start_weight"]) - float(live_profile["current_weight"]))
goal_pct = max(0.0, min(100.0, (goal_done / goal_total) * 100.0))
stars_count = stars_earned(float(live_profile["start_weight"]), float(live_profile["current_weight"]))

st.markdown(
    f'''
    <div class="app-top-nav">
        <a class="app-top-nav-item" href="?nav=stats" title="Statistik öffnen">
            <span class="app-top-nav-icon">📊</span><span class="app-top-nav-text">Statistik</span>
        </a>
        <a class="app-top-nav-item" href="?nav=profil" title="Profil öffnen">
            <span class="app-top-nav-icon">👤</span><span class="app-top-nav-text">Profil</span>
        </a>
        <div class="app-top-ring" title="Punkte übrig">
            <div class="ring" style="--p:{day_progress_pct:.1f};">
                <div class="ring-inner">
                    <div class="ring-value">{today_remaining:.0f}</div>
                    <div class="ring-label">Übrig</div>
                </div>
            </div>
        </div>
        <div class="app-top-stars" title="Sterne">
            <span class="app-top-stars-icon">⭐⭐⭐</span>
            <span class="app-top-stars-value">{stars_count}</span>
        </div>
    </div>
    ''',
    unsafe_allow_html=True,
)

mobile_nav_page = str(st.session_state.get("main_nav", "mahlz"))
mobile_nav_items = [
    {"page": "mahlz", "icon": "🍽️", "label": "Mahlz."},
    {"page": "aktiv", "icon": "🏃", "label": "Aktiv."},
    {"page": "gewicht", "icon": "⚖️", "label": "Gewicht"},
    {"page": "masze", "icon": "📏", "label": "Maße"},
    {"page": "food", "icon": "🍎", "label": "Food"},
]
mobile_nav_html = []
for item in mobile_nav_items:
    active_class = " is-active" if mobile_nav_page == item["page"] else ""
    mobile_nav_html.append(
        f'<a class="app-mid-nav-item{active_class}" href="?nav={item["page"]}" title="{item["label"]}">'
        f'<span class="app-mid-nav-icon">{item["icon"]}</span><span class="app-mid-nav-text">{item["label"]}</span></a>'
    )

st.markdown(f'<nav class="app-mid-nav-mobile">{"".join(mobile_nav_html)}</nav>', unsafe_allow_html=True)

st.markdown(
    f"""
    <div class="mobile-magenta-dashboard">
        <div class="mobile-magenta-title">MeinTagebuch</div>
        <div class="mobile-magenta-grid">
            <div class="mobile-magenta-pill">
                <div class="mobile-pill-icon">⭐</div>
                <div class="mobile-pill-value">{today_remaining:.0f}</div>
                <div class="mobile-pill-label">Heute</div>
            </div>
            <div class="mobile-magenta-pill">
                <div class="mobile-pill-icon">🎯</div>
                <div class="mobile-pill-value">{w_remaining:.0f}</div>
                <div class="mobile-pill-label">Extra</div>
            </div>
            <div class="mobile-magenta-pill">
                <div class="mobile-pill-icon">📅</div>
                <div class="mobile-pill-value">{live_profile.get('weigh_day', 'Mo')[:2]}</div>
                <div class="mobile-pill-label">Tag</div>
            </div>
            <div class="mobile-magenta-pill">
                <div class="mobile-pill-icon">🏅</div>
                <div class="mobile-pill-value">{stars_earned(float(live_profile['start_weight']), float(live_profile['current_weight']))}</div>
                <div class="mobile-pill-label">Sterne</div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="summary-strip">
        <div class="summary-card">
            <div class="summary-label">⭐ Heute</div>
            <div class="summary-value">{today_remaining:.1f}</div>
            <div class="summary-foot">{today_used:.1f} / {today_target:.1f}</div>
        </div>
        <div class="summary-card">
            <div class="summary-label">🎯 Extra</div>
            <div class="summary-value">{w_remaining:.1f}</div>
            <div class="summary-foot">{w_used:.1f} / {w_extra:.1f}</div>
        </div>
        <div class="summary-card">
            <div class="summary-label">📅 Tag</div>
            <div class="summary-value">{live_profile.get('weigh_day', 'Montag')}</div>
            <div class="summary-foot">Erneuert</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if "main_nav" not in st.session_state:
    st.session_state["main_nav"] = "mahlz"

if "bottom_nav" not in st.session_state:
    st.session_state["bottom_nav"] = "🍽️ Mahlz."

if "last_bottom_nav" not in st.session_state:
    st.session_state["last_bottom_nav"] = st.session_state["bottom_nav"]

if "header_override" not in st.session_state:
    st.session_state["header_override"] = False

if st.session_state["main_nav"] in ["Mahlzeiten", "🍽️ Mahlz."]:
    st.session_state["main_nav"] = "mahlz"
if st.session_state["main_nav"] in ["Lebensmittel", "🍎 Food"]:
    st.session_state["main_nav"] = "food"
if st.session_state["main_nav"] in ["Sport", "Schritte", "🏃 Sport", "👣 Schritte"]:
    st.session_state["main_nav"] = "aktiv"
if st.session_state["main_nav"] in ["Gewicht", "⚖️ Gewicht"]:
    st.session_state["main_nav"] = "gewicht"
if st.session_state["main_nav"] in ["Profil", "👤 Profil"]:
    st.session_state["main_nav"] = "profil"
if st.session_state["main_nav"] in ["Statistik", "📊 Stats"]:
    st.session_state["main_nav"] = "stats"

bottom_labels = ["🍽️ Mahlz.", "🍎 Food", "🏃 Aktiv.", "⚖️ Gewicht"]
label_to_page = {
    "🍽️ Mahlz.": "mahlz",
    "🏃 Aktiv.": "aktiv",
    "⚖️ Gewicht": "gewicht",
    "📏 Maße": "masze",
    "🍎 Food": "food",
}
page_to_label = {v: k for k, v in label_to_page.items()}

query_nav = st.query_params.get("nav")
if isinstance(query_nav, list):
    query_nav = query_nav[0] if query_nav else None

if query_nav in page_to_label:
    st.session_state["main_nav"] = query_nav
    st.session_state["header_override"] = False
    st.session_state["bottom_nav"] = page_to_label[query_nav]
    st.session_state["last_bottom_nav"] = page_to_label[query_nav]
elif query_nav in ["stats", "profil"]:
    st.session_state["main_nav"] = query_nav
    st.session_state["header_override"] = True


# Nur Bottom-Nav aktualisieren, wenn wir auf einer Bottom-Nav-Seite sind
if st.session_state["main_nav"] in page_to_label:
    st.session_state["bottom_nav"] = page_to_label[st.session_state["main_nav"]]
    st.session_state["last_bottom_nav"] = st.session_state["bottom_nav"]
# Wenn ungültige Seite (nicht profil, stats, oder in page_to_label), zurück auf mahlz
elif st.session_state["main_nav"] not in ["profil", "stats"]:
    st.session_state["main_nav"] = "mahlz"
    st.session_state["bottom_nav"] = page_to_label[st.session_state["main_nav"]]
    st.session_state["last_bottom_nav"] = st.session_state["bottom_nav"]

nav_items = [
    {"page": "mahlz", "icon": "🍽️", "label": "Mahlz.", "tooltip": "Mahlzeiten eintragen"},
    {"page": "aktiv", "icon": "🏃", "label": "Aktiv.", "tooltip": "Aktivitäten eintragen"},
    {"page": "gewicht", "icon": "⚖️", "label": "Gewicht", "tooltip": "Gewicht eintragen"},
    {"page": "masze", "icon": "📏", "label": "Maße", "tooltip": "Körpermaße eintragen"},
    {"page": "food", "icon": "🍎", "label": "Food", "tooltip": "Neue Lebensmittel oder Rezepte eingeben"},
]

nav_html_parts = []
for item in nav_items:
    active_class = " is-active" if st.session_state["main_nav"] == item["page"] else ""
    nav_html_parts.append(
        f'<a class="app-nav-item{active_class}" href="?nav={item["page"]}" '
        f'title="{item["tooltip"]}" aria-label="{item["tooltip"]}">'
        f'<span class="app-nav-icon">{item["icon"]}</span><span class="app-nav-text">{item["label"]}</span></a>'
    )

st.markdown(f'<nav class="app-bottom-nav">{"".join(nav_html_parts)}</nav>', unsafe_allow_html=True)

active_page = st.session_state["main_nav"]

if active_page == "profil":
    st.subheader("Profil")
    if st.button("← Zurück zur App", key="back_from_profile"):
        st.session_state["main_nav"] = "mahlz"
        st.session_state["bottom_nav"] = "🍽️ Mahlz."
        st.session_state["last_bottom_nav"] = "🍽️ Mahlz."
        st.session_state["header_override"] = False
        st.rerun()

    name = st.text_input("Name", value=profile["name"], key="p_name")
    col1, col2, col3 = st.columns(3)
    with col1:
        gender = st.selectbox("Geschlecht", ["Weiblich", "Männlich"],
                              index=0 if profile["gender"] == "Weiblich" else 1,
                              key="p_gender")
    with col2:
        birth = st.date_input("Geburtsdatum",
                              value=datetime.strptime(profile["birth_date"], "%Y-%m-%d").date(),
                              min_value=date(1920, 1, 1),
                              max_value=date.today(),
                              format="DD.MM.YYYY",
                              key="p_birth")
    with col3:
        plan = st.selectbox("Plan", ["Restriktiv", "Ausgewogen", "Liberal"],
                            index=["Restriktiv", "Ausgewogen", "Liberal"].index(profile["plan"]),
                            key="p_plan")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        height = st.number_input("Größe (cm)", min_value=120.0, max_value=230.0,
                                 value=float(profile["height"]), step=0.5, key="p_height")
    with c2:
        start_w = st.number_input("Startgewicht (kg)", min_value=30.0, max_value=300.0,
                                  value=float(profile["start_weight"]), step=0.1, key="p_startw")
    with c3:
        current_w = st.number_input("Aktuell (kg)", min_value=30.0, max_value=300.0,
                                    value=float(profile["current_weight"]), step=0.1, key="p_curw")
    with c4:
        goal_w = st.number_input("Zielgewicht (kg)", min_value=30.0, max_value=300.0,
                                 value=float(profile["goal_weight"]), step=0.1, key="p_goalw")

    activity = st.selectbox(
        "Aktivität",
        ["Kaum Bewegung", "Wenig Bewegung", "Viel Bewegung", "Täglich viel Bewegung"],
        index=["Kaum Bewegung", "Wenig Bewegung", "Viel Bewegung", "Täglich viel Bewegung"].index(profile["activity_level"]),
        key="p_activity",
    )
    current_activity_mode = profile.get("activity_extra_mode", DEFAULT_PROFILE["activity_extra_mode"])
    if current_activity_mode not in ALLOWED_ACTIVITY_EXTRA_MODES:
        current_activity_mode = DEFAULT_PROFILE["activity_extra_mode"]

    activity_extra_mode = st.selectbox(
        "Aktivitätspunkte verwenden",
        ALLOWED_ACTIVITY_EXTRA_MODES,
        index=ALLOWED_ACTIVITY_EXTRA_MODES.index(current_activity_mode),
        key="p_activity_extra_mode",
    )
    goal = st.selectbox("Ziel", ["Abnehmen", "Gewicht halten"],
                        index=0 if profile["weight_goal"] == "Abnehmen" else 1,
                        key="p_goal")

    # Live-Vorschau der Punkte
    preview_profile = {
        "gender": gender,
        "birth_date": birth.isoformat(),
        "height": height,
        "current_weight": current_w,
        "activity_level": activity,
        "weight_goal": goal,
    }
    preview_daily = daily_points(preview_profile)
    weigh_day = st.selectbox("Wiegetag (Wochenextrapunkte erneuern)", WEIGH_DAYS,
                              index=WEIGH_DAYS.index(profile.get("weigh_day", "Montag")),
                              key="p_weigh_day")

    preview_extra = weekly_extra_points({"current_weight": current_w})
    pc1, pc2, pc3 = st.columns(3)
    pc1.info(f"Tagespunkte (Vorschau): **{preview_daily}**")
    pc2.info(f"Wochenextra (Vorschau): **{preview_extra}**")
    pc3.caption("Regel: 100 kg = 35, je 10 kg weniger = -5, Minimum 15.")

    with st.expander("Temporäre Berechnung anzeigen (live)", expanded=True):
        breakdown_rows, breakdown_total, breakdown_age = daily_points_breakdown(preview_profile)
        st.dataframe(pd.DataFrame(breakdown_rows), width="stretch", hide_index=True)
        st.caption(f"Berechnetes Alter aus Geburtsdatum: {breakdown_age} Jahre")
        st.info(f"Summe Tagespunkte: {breakdown_total}")
        st.caption("Hinweis: Alterspunkte ändern sich nur beim Wechsel der Altersstufe (18-20, 21-35, 36-50, 51-65, 66+).")

    if st.button("Profil speichern", key="save_profile"):
        store["profile"] = {
            "name": name,
            "gender": gender,
            "birth_date": birth.isoformat(),
            "height": height,
            "start_weight": start_w,
            "current_weight": current_w,
            "goal_weight": goal_w,
            "activity_level": activity,
            "weight_goal": goal,
            "plan": plan,
            "weigh_day": weigh_day,
            "activity_extra_mode": activity_extra_mode,
        }
        save_store(store)
        st.success("Profil gespeichert")

    st.divider()
    st.write("Profil sichern und wiederherstellen")
    st.caption("Du kannst dein Profil als JSON exportieren, per E-Mail verschicken und spaeter wieder importieren.")

    export_json = json.dumps(store.get("profile", DEFAULT_PROFILE), ensure_ascii=False, indent=2)
    st.download_button(
        "Profil als JSON exportieren",
        data=export_json.encode("utf-8"),
        file_name="mein_tagebuch_profil.json",
        mime="application/json",
        key="profile_export_btn",
    )

    uploaded_profile_file = st.file_uploader(
        "Profil-JSON importieren",
        type=["json"],
        key="profile_import_file",
        help="Datei waehlen und danach auf Import klicken.",
    )

    if st.button("Profil aus Datei importieren", key="profile_import_btn"):
        if uploaded_profile_file is None:
            st.error("Bitte zuerst eine JSON-Datei auswaehlen.")
        else:
            try:
                imported_raw = json.loads(uploaded_profile_file.getvalue().decode("utf-8"))
                imported_profile = sanitize_profile_data(imported_raw)
                store["profile"] = imported_profile
                save_store(store)
                set_profile_form_state(imported_profile)

                st.success("Profil erfolgreich importiert.")
                st.rerun()
            except Exception:
                st.error("Import fehlgeschlagen. Bitte eine gueltige Profil-JSON verwenden.")

    st.divider()
    st.write("Komplette App-Daten sichern (inkl. Mahlzeiten und Aktivitäten)")
    st.caption("Exportiere alle Daten als JSON und importiere sie auf einem anderen Geraet (Windows, iPhone, iPad).")

    full_backup_payload = build_backup_payload(store)
    full_backup_json = json.dumps(full_backup_payload, ensure_ascii=False, indent=2)
    backup_date = datetime.now().strftime("%Y-%m-%d")
    st.download_button(
        "Komplett-Backup exportieren",
        data=full_backup_json.encode("utf-8"),
        file_name=f"mein_tagebuch_backup_{backup_date}.json",
        mime="application/json",
        key="full_backup_export_btn",
    )

    uploaded_backup_file = st.file_uploader(
        "Komplett-Backup importieren",
        type=["json"],
        key="full_backup_import_file",
        help="Import ersetzt die aktuellen Daten in dieser App-Instanz.",
    )

    if st.button("Komplett-Backup importieren", key="full_backup_import_btn"):
        if uploaded_backup_file is None:
            st.error("Bitte zuerst eine Backup-JSON auswaehlen.")
        else:
            try:
                imported_backup_raw = json.loads(uploaded_backup_file.getvalue().decode("utf-8"))
                imported_data = sanitize_backup_data(imported_backup_raw)
                store.clear()
                store.update(imported_data)
                save_store(store)
                set_profile_form_state(store.get("profile", DEFAULT_PROFILE))
                st.success("Backup erfolgreich importiert. Mahlzeiten, Aktivitäten und Schritte sind aktualisiert.")
                st.rerun()
            except Exception:
                st.error("Backup-Import fehlgeschlagen. Bitte eine gueltige Backup-JSON verwenden.")

if active_page == "food":
    all_foods = sort_foods_by_usage(store["foods"], store["logs"])
    foods = list(all_foods)
    selected_food = None

    if all_foods:
        food_options = [f"{f['name']} ({f.get('category', 'Sonstiges')})" for f in all_foods]
        selected_option = st.selectbox(
            "🔍 Lebensmittel suchen (Tippen für Vorschläge)",
            food_options,
            key="foods_search_select",
            help="Tippe im Feld, um passende Lebensmittel direkt vorgeschlagen zu bekommen.",
        )
        st.caption("Reihenfolge priorisiert heute/gestern/häufig verwendete Lebensmittel.")
        selected_index = food_options.index(selected_option)
        selected_food = all_foods[selected_index]
        foods = [selected_food]
    else:
        st.warning("Keine Lebensmittel vorhanden")

    rows = []
    for f in foods:
        pts = food_points_for_plan(f, store["profile"]["plan"])
        display_portion = int(math.floor(float(f["portion_g"]) + 0.5))
        display_points = int(math.floor(float(pts) + 0.5))
        rows.append({
            "Name": f["name"],
            "Kategorie": f["category"],
            "Portion (g)": display_portion,
            "Punkte": display_points,
            "Ohne Punkte": "Ja" if display_points == 0 else "Nein",
        })
    food_df = pd.DataFrame(rows)
    if not food_df.empty:
        st.table(
            food_df.style.set_properties(
                **{
                    "background-color": "#ffffff",
                    "color": "#22232a",
                    "border-color": "#ececf2",
                }
            ).set_table_styles(
                [
                    {
                        "selector": "th",
                        "props": [
                            ("background-color", "#ffffff"),
                            ("color", "#22232a"),
                            ("border-color", "#ececf2"),
                            ("font-weight", "700"),
                        ],
                    },
                    {
                        "selector": "td",
                        "props": [
                            ("background-color", "#ffffff"),
                            ("color", "#22232a"),
                            ("border-color", "#ececf2"),
                        ],
                    },
                ]
            )
        )
    else:
        st.table(food_df)

    st.caption("Die Tabelle zeigt das aktuell ausgewählte Lebensmittel mit heller Darstellung an.")
    if selected_food:
        st.write("Ausgewähltes Lebensmittel")
        d1, d2, d3 = st.columns(3)
        with d1:
            st.metric("Kalorien (kcal)", f"{float(selected_food.get('kcal', 0.0)):.1f}")
            st.metric("Portion (g)", f"{float(selected_food.get('portion_g', 0.0)):.1f}")
            st.metric("Punkte", f"{food_points_for_plan(selected_food, store['profile']['plan']):.1f}")
        with d2:
            st.metric("Fett (g)", f"{float(selected_food.get('fat', 0.0)):.1f}")
            st.metric("Ges. Fett (g)", f"{float(selected_food.get('sat_fat', 0.0)):.1f}")
            st.metric("Zucker (g)", f"{float(selected_food.get('sugar', 0.0)):.1f}")
        with d3:
            st.metric("Eiweiß (g)", f"{float(selected_food.get('protein', 0.0)):.1f}")
            st.metric("Kategorie", selected_food.get("category", "-"))
            zero_flags = []
            if bool(selected_food.get("zr", False)):
                zero_flags.append("Restriktiv")
            if bool(selected_food.get("zb", False)):
                zero_flags.append("Ausgewogen")
            if bool(selected_food.get("zl", False)):
                zero_flags.append("Liberal")
            st.metric("Ohne Punkte in", ", ".join(zero_flags) if zero_flags else "-" )

    st.divider()
    st.write("Internet-Import")
    st.caption("Suche direkt online (Open Food Facts) und importiere ein Produkt in Eigene Lebensmittel.")

    s1, s2 = st.columns([3, 1])
    with s1:
        online_query = st.text_input("Produkt im Internet suchen", placeholder="z. B. körniger Frischkäse", key="food_online_query")
    with s2:
        do_online_search = st.button("Suchen", key="food_online_search")

    if "food_online_results" not in st.session_state:
        st.session_state["food_online_results"] = []

    if do_online_search:
        if not online_query.strip():
            st.warning("Bitte Suchbegriff eingeben.")
        else:
            st.session_state["food_online_results"] = search_foods_online(online_query, page_size=12)
            if not st.session_state["food_online_results"]:
                st.info("Keine Treffer oder aktuell keine Internetverbindung.")

    online_results = st.session_state.get("food_online_results", [])
    if online_results:
        online_labels = [
            f"{f['name']} | {f.get('kcal', 0.0):.0f} kcal/100g | {f.get('points', 0.0):.1f} P"
            for f in online_results
        ]
        selected_online_label = st.selectbox("Online-Treffer", online_labels, key="food_online_pick")
        selected_online = online_results[online_labels.index(selected_online_label)]

        oc1, oc2, oc3, oc4 = st.columns(4)
        with oc1:
            st.metric("kcal/100g", f"{selected_online.get('kcal', 0.0):.1f}")
        with oc2:
            st.metric("Fett", f"{selected_online.get('fat', 0.0):.1f} g")
        with oc3:
            st.metric("Zucker", f"{selected_online.get('sugar', 0.0):.1f} g")
        with oc4:
            st.metric("Punkte", f"{selected_online.get('points', 0.0):.1f}")

        if st.button("Auswahl in Eigene Lebensmittel importieren", key="food_online_import"):
            existing_names = {food_name_key(f.get("name", "")) for f in store.get("foods", [])}
            import_name_key = food_name_key(selected_online.get("name", ""))
            if import_name_key in existing_names:
                st.warning("Dieses Lebensmittel ist bereits vorhanden.")
            else:
                store["foods"].append(dict(selected_online))
                save_store(store)
                st.success(f"Importiert: {selected_online.get('name', 'Unbekannt')}")
                st.rerun()

    st.divider()
    st.write("Eigenes Lebensmittel")
    with st.form("add_food"):
        n1, n2, n3 = st.columns(3)
        with n1:
            name = st.text_input("Name", key="food_name")
            cat = st.text_input("Kategorie", value="Sonstiges")
            portion = st.number_input("Portion (g)", min_value=1.0, value=100.0, step=1.0)
        with n2:
            kcal = st.number_input("kcal", min_value=0.0, value=100.0, step=1.0)
            fat = st.number_input("Fett", min_value=0.0, value=2.0, step=0.1)
            sat = st.number_input("Ges. Fett", min_value=0.0, value=0.5, step=0.1)
        with n3:
            sugar = st.number_input("Zucker", min_value=0.0, value=1.0, step=0.1)
            protein = st.number_input("Eiweiß", min_value=0.0, value=5.0, step=0.1)
            points_manual = st.checkbox("Punkte manuell setzen", value=False)

        pcol1, pcol2, pcol3 = st.columns(3)
        with pcol1:
            zr = st.checkbox("Ohne Punkte (Restriktiv)", value=False)
        with pcol2:
            zb = st.checkbox("Ohne Punkte (Ausgewogen)", value=False)
        with pcol3:
            zl = st.checkbox("Ohne Punkte (Liberal)", value=False)

        points = calc_food_points(kcal, fat, sat, sugar, protein)
        st.caption(f"Berechnet: {points:.1f} Punkte")
        manual_points = st.number_input("Punkte", min_value=0.0, value=float(points), step=0.5)

        if st.form_submit_button("Lebensmittel speichern"):
            if not name.strip():
                st.error("Bitte Name eingeben")
            else:
                store["foods"].append({
                    "name": name.strip(),
                    "category": cat.strip() or "Sonstiges",
                    "portion_g": portion,
                    "kcal": kcal,
                    "fat": fat,
                    "sat_fat": sat,
                    "sugar": sugar,
                    "protein": protein,
                    "points": manual_points if points_manual else points,
                    "zr": zr,
                    "zb": zb,
                    "zl": zl,
                })
                save_store(store)
                st.success("Lebensmittel gespeichert")

if active_page == "mahlz":
    d = weekly_strip_nav("mahlz_day", store["profile"], store)
    day = d.isoformat()
    log = todays_log(store["logs"], day)
    log.setdefault("steps", 0)

    meals_count = len(log.get("entries", []))

    c_meals, _ = st.columns([1, 2])
    with c_meals:
        st.metric("🍽️ Mahlzeiten", meals_count)

    left, right = st.columns([2, 1])
    with left:
        quick_entries = recent_log_entries(store["logs"], limit=5)
        if quick_entries:
            st.write("⏱️ Schnellwahl")
            st.markdown('<div class="quick-buttons-anchor"></div>', unsafe_allow_html=True)
            q_cols = st.columns(5, gap="small")
            for idx, q in enumerate(quick_entries):
                q_col = q_cols[idx]
                name = str(q.get("name", "")).strip()
                label = name if len(name) <= 20 else f"{name[:19]}…"
                with q_col:
                    if st.button(label, key=f"quick_add_{idx}"):
                        log["entries"].append(
                            {
                                "name": q["name"],
                                "amount": q["amount"],
                                "meal": q["meal"],
                                "points": q["points"],
                                "time": datetime.now().isoformat(timespec="seconds"),
                                "is_combo": q.get("is_combo", False),
                            }
                        )
                        log["daily_pts_snapshot"] = daily_points(store["profile"])
                        save_store(store)
                        st.success(f"{q['name']} hinzugefügt")
                        st.rerun()

            st.caption("Die 5 zuletzt genutzten Einträge stehen hier oben zur Schnellwahl.")

        ordered_foods = sort_foods_by_usage(store["foods"], store["logs"])
        combos = list(store.get("combos", []))
        score_map = usage_scores_from_logs(store["logs"])
        favorite_keys = set(store.get("favorites", []))

        combos = sorted(
            combos,
            key=lambda c: (
                0 if favorite_key("combo", c.get("name", "")) in favorite_keys else 1,
                -score_map.get(c.get("name", ""), 0.0),
                c.get("name", "").lower(),
            ),
        )
        ordered_foods = sorted(
            ordered_foods,
            key=lambda f: (
                0 if favorite_key("food", f.get("name", "")) in favorite_keys else 1,
                -score_map.get(f.get("name", ""), 0.0),
                f.get("name", "").lower(),
            ),
        )

        food_by_name = {f.get("name", "").strip().lower(): f for f in ordered_foods}
        combo_by_name = {c.get("name", "").strip().lower(): c for c in combos}
        pinned_items = []
        for fav in store.get("favorites", []):
            if ":" not in str(fav):
                continue
            kind, raw_name = str(fav).split(":", 1)
            if kind == "food":
                item_food = food_by_name.get(raw_name)
                if item_food:
                    pinned_items.append({"kind": "food", "value": item_food})
            elif kind == "combo":
                item_combo = combo_by_name.get(raw_name)
                if item_combo:
                    pinned_items.append({"kind": "combo", "value": item_combo})

        if pinned_items:
            st.write("📌 Favoriten")
            fav_meal = st.selectbox(
                "🍽️ Mahlz.",
                ["Frühstück", "Mittagessen", "Abendessen", "Snack"],
                key="fav_quick_meal",
            )
            p_cols = st.columns(2)
            for idx, item in enumerate(pinned_items):
                p_col = p_cols[idx % 2]
                with p_col:
                    if item["kind"] == "food":
                        fav_food = item["value"]
                        fav_amount = float(fav_food.get("portion_g", 100.0))
                        fav_pts = math.ceil(food_points_for_plan(fav_food, store["profile"]["plan"]) * 10) / 10
                        fav_label = f"🍽️ {fav_food['name']} ({fav_amount:.0f} g, {fav_pts:.1f} P)"
                        if st.button(fav_label, key=f"pin_add_food_{idx}"):
                            log["entries"].append(
                                {
                                    "name": fav_food["name"],
                                    "amount": fav_amount,
                                    "meal": fav_meal,
                                    "points": fav_pts,
                                    "time": datetime.now().isoformat(timespec="seconds"),
                                }
                            )
                            log["daily_pts_snapshot"] = daily_points(store["profile"])
                            save_store(store)
                            st.success(f"{fav_food['name']} hinzugefügt")
                            st.rerun()
                    else:
                        fav_combo = item["value"]
                        fav_pts = combo_points_for_plan(fav_combo, store["foods"], store["profile"]["plan"])
                        fav_label = f"⭐ {fav_combo.get('name', 'Kombi')} (1x, {fav_pts:.1f} P)"
                        if st.button(fav_label, key=f"pin_add_combo_{idx}"):
                            log["entries"].append(
                                {
                                    "name": fav_combo.get("name", "Kombi"),
                                    "amount": 1.0,
                                    "meal": fav_meal,
                                    "points": fav_pts,
                                    "time": datetime.now().isoformat(timespec="seconds"),
                                    "is_combo": True,
                                }
                            )
                            log["daily_pts_snapshot"] = daily_points(store["profile"])
                            save_store(store)
                            st.success(f"{fav_combo.get('name', 'Kombi')} hinzugefügt")
                            st.rerun()
            st.caption("Fixierte Favoriten bleiben dauerhaft oben und sind hier mit einem Klick eintragbar.")

        selector_entries = []
        for combo in combos:
            selector_entries.append({"label": f"⭐ Kombi: {combo.get('name', '')}", "kind": "combo", "value": combo})
        for food in ordered_foods:
            selector_entries.append({"label": f"🍽️ {food['name']} ({food.get('category', 'Sonstiges')})", "kind": "food", "value": food})

        if selector_entries:
            labels = [e["label"] for e in selector_entries]
            selected_label = st.selectbox(
                "🔍 Food/Kombi",
                labels,
                key="log_food_select",
                help="Tippen zeigt Vorschläge; heute/gestern/häufig verwendete Einträge stehen oben.",
            )
            selected_entry = next(e for e in selector_entries if e["label"] == selected_label)
            meal = st.selectbox("🍽️", ["Frühstück", "Mittagessen", "Abendessen", "Snack"])

            selected_kind = selected_entry["kind"]
            selected_name_for_fav = selected_entry["value"].get("name", "")
            fav_key = favorite_key(selected_kind, selected_name_for_fav)
            is_fav = fav_key in favorite_keys

            fav_col1, fav_col2 = st.columns([1, 3])
            with fav_col1:
                fav_button_label = "Fixierung lösen" if is_fav else "Fixieren"
                if st.button(fav_button_label, key="toggle_favorite"):
                    if is_fav:
                        store["favorites"] = [k for k in store.get("favorites", []) if k != fav_key]
                        st.success("Fixierung entfernt")
                    else:
                        store.setdefault("favorites", []).append(fav_key)
                        st.success("Fixiert und nach oben gelegt")
                    save_store(store)
                    st.rerun()
            with fav_col2:
                if is_fav:
                    st.caption("Dieser Eintrag ist fixiert und bleibt immer ganz oben.")
                else:
                    st.caption("Nicht fixiert: per Klick dauerhaft ganz oben anheften.")

            if selected_entry["kind"] == "food":
                food = selected_entry["value"]
                selected_name = food["name"]
                amount = st.number_input("⚖️ g", min_value=1.0, value=float(food["portion_g"]), step=1.0)
                factor = amount / float(food["portion_g"])
                pts = math.ceil(food_points_for_plan(food, store["profile"]["plan"]) * factor * 10) / 10
                st.caption(f"Eintrag: {pts:.1f} Punkte")

                if st.button("Eintrag hinzufügen"):
                    log["entries"].append({
                        "name": selected_name,
                        "amount": amount,
                        "meal": meal,
                        "points": pts,
                        "time": datetime.now().isoformat(timespec="seconds"),
                    })
                    log["daily_pts_snapshot"] = daily_points(store["profile"])
                    save_store(store)
                    st.success("Hinzugefügt")
            else:
                combo = selected_entry["value"]
                combo_base_pts = combo_points_for_plan(combo, store["foods"], store["profile"]["plan"])
                combo_factor = st.number_input("Kombi-Faktor", min_value=0.1, value=1.0, step=0.1)
                pts = math.ceil(combo_base_pts * combo_factor * 10) / 10

                item_lines = []
                for item in combo.get("items", []):
                    item_lines.append(f"- {item.get('food_name', '-')}: {float(item.get('amount_g', 0.0)):.0f} g")
                st.caption("Kombi-Inhalt:\n" + "\n".join(item_lines) if item_lines else "Kombi ohne Komponenten")
                st.caption(f"Eintrag: {pts:.1f} Punkte")

                if st.button("Kombi eintragen"):
                    log["entries"].append({
                        "name": combo.get("name", "Kombi"),
                        "amount": combo_factor,
                        "meal": meal,
                        "points": pts,
                        "time": datetime.now().isoformat(timespec="seconds"),
                        "is_combo": True,
                    })
                    log["daily_pts_snapshot"] = daily_points(store["profile"])
                    save_store(store)
                    st.success("Kombi hinzugefügt")
        else:
            st.warning("Keine Lebensmittel vorhanden")

        with st.expander("Kombi speichern (z. B. Kaffee + Kondensmilch + Zucker)"):
            combo_name = st.text_input("Name der Kombi", key="combo_name")
            if ordered_foods:
                combo_food_labels = [f"{f['name']} ({f.get('category', 'Sonstiges')})" for f in ordered_foods]
                selected_parts = st.multiselect(
                    "Komponenten auswählen",
                    combo_food_labels,
                    key="combo_parts",
                    help="Mehrere Lebensmittel auswählen und Mengen festlegen.",
                )

                label_to_food = {f"{f['name']} ({f.get('category', 'Sonstiges')})": f for f in ordered_foods}
                combo_items = []
                for idx, label in enumerate(selected_parts):
                    part_food = label_to_food[label]
                    part_amount = st.number_input(
                        f"Menge für {part_food['name']} (g)",
                        min_value=1.0,
                        value=float(part_food.get("portion_g", 100.0)),
                        step=1.0,
                        key=f"combo_amount_{idx}",
                    )
                    combo_items.append({"food_name": part_food["name"], "amount_g": float(part_amount)})

                temp_combo = {"name": combo_name.strip(), "items": combo_items}
                preview_combo_pts = combo_points_for_plan(temp_combo, store["foods"], store["profile"]["plan"])
                st.caption(f"Kombi-Punkte (1x): {preview_combo_pts:.1f}")

                if st.button("Kombi speichern/aktualisieren"):
                    if not combo_name.strip():
                        st.error("Bitte einen Kombi-Namen eingeben")
                    elif not combo_items:
                        st.error("Bitte mindestens ein Lebensmittel auswählen")
                    else:
                        new_combo = {"name": combo_name.strip(), "items": combo_items}
                        existing_idx = next((i for i, c in enumerate(store["combos"]) if c.get("name", "").lower() == combo_name.strip().lower()), None)
                        if existing_idx is None:
                            store["combos"].append(new_combo)
                        else:
                            store["combos"][existing_idx] = new_combo
                        save_store(store)
                        st.success("Kombi gespeichert")
            else:
                st.caption("Keine Lebensmittel für Kombis verfügbar")

    with right:
        log["water_l"] = st.number_input("Wasser (L)", min_value=0.0, value=float(log.get("water_l", 0.0)), step=0.25)
        if st.button("Wasser speichern"):
            save_store(store)
            st.success("Gespeichert")

    entries = log.get("entries", [])
    if entries:
        total = sum(float(e["points"]) for e in entries)
        w_extra_now = weekly_extra_points(store["profile"])
        w_start_now = current_weigh_week_start(store["profile"])
        used_before_day = weekly_extra_used(store["logs"], w_start_now, store["profile"], d - timedelta(days=1))
        day_status = day_budget_status(log, store["profile"], max(0.0, w_extra_now - used_before_day))
        w_used_now = min(w_extra_now, used_before_day + day_status["weekly_used_today"])
        w_left = max(0.0, w_extra_now - w_used_now)

        if day_status["deficit"] <= 0 and total <= day_status["daily_base"]:
            st.success(f"Tag: {total:.1f} / {day_status['daily_base']:.1f} Punkte")
        elif day_status["deficit"] <= 0:
            st.warning(
                f"Tag: {total:.1f} / {day_status['daily_base']:.1f} Punkte - "
                f"{day_status['weekly_used_today']:.1f} aus Wochenextra"
            )
            if day_status["activity_used_today"] > 0:
                st.info(
                    f"Aktivitätspunkte genutzt: {day_status['activity_used_today']:.1f} / "
                    f"{day_status['activity_available']:.1f}"
                )
        else:
            st.error(
                f"Tag: {total:.1f} / {day_status['daily_base']:.1f} Punkte - "
                f"{day_status['deficit']:.1f} über Tages-/Wochen-/Aktivitätslimit"
            )
        st.info(f"Wochenextra noch verfügbar: {w_left:.1f} / {w_extra_now} Punkte (seit {w_start_now.strftime('%d.%m.')})")

        st.write("Eintrag bearbeiten oder löschen")
        entry_labels = []
        for i, e in enumerate(entries):
            e_time = str(e.get("time", "-"))
            e_meal = str(e.get("meal", "-"))
            e_name = str(e.get("name", "-"))
            e_amount = float(e.get("amount", 0.0))
            e_points = float(e.get("points", 0.0))
            entry_labels.append(f"#{i} | {e_time} | {e_meal} | {e_name} | {e_amount:.1f} | {e_points:.1f} P")

        selected_entry_label = st.selectbox(
            "Eintrag auswählen",
            entry_labels,
            key=f"edit_entry_select_{day}",
        )
        selected_idx = entry_labels.index(selected_entry_label)
        selected_entry = entries[selected_idx]

        with st.form(key=f"edit_entry_form_{day}_{selected_idx}"):
            meal_options = ["Frühstück", "Mittagessen", "Abendessen", "Snack"]
            current_meal = str(selected_entry.get("meal", "Snack"))
            meal_index = meal_options.index(current_meal) if current_meal in meal_options else 3

            edit_meal = st.selectbox("Mahlzeit", meal_options, index=meal_index)
            edit_name = st.text_input("Name", value=str(selected_entry.get("name", "")))
            edit_amount = st.number_input(
                "Menge",
                min_value=0.1,
                value=max(0.1, float(selected_entry.get("amount", 0.1))),
                step=0.1,
            )

            is_combo_entry = bool(selected_entry.get("is_combo", False))
            calc_points = None
            if is_combo_entry:
                combo_match = next(
                    (c for c in store.get("combos", []) if c.get("name", "").strip().lower() == edit_name.strip().lower()),
                    None,
                )
                if combo_match:
                    base_combo = combo_points_for_plan(combo_match, store["foods"], store["profile"]["plan"])
                    calc_points = math.ceil(base_combo * float(edit_amount) * 10) / 10
            else:
                food_match = next(
                    (f for f in store.get("foods", []) if f.get("name", "").strip().lower() == edit_name.strip().lower()),
                    None,
                )
                if food_match:
                    base_food_points = food_points_for_plan(food_match, store["profile"]["plan"])
                    portion_g = max(1.0, float(food_match.get("portion_g", 100.0)))
                    calc_points = math.ceil(base_food_points * (float(edit_amount) / portion_g) * 10) / 10

            if calc_points is not None:
                st.caption(f"Automatisch berechnet: {calc_points:.1f} Punkte")
            use_calc = st.checkbox("Berechnete Punkte verwenden", value=(calc_points is not None))

            edit_points_default = float(selected_entry.get("points", 0.0))
            edit_points = st.number_input("Punkte", min_value=0.0, value=edit_points_default, step=0.1)

            c1, c2 = st.columns(2)
            with c1:
                save_edit = st.form_submit_button("Änderungen speichern")
            with c2:
                delete_entry = st.form_submit_button("Eintrag löschen")

            if save_edit:
                if not edit_name.strip():
                    st.error("Bitte einen Namen eingeben")
                else:
                    final_points = calc_points if (use_calc and calc_points is not None) else float(edit_points)
                    log["entries"][selected_idx] = {
                        **selected_entry,
                        "name": edit_name.strip(),
                        "meal": edit_meal,
                        "amount": float(edit_amount),
                        "points": math.ceil(float(final_points) * 10) / 10,
                    }
                    save_store(store)
                    st.success("Eintrag aktualisiert")
                    st.rerun()

            if delete_entry:
                del log["entries"][selected_idx]
                save_store(store)
                st.success("Eintrag gelöscht")
                st.rerun()

        with st.expander("Einträge anzeigen", expanded=True):
            df = pd.DataFrame(entries)
            st.dataframe(df[["time", "meal", "name", "amount", "points"]], width="stretch", hide_index=True)
    else:
        st.caption("Noch keine Einträge")

if active_page == "aktiv":
    act_date = weekly_strip_nav("aktiv_day", store["profile"], store)
    act_day = act_date.isoformat()
    act_log = todays_log(store["logs"], act_day)
    act_log.setdefault("activities", [])
    act_log.setdefault("bonus", 0)
    act_log.setdefault("steps", 0)

    current_weight = float(live_profile.get("current_weight", 70.0))
    current_bonus = int(act_log.get("bonus", 0))
    current_steps = int(act_log.get("steps", 0))

    # Tab 1: Aktivitäten
    st.subheader("🏃 Sport")
    st.caption("Sport wählen, Minuten eingeben, Punkte kommen automatisch.")
    
    col1, col2 = st.columns(2)
    with col1:
        activity_list = sorted(ACTIVITIES.keys())
        selected_activity = st.selectbox(
            "🏷️ Sport",
            activity_list,
            key="activity_select"
        )
    
    if selected_activity:
        available_intensities = list(ACTIVITIES[selected_activity].keys())
        
        with col2:
            selected_intensity = st.selectbox(
                "⚡ Intens.",
                available_intensities,
                format_func=lambda x: INTENSITY_LABELS.get(x, x),
                key="intensity_select"
            )
        
        duration = st.number_input(
            "⏱️ Min",
            min_value=1,
            value=30,
            step=1,
            key="activity_duration"
        )
        
        calc_points = activity_points(selected_activity, selected_intensity, duration, current_weight)
        
        col_min, col_pts = st.columns(2)
        with col_min:
            st.metric("⏱️ Minuten", duration)
        with col_pts:
            st.metric("⭐ Punkte", f"{calc_points}")
        
        if st.button("➕ Aktivität", key="add_activity"):
            activity_entry = {
                "name": selected_activity,
                "intensity": selected_intensity,
                "duration": duration,
                "points": calc_points,
                "weight_at_entry": current_weight,
            }
            if "activities" not in act_log:
                act_log["activities"] = []
            act_log["activities"].append(activity_entry)
            act_log["bonus"] = int(sum(float(a.get("points", 0)) for a in act_log["activities"]))
            save_store(store)
            st.success(f"{selected_activity} ({selected_intensity}, {duration} min) hinzugefügt - {calc_points} Punkte")
            st.rerun()
    
    st.divider()
    st.subheader("🧾 Heute")
    
    if act_log.get("activities"):
        for i, activity in enumerate(act_log["activities"]):
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                intensity_label = INTENSITY_LABELS.get(activity.get("intensity", ""), activity.get("intensity", ""))
                st.write(f"{activity.get('name')} ({intensity_label}) - {activity.get('duration')} min")
            with col2:
                st.metric("Punkte", activity.get("points", 0))
            with col3:
                if st.button("✕", key=f"del_activity_{i}"):
                    act_log["activities"].pop(i)
                    act_log["bonus"] = int(sum(float(a.get("points", 0)) for a in act_log["activities"]))
                    save_store(store)
                    st.rerun()
    else:
        st.info("Noch keine Aktivitäten heute eingetragen.")
    
    st.metric("🏃 Gesamt-Sportpunkte heute", current_bonus)
    
    st.divider()
    st.subheader("👟 Schritte")
    st.caption("Schritte eingeben, Punkte werden automatisch berechnet.")
    
    steps_input = st.number_input(
        "👟 Heute",
        min_value=0,
        value=current_steps,
        step=100,
        key="steps_input"
    )
    
    if steps_input > 0:
        steps_points = steps_to_points(steps_input)
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("👟 Schritte", steps_input)
        with col2:
            st.metric("⭐ Punkte", f"{steps_points}")
    
    if st.button("Schritte speichern", key="save_steps"):
        act_log["steps"] = int(steps_input)
        save_store(store)
        st.success("Schritte gespeichert")
        st.rerun()

if active_page == "stats":
    st.subheader("Statistik")
    if st.button("← Zurück zur App", key="back_from_stats"):
        st.session_state["main_nav"] = "mahlz"
        st.session_state["bottom_nav"] = "🍽️ Mahlz."
        st.session_state["last_bottom_nav"] = "🍽️ Mahlz."
        st.session_state["header_override"] = False
        st.rerun()

    p = store["profile"]
    dp = daily_points(p)

    w_extra_s = weekly_extra_points(p)
    w_start_s = current_weigh_week_start(p)
    w_used_s = weekly_extra_used(store["logs"], w_start_s, p, date.today())
    w_left_s = max(0.0, w_extra_s - w_used_s)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Tagespunkte", dp)
    with c2:
        st.metric("Wochenextra gesamt", w_extra_s)
        st.caption("Regel: 100 kg = 35, je 10 kg weniger = -5, Minimum 15")
    with c3:
        st.metric("Wochenextra verbleibend", f"{w_left_s:.1f}")
        st.caption(f"Erneuert jeden {p.get('weigh_day', 'Montag')} (Wiegetag)")
    with c4:
        st.metric("Sterne", stars_earned(float(p["start_weight"]), float(p["current_weight"])))

    progress_total = max(0.0, float(p["start_weight"]) - float(p["goal_weight"]))
    progress_done = max(0.0, float(p["start_weight"]) - float(p["current_weight"]))
    pct = 100.0 if progress_total == 0 else max(0.0, min(100.0, progress_done / progress_total * 100.0))
    st.progress(pct / 100.0)
    st.caption(f"Ziel-Fortschritt: {pct:.1f}%")

    st.caption(f"Wochenschnitt Punkte (alle Logs): {week_avg_points(store['logs']):.2f}")

    # Täglicher Punkteverbrauch
    st.write("Täglicher Punkteverbrauch")
    if store["logs"]:
        daily_data = []
        for log in store["logs"]:
            log_date = log.get("date", "")
            total_points = sum(float(e.get("points", 0)) for e in log.get("entries", []))
            daily_bonus = int(log.get("bonus", 0))
            daily_data.append({
                "date": log_date,
                "Punkte": f"{total_points:.1f}",
                "Sportpunkte": daily_bonus,
                "Schritte": int(log.get("steps", 0)),
            })
        
        daily_df = pd.DataFrame(daily_data).copy()
        daily_df = daily_df.sort_values("date", ascending=False)
        daily_df["date"] = pd.to_datetime(daily_df["date"], errors="coerce").dt.strftime("%d.%m.%Y")
        daily_df = daily_df.rename(columns={"date": "Datum"})
        st.dataframe(daily_df[["Datum", "Punkte", "Sportpunkte", "Schritte"]], width="stretch", hide_index=True)
    else:
        st.caption("Noch keine Einträge vorhanden.")

    # Sportarten Übersicht
    st.write("Sportarten & Aktivitäten")
    activity_data = []
    for log in store["logs"]:
        log_date = log.get("date", "")
        for activity in log.get("activities", []):
            activity_data.append({
                "date": log_date,
                "Datum": pd.to_datetime(log_date, errors="coerce").strftime("%d.%m.%Y"),
                "Sportart": activity.get("name", ""),
                "Intensität": activity.get("intensity", ""),
                "Dauer (min)": activity.get("duration", 0),
                "Punkte": int(activity.get("points", 0)),
            })
    
    if activity_data:
        activity_df = pd.DataFrame(activity_data).copy()
        activity_df = activity_df.sort_values("date", ascending=False)
        st.dataframe(activity_df[["Datum", "Sportart", "Intensität", "Dauer (min)", "Punkte"]], width="stretch", hide_index=True)
    else:
        st.caption("Noch keine Sportarten eingetragen.")

    # Schritte Übersicht
    st.write("Schritte Verlauf")
    steps_data = []
    for log in store["logs"]:
        log_date = log.get("date", "")
        steps = int(log.get("steps", 0))
        if steps > 0:
            steps_points = steps_to_points(steps)
            steps_data.append({
                "date": log_date,
                "Datum": pd.to_datetime(log_date, errors="coerce").strftime("%d.%m.%Y"),
                "Schritte": steps,
                "Punkte": steps_points,
            })
    
    if steps_data:
        steps_df = pd.DataFrame(steps_data).copy()
        steps_df = steps_df.sort_values("date", ascending=False)
        st.dataframe(steps_df[["Datum", "Schritte", "Punkte"]], width="stretch", hide_index=True)
    else:
        st.caption("Noch keine Schritte eingetragen.")

    st.write("Gewichtsverlauf (Tabelle)")
    if store["weights"]:
        wtable = pd.DataFrame(store["weights"]).copy()
        wtable = wtable.sort_values("date", ascending=False)
        wtable["date"] = pd.to_datetime(wtable["date"], errors="coerce").dt.strftime("%d.%m.%Y")
        wtable["weight"] = wtable["weight"].map(lambda x: f"{float(x):.1f}")
        wtable["note"] = wtable.get("note", "").fillna("")
        wtable = wtable.rename(columns={"date": "Datum", "weight": "Gewicht (kg)", "note": "Notiz"})
        st.dataframe(wtable[["Datum", "Gewicht (kg)", "Notiz"]], width="stretch", hide_index=True)
    else:
        st.caption("Noch keine Gewichtseinträge vorhanden.")

    st.write("Körpermaße Verlauf")
    store.setdefault("measurements", [])
    if store["measurements"]:
        mstat = pd.DataFrame(store["measurements"]).copy()
        mstat = mstat.sort_values("date", ascending=False)
        mstat["date"] = pd.to_datetime(mstat["date"], errors="coerce").dt.strftime("%d.%m.%Y")
        _masz_cols = ["oberarm_links", "oberarm_rechts", "brust", "taille", "huefte", "oberschenkel_links", "oberschenkel_rechts"]
        for col in _masz_cols:
            if col in mstat.columns:
                mstat[col] = mstat[col].apply(lambda x: f"{float(x):.1f}" if float(x) > 0 else "-")
        mstat = mstat.rename(columns={
            "date": "Datum", "oberarm_links": "Oberarm L", "oberarm_rechts": "Oberarm R",
            "brust": "Brust (cm)", "taille": "Taille (cm)",
            "huefte": "Hüfte (cm)", "oberschenkel_links": "Ober. L", "oberschenkel_rechts": "Ober. R", "note": "Notiz"
        })
        _stat_show = [c for c in ["Datum", "Oberarm L", "Oberarm R", "Brust (cm)", "Taille (cm)", "Hüfte (cm)", "Ober. L", "Ober. R", "Notiz"] if c in mstat.columns]
        st.dataframe(mstat[_stat_show], width="stretch", hide_index=True)
    else:
        st.caption("Noch keine Körpermaße eingetragen.")

if active_page == "masze":
    st.subheader("📏 Körpermaße")
    store.setdefault("measurements", [])
    m_date = weekly_strip_nav("masze_day", store["profile"], store)

    with st.form("add_measurement"):
        st.write("Neue Messung eintragen")

        _img_path = Path(__file__).parent / "body_silhouette.jpg"
        row_arm_l, row_arm_r = st.columns(2)
        with row_arm_l:
            m_oberarm_l = st.number_input("💪 Oberarm links (cm)", min_value=0.0, max_value=150.0, value=0.0, step=0.5, key="masz_oberarm_l")
        with row_arm_r:
            m_oberarm_r = st.number_input("💪 Oberarm rechts (cm)", min_value=0.0, max_value=150.0, value=0.0, step=0.5, key="masz_oberarm_r")

        row_brust, row_img, row_taille = st.columns([3, 0.8, 3])
        with row_brust:
            m_brust = st.number_input("👆 Brust (cm)", min_value=0.0, max_value=300.0, value=0.0, step=0.5, key="masz_brust")
        with row_img:
            if _img_path.exists():
                _img_data = base64.b64encode(_img_path.read_bytes()).decode("ascii")
                st.markdown(
                    f'<div class="measure-figure-desktop"><img src="data:image/jpeg;base64,{_img_data}" alt="Körpersilhouette" /></div>',
                    unsafe_allow_html=True,
                )
            else:
                st.info("Bild nicht gefunden")
        with row_taille:
            m_taille = st.number_input("✂️ Taille (cm)", min_value=0.0, max_value=300.0, value=0.0, step=0.5, key="masz_taille")

        m_huefte = st.number_input("📐 Hüfte (cm)", min_value=0.0, max_value=300.0, value=0.0, step=0.5, key="masz_huefte")

        row_thigh_l, row_thigh_r = st.columns(2)
        with row_thigh_l:
            m_ober_l = st.number_input("🦵 Oberschenkel links (cm)", min_value=0.0, max_value=150.0, value=0.0, step=0.5, key="masz_ober_l")
        with row_thigh_r:
            m_ober_r = st.number_input("🦵 Oberschenkel rechts (cm)", min_value=0.0, max_value=150.0, value=0.0, step=0.5, key="masz_ober_r")

        m_note = st.text_input("Notiz (optional)", key="masz_note")
        if st.form_submit_button("Messung speichern"):
            store["measurements"].append({
                "date": m_date.isoformat(),
                "oberarm_links": m_oberarm_l,
                "oberarm_rechts": m_oberarm_r,
                "brust": m_brust,
                "taille": m_taille,
                "huefte": m_huefte,
                "oberschenkel_links": m_ober_l,
                "oberschenkel_rechts": m_ober_r,
                "note": m_note.strip(),
            })
            save_store(store)
            st.success("Messung gespeichert")
            st.rerun()

    st.divider()
    st.write("Verlauf")
    if store["measurements"]:
        mdf = pd.DataFrame(store["measurements"]).copy()
        mdf = mdf.sort_values("date", ascending=False)
        mdf["date"] = pd.to_datetime(mdf["date"], errors="coerce").dt.strftime("%d.%m.%Y")
        _all_masz_cols = ["oberarm_links", "oberarm_rechts", "brust", "taille", "huefte", "oberschenkel_links", "oberschenkel_rechts"]
        for col in _all_masz_cols:
            if col in mdf.columns:
                mdf[col] = mdf[col].apply(lambda x: f"{float(x):.1f}" if float(x) > 0 else "-")
        mdf = mdf.rename(columns={
            "date": "Datum", "oberarm_links": "Oberarm L", "oberarm_rechts": "Oberarm R",
            "brust": "Brust (cm)", "taille": "Taille (cm)",
            "huefte": "Hüfte (cm)", "oberschenkel_links": "Ober. L", "oberschenkel_rechts": "Ober. R", "note": "Notiz"
        })
        _mdf_show = [c for c in ["Datum", "Oberarm L", "Oberarm R", "Brust (cm)", "Taille (cm)", "Hüfte (cm)", "Ober. L", "Ober. R", "Notiz"] if c in mdf.columns]
        st.dataframe(mdf[_mdf_show], width="stretch", hide_index=True)

        sorted_measurements = sorted(store["measurements"], key=lambda x: x.get("date", ""), reverse=True)
        edit_labels = [
            f"{m.get('date', '')} | B:{float(m.get('brust', 0.0)):.1f} T:{float(m.get('taille', 0.0)):.1f} H:{float(m.get('huefte', 0.0)):.1f}"
            for m in sorted_measurements
        ]

        with st.expander("Eintrag bearbeiten"):
            edit_sel = st.selectbox("Eintrag auswählen", edit_labels, key="masz_edit_sel")
            edit_idx = edit_labels.index(edit_sel)
            edit_orig_idx = store["measurements"].index(sorted_measurements[edit_idx])
            edit_item = store["measurements"][edit_orig_idx]
            edit_item_date = pd.to_datetime(str(edit_item.get("date", "")), errors="coerce")
            edit_item_date_value = edit_item_date.date() if not pd.isna(edit_item_date) else date.today()

            with st.form("masz_edit_form"):
                me_date = st.date_input(
                    "Datum bearbeiten",
                    value=edit_item_date_value,
                    format="DD.MM.YYYY",
                )
                me_arm_l, me_arm_r = st.columns(2)
                with me_arm_l:
                    me_oberarm_l = st.number_input("Oberarm links (cm)", min_value=0.0, max_value=150.0, value=float(edit_item.get("oberarm_links", 0.0)), step=0.5)
                with me_arm_r:
                    me_oberarm_r = st.number_input("Oberarm rechts (cm)", min_value=0.0, max_value=150.0, value=float(edit_item.get("oberarm_rechts", 0.0)), step=0.5)
                me_brust, me_taille = st.columns(2)
                with me_brust:
                    me_brust_val = st.number_input("Brust (cm)", min_value=0.0, max_value=300.0, value=float(edit_item.get("brust", 0.0)), step=0.5)
                with me_taille:
                    me_taille_val = st.number_input("Taille (cm)", min_value=0.0, max_value=300.0, value=float(edit_item.get("taille", 0.0)), step=0.5)
                me_huefte = st.number_input("Hüfte (cm)", min_value=0.0, max_value=300.0, value=float(edit_item.get("huefte", 0.0)), step=0.5)
                me_thigh_l, me_thigh_r = st.columns(2)
                with me_thigh_l:
                    me_ober_l = st.number_input("Oberschenkel links (cm)", min_value=0.0, max_value=150.0, value=float(edit_item.get("oberschenkel_links", 0.0)), step=0.5)
                with me_thigh_r:
                    me_ober_r = st.number_input("Oberschenkel rechts (cm)", min_value=0.0, max_value=150.0, value=float(edit_item.get("oberschenkel_rechts", 0.0)), step=0.5)
                me_note = st.text_input("Notiz", value=str(edit_item.get("note", "")))

                save_masz_edit = st.form_submit_button("Messung aktualisieren")
                if save_masz_edit:
                    store["measurements"][edit_orig_idx] = {
                        "date": me_date.isoformat(),
                        "oberarm_links": float(me_oberarm_l),
                        "oberarm_rechts": float(me_oberarm_r),
                        "brust": float(me_brust_val),
                        "taille": float(me_taille_val),
                        "huefte": float(me_huefte),
                        "oberschenkel_links": float(me_ober_l),
                        "oberschenkel_rechts": float(me_ober_r),
                        "note": me_note.strip(),
                    }
                    save_store(store)
                    st.success("Messung aktualisiert")
                    st.rerun()

        with st.expander("Eintrag löschen"):
            del_labels = [f"{m.get('date', '')} | B:{m.get('brust', 0):.0f} T:{m.get('taille', 0):.0f} H:{m.get('huefte', 0):.0f}" for m in sorted_measurements]
            del_sel = st.selectbox("Eintrag auswählen", del_labels, key="masz_del_sel")
            if st.button("Ausgewählten Eintrag löschen", key="masz_del_btn"):
                del_idx = del_labels.index(del_sel)
                orig_idx = store["measurements"].index(sorted_measurements[del_idx])
                store["measurements"].pop(orig_idx)
                save_store(store)
                st.success("Eintrag gelöscht")
                st.rerun()
    else:
        st.caption("Noch keine Messungen vorhanden.")

if active_page == "gewicht":
    p = store["profile"]
    w_date = weekly_strip_nav("weight_day", store["profile"], store)
    
    st.markdown('<div class="weight-input-row">', unsafe_allow_html=True)
    w_col1, w_col2 = st.columns(2, gap="small")
    with w_col1:
        st.caption(f"Ausgewählt: {w_date.strftime('%d.%m.%Y')}")
    with w_col2:
        w_val = st.number_input("⚖️ kg", min_value=30.0, max_value=300.0, value=float(p["current_weight"]), step=0.1, key="weight_value")
    st.markdown('</div>', unsafe_allow_html=True)

    w_note = st.text_input("Notiz", key="weight_note")

    if st.button("Gewicht speichern"):
        store["weights"].append({
            "date": w_date.isoformat(),
            "weight": w_val,
            "note": w_note,
        })
        store["profile"]["current_weight"] = w_val
        save_store(store)
        st.success("Gewicht gespeichert")

    if store["weights"]:
        wdf = pd.DataFrame(store["weights"])
        wdf = wdf.sort_values("date")
        wdf["weight"] = wdf["weight"].astype(float)

        min_weight = float(wdf["weight"].min())
        max_weight = float(wdf["weight"].max())
        spread_kg = max_weight - min_weight

        # Adaptive chart: for small early changes, show gram deltas so progress is visible.
        if len(wdf) >= 2 and spread_kg < 2.0:
            baseline = float(wdf["weight"].iloc[0])
            wdf["delta_g"] = ((wdf["weight"] - baseline) * 1000.0).round().astype(int)
            st.caption("Feinmodus aktiv: Verlauf in Gramm relativ zum ersten Eintrag")
            st.line_chart(wdf.set_index("date")["delta_g"])
        else:
            st.caption("Standardmodus: Verlauf in Kilogramm")
            st.line_chart(wdf.set_index("date")["weight"])

        wtable = pd.DataFrame(store["weights"]).copy()
        wtable = wtable.sort_values("date", ascending=False)
        wtable["date"] = pd.to_datetime(wtable["date"], errors="coerce").dt.strftime("%d.%m.%Y")
        wtable["weight"] = wtable["weight"].map(lambda x: f"{float(x):.1f}")
        wtable["note"] = wtable.get("note", "").fillna("")
        wtable = wtable.rename(columns={"date": "Datum", "weight": "Gewicht (kg)", "note": "Notiz"})
        st.dataframe(wtable[["Datum", "Gewicht (kg)", "Notiz"]], width="stretch", hide_index=True)

        delete_candidates = []
        for idx, entry in enumerate(store["weights"]):
            raw_date = str(entry.get("date", ""))
            parsed_date = pd.to_datetime(raw_date, errors="coerce")
            display_date = parsed_date.strftime("%d.%m.%Y") if not pd.isna(parsed_date) else raw_date
            display_weight = float(entry.get("weight", 0.0) or 0.0)
            note = str(entry.get("note", "") or "").strip()
            short_note = f" | {note[:28]}" if note else ""

            delete_candidates.append(
                {
                    "idx": idx,
                    "sort_date": raw_date,
                    "label": f"{display_date} - {display_weight:.1f} kg{short_note}",
                }
            )

        delete_candidates.sort(key=lambda x: x["sort_date"], reverse=True)
        delete_ids = [item["idx"] for item in delete_candidates]
        delete_label_by_idx = {item["idx"]: item["label"] for item in delete_candidates}

        st.write("Eintrag bearbeiten")
        selected_edit_idx = st.selectbox(
            "Zu bearbeitender Gewichtseintrag",
            delete_ids,
            format_func=lambda idx: delete_label_by_idx.get(idx, str(idx)),
            key="weight_edit_pick",
        )
        current_weight_entry = store["weights"][selected_edit_idx]
        current_weight_date = pd.to_datetime(current_weight_entry.get("date", ""), errors="coerce")
        edit_weight_date = (
            current_weight_date.date()
            if not pd.isna(current_weight_date)
            else date.today()
        )

        with st.form("weight_edit_form"):
            ew_c1, ew_c2 = st.columns(2)
            with ew_c1:
                edit_date_val = st.date_input("Datum bearbeiten", value=edit_weight_date, format="DD.MM.YYYY")
            with ew_c2:
                edit_weight_val = st.number_input(
                    "Gewicht bearbeiten (kg)",
                    min_value=30.0,
                    max_value=300.0,
                    value=float(current_weight_entry.get("weight", 80.0)),
                    step=0.1,
                )
            edit_note_val = st.text_input("Notiz bearbeiten", value=str(current_weight_entry.get("note", "")))
            save_weight_edit = st.form_submit_button("Gewichts-Eintrag speichern")

            if save_weight_edit:
                store["weights"][selected_edit_idx] = {
                    "date": edit_date_val.isoformat(),
                    "weight": float(edit_weight_val),
                    "note": edit_note_val.strip(),
                }
                latest_entry = max(store["weights"], key=lambda x: str(x.get("date", "")))
                try:
                    store["profile"]["current_weight"] = float(latest_entry.get("weight", store["profile"]["current_weight"]))
                except (TypeError, ValueError):
                    pass
                save_store(store)
                st.success("Gewichts-Eintrag aktualisiert")
                st.rerun()

        st.write("Eintrag löschen")
        selected_delete_idx = st.selectbox(
            "Zu löschender Gewichtseintrag",
            delete_ids,
            format_func=lambda idx: delete_label_by_idx.get(idx, str(idx)),
            key="weight_delete_pick",
        )

        if st.button("Ausgewählten Eintrag löschen", key="delete_weight_entry"):
            removed = store["weights"].pop(selected_delete_idx)

            if store["weights"]:
                latest_entry = max(store["weights"], key=lambda x: str(x.get("date", "")))
                try:
                    store["profile"]["current_weight"] = float(latest_entry.get("weight", store["profile"]["current_weight"]))
                except (TypeError, ValueError):
                    pass

            save_store(store)
            st.success(f"Eintrag gelöscht: {removed.get('date', '')}")
            st.rerun()

