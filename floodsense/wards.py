"""Ward table and flood impact score for Budalangi, Busia County.

The impact score measures how hard each ward was hit by a flood that the satellite
observed. It is a priority for response, not a forecast of future flooding.

data/wards.csv comes from geo/flood_numbers.py (satellite data for the April-May
2026 floods); data/source.txt says exactly which data and dates.

impact = 0.5 * flooded share + 0.3 * people exposed + 0.2 * extra rain,
each scaled 0-1, plus 0.1 if a school or clinic is in the flood zone.
"""

from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data" / "wards.csv"
SOURCE_FILE = DATA.with_name("source.txt")
SOURCE = SOURCE_FILE.read_text(encoding="utf-8").strip() if SOURCE_FILE.exists() else "Replay scenario (not measured data)"


def load_wards() -> pd.DataFrame:
    df = pd.read_csv(DATA)
    flooded_share = (df["flooded_km2"] / df["area_km2"]).clip(0, 1)
    people = df["people_exposed"] / df["people_exposed"].max()
    extra_rain = (df["rain_vs_normal"] - 1).clip(lower=0)
    extra_rain = extra_rain / extra_rain.max() if extra_rain.max() > 0 else extra_rain
    bonus = ((df["schools_flooded"] + df["clinics_flooded"]) > 0) * 0.1

    df["flooded_pct"] = (flooded_share * 100).round().astype(int)
    df["impact_score"] = (0.5 * flooded_share + 0.3 * people + 0.2 * extra_rain + bonus).clip(0, 1).round(2)
    return df.sort_values("impact_score", ascending=False).reset_index(drop=True)


def find_ward(name: str) -> dict | None:
    """Match "Bunyala South" or just "south"; None if no single ward matches."""
    df = load_wards()
    key = name.strip().lower()
    hits = df[df["ward"].str.lower() == key]
    if hits.empty:
        hits = df[df["ward"].str.lower().str.contains(key, regex=False)]
    if len(hits) != 1:
        return None
    row = hits.iloc[0].to_dict()
    return {k: (v.item() if hasattr(v, "item") else v) for k, v in row.items()}
