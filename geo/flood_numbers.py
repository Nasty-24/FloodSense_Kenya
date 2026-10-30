"""Computes real flood figures for Budalangi's wards from satellite data, and writes data/wards.csv.

For each ward (data/budalangi_wards.geojson):
  flooded_km2      Sentinel-1 radar: land that was dry before the floods and under water at their peak
  people_exposed   WorldPop 2020 population living on that flooded land
  schools_flooded  OpenStreetMap schools within 50 m of flooded land
  clinics_flooded  OpenStreetMap hospitals and clinics within 50 m of flooded land
  rain_vs_normal   CHIRPS rainfall over the upstream Nzoia catchment (where Budalangi's floods come from),
                   March-May 2026, divided by the 1991-2020 average for March-May. Same value for every ward.

    .venv\\Scripts\\python geo\\flood_numbers.py

Needs Earth Engine access (`earthengine authenticate`). EE_PROJECT in .env picks a
Cloud project other than the one chosen at sign-in.
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import ee
import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
WARDS = ROOT / "data" / "budalangi_wards.geojson"
OUT_CSV = ROOT / "data" / "wards.csv"
OUT_SOURCE = ROOT / "data" / "source.txt"
OUT_MAP = ROOT / "data" / "flood_map.png"
OSM_CACHE = ROOT / "data" / "osm_facilities.json"  # last good OpenStreetMap answer

YEAR = 2026                            # the 2026 long rains
BEFORE = ("2023-01-01", "2023-03-01")  # a truly dry baseline (drought year); early 2024-2026 were already wet
AFTER = ("2026-04-01", "2026-06-01")   # the floods at their peak
RAIN_MONTHS = (3, 6)                   # 1 March to 31 May
WATER_DB = -18                         # radar backscatter below this = open water
DROP_DB = -3                           # and it fell by at least this much since before

OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
SCHOOL_TAGS = {"school", "kindergarten", "college"}
CLINIC_TAGS = {"hospital", "clinic", "doctors"}


def flood_mask(area):
    s1 = (ee.ImageCollection("COPERNICUS/S1_GRD")
          .filterBounds(area)
          .filter(ee.Filter.eq("instrumentMode", "IW"))
          .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
          .select("VV"))
    before_col, after_col = s1.filterDate(*BEFORE), s1.filterDate(*AFTER)
    n_before, n_after = before_col.size().getInfo(), after_col.size().getInfo()
    print(f"Sentinel-1 images: {n_before} before, {n_after} during the floods")
    if not n_before or not n_after:
        sys.exit("Not enough Sentinel-1 images for these dates.")

    before = before_col.median().focal_median(30, "circle", "meters")
    after = after_col.min().focal_median(30, "circle", "meters")  # the wettest look at each spot
    flooded = after.lt(WATER_DB).And(after.subtract(before).lt(DROP_DB))

    # Not flooding: permanent water (Lake Victoria, the Nzoia channel) and slopes too steep to hold water
    permanent = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence").gte(80).unmask(0)
    slope = ee.Terrain.slope(ee.Image("USGS/SRTMGL1_003"))
    return flooded.And(permanent.Not()).And(slope.lt(5)).selfMask().rename("flooded"), after


def rain_vs_normal():
    chirps = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").select("precipitation")
    m0, m1 = RAIN_MONTHS

    def season(year):
        year = ee.Number(year)
        return chirps.filterDate(ee.Date.fromYMD(year, m0, 1), ee.Date.fromYMD(year, m1, 1)).sum()

    normal = ee.ImageCollection(ee.List.sequence(1991, 2020).map(season)).mean()
    return season(YEAR).divide(normal).rename("ratio")


def osm_facilities(bounds):
    """Schools, hospitals and clinics from OpenStreetMap (Overpass API) inside the bounding box."""
    w, s, e, n = bounds
    query = f"""[out:json][timeout:60];
    (nwr["amenity"~"^(school|kindergarten|college|hospital|clinic|doctors)$"]({s},{w},{n},{e}););
    out center;"""
    data = urllib.parse.urlencode({"data": query}).encode()
    elements = None
    for server in OVERPASS_SERVERS:  # public servers are often busy; try the next one
        try:
            req = urllib.request.Request(server, data=data, headers={"User-Agent": "FloodSense-Kenya-hackathon"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                elements = json.load(resp)["elements"]
            break
        except Exception as exc:
            print(f"OpenStreetMap server {server} failed ({exc}), trying the next one")
    if elements is None and OSM_CACHE.exists():
        print(f"All OpenStreetMap servers failed; using the saved copy in {OSM_CACHE.name}")
        elements = json.loads(OSM_CACHE.read_text(encoding="utf-8"))
    elif elements is None:
        sys.exit("All OpenStreetMap servers failed. Try again in a minute.")
    else:
        OSM_CACHE.write_text(json.dumps(elements), encoding="utf-8")
    points = []
    for el in elements:
        lat = el.get("lat", el.get("center", {}).get("lat"))
        lon = el.get("lon", el.get("center", {}).get("lon"))
        kind = "school" if el["tags"].get("amenity") in SCHOOL_TAGS else "clinic"
        if lat is not None:
            points.append(ee.Feature(ee.Geometry.Point([lon, lat]), {"kind": kind}))
    print(f"OpenStreetMap: {len(points)} schools/clinics in the area")
    return ee.FeatureCollection(points)


def main():
    load_dotenv(ROOT / ".env")
    # Without EE_PROJECT, Earth Engine uses the project chosen at `earthengine authenticate`
    ee.Initialize(project=os.getenv("EE_PROJECT") or None)

    wards = ee.FeatureCollection(json.loads(WARDS.read_text()))
    area = wards.geometry().bounds()
    flooded, after = flood_mask(area)
    ratio = rain_vs_normal()
    # The HydroSHEDS level-6 basin containing Budalangi = the lower Nzoia catchment that feeds its floods
    catchment = ee.Feature(ee.FeatureCollection("WWF/HydroSHEDS/v1/Basins/hybas_6")
                           .filterBounds(ee.Geometry.Point([34.05, 0.10])).first()).geometry()
    catchment_rain = ratio.reduceRegion(ee.Reducer.mean(), catchment, 5566).get("ratio")
    pixel_km2 = ee.Image.pixelArea().divide(1e6)
    pop = (ee.ImageCollection("WorldPop/GP/100m/pop")
           .filter(ee.Filter.eq("country", "KEN")).filter(ee.Filter.eq("year", 2020)).mosaic())

    # Facilities: is there flooded land within 50 m?
    facilities = osm_facilities(area.coordinates().getInfo()[0][0] + area.coordinates().getInfo()[0][2])
    near_flood = flooded.unmask(0).focal_max(50, "circle", "meters").rename("wet")
    facilities = near_flood.reduceRegions(facilities, ee.Reducer.max(), 10)

    def per_ward(w):
        g = w.geometry()
        wet = facilities.filterBounds(g).filter(ee.Filter.eq("max", 1))
        centroid = g.centroid(10).coordinates()
        return w.set({
            "area_km2": g.area(10).divide(1e6),
            "flooded_km2": pixel_km2.updateMask(flooded).reduceRegion(ee.Reducer.sum(), g, 10, maxPixels=1e10).get("area"),
            "people_exposed": pop.updateMask(flooded).reduceRegion(ee.Reducer.sum(), g, 100, maxPixels=1e10).get("population"),
            "schools_flooded": wet.filter(ee.Filter.eq("kind", "school")).size(),
            "clinics_flooded": wet.filter(ee.Filter.eq("kind", "clinic")).size(),
            "rain_vs_normal": catchment_rain,
            "lon": centroid.get(0),
            "lat": centroid.get(1),
        })

    rows = [f["properties"] for f in wards.map(per_ward).getInfo()["features"]]
    df = pd.DataFrame(rows).fillna(0)
    df = df.round({"area_km2": 1, "flooded_km2": 1, "rain_vs_normal": 2, "lat": 4, "lon": 4})
    df["people_exposed"] = (df["people_exposed"] / 10).round().astype(int) * 10  # nearest 10: WorldPop is an estimate
    df = df[["ward", "lat", "lon", "area_km2", "flooded_km2", "people_exposed",
             "schools_flooded", "clinics_flooded", "rain_vs_normal"]]
    print(df.to_string(index=False))
    try:
        df.to_csv(OUT_CSV, index=False)
    except PermissionError:
        sys.exit(f"Can't write {OUT_CSV}: close it in Excel or any other program, then run this again.")
    OUT_SOURCE.write_text(
        f"Sentinel-1 radar ({AFTER[0]} to {AFTER[1]} vs {BEFORE[0]} to {BEFORE[1]}), "
        "WorldPop 2020, OpenStreetMap, CHIRPS rainfall over the Nzoia catchment", encoding="utf-8")

    # A picture for the officer page: flooded land in blue over the radar image
    radar = after.visualize(min=-25, max=0, palette=["000000", "ffffff"])  # RGB, to stack with the layers below
    water = flooded.visualize(palette=["1e90ff"])
    outlines = ee.Image().paint(wards, 0, 2).visualize(palette=["ffffff"])
    url = ee.ImageCollection([radar, water, outlines]).mosaic().getThumbURL(
        {"region": area, "dimensions": 900, "format": "png"})
    urllib.request.urlretrieve(url, OUT_MAP)
    print(f"Wrote {OUT_CSV}, {OUT_SOURCE} and {OUT_MAP}")


if __name__ == "__main__":
    main()
