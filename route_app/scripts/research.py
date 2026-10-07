#!/usr/bin/env python3
"""research.py — сбор фактов по маршруту из открытых источников (без ключей).

Источники (бесплатные, верифицируемые, с URL в выдаче):
- Википедия (ru, затем en): поиск по имени каждой точки + геопоиск статей
  в радиусе 10 км от точек (geosearch) — история, география, флора/фауна;
- OpenStreetMap/Overpass: родники, водные источники, хижины, сёла, магазины
  в bbox маршрута — инфраструктура и аварийные сходы.

Результат: факты.json (структура) + Факты.md (дайджест для LLM-шага гида;
llm.py подмешивает его в контекст автоматически).

Использование:
  python3 research.py points.json --out facts_dir/ [--gpx track.gpx]
  python3 research.py points.json --region "Фанские горы" --no-overpass
"""
import argparse, json, sys, time, urllib.parse, urllib.request
from pathlib import Path

UA = {"User-Agent": "KIMIK3-route-guide/1.0 (https://github.com/shulgaop/KIMIK3)"}
WIKI_LANGS = ["ru", "en"]


def get_json(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def wiki_search(query, lang, limit=3):
    """Поиск статей Википедии: [(title, pageid)]."""
    url = (f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search"
           f"&format=json&srlimit={limit}&srsearch={urllib.parse.quote(query)}")
    try:
        return [(x["title"], x["pageid"]) for x in get_json(url)["query"]["search"]]
    except Exception as e:
        print(f"⚠️  wiki/{lang} поиск «{query}»: {e}", file=sys.stderr)
        return []


def wiki_extract(title, lang, limit=1200):
    """Вступление статьи (plain text) + URL."""
    url = (f"https://{lang}.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext"
           f"&exintro&format=json&redirects=1&titles={urllib.parse.quote(title)}")
    try:
        pages = get_json(url)["query"]["pages"]
        for p in pages.values():
            if "extract" in p:
                return {"title": p["title"], "lang": lang,
                        "text": p["extract"][:limit],
                        "url": f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(p['title'])}"}
    except Exception as e:
        print(f"⚠️  wiki/{lang} «{title}»: {e}", file=sys.stderr)
    return None


def wiki_geosearch(lat, lon, lang, radius=10000, limit=8):
    """Статьи Википедии в радиусе от координат (озёра, пики, сёла рядом)."""
    url = (f"https://{lang}.wikipedia.org/w/api.php?action=query&list=geosearch&format=json"
           f"&gscoord={lat}|{lon}&gsradius={radius}&gslimit={limit}")
    try:
        return [(x["title"], x["dist"]) for x in get_json(url)["query"]["geosearch"]]
    except Exception as e:
        print(f"⚠️  geosearch/{lang}: {e}", file=sys.stderr)
        return []


def overpass_pois(south, north, west, east):
    """Инфраструктура из OSM: родники/вода, хижины, сёла, магазины в bbox."""
OVERPASS_MIRRORS = ["https://overpass-api.de/api/interpreter",
                    "https://overpass.kumi.systems/api/interpreter",
                    "https://overpass.nchc.org.tw/api/interpreter"]


def overpass_pois(south, north, west, east):
    """Инфраструктура из OSM: родники/вода, хижины, сёла, магазины в bbox."""
    query = f"""[out:json][timeout:50];
(
  node["natural"="spring"]({south},{west},{north},{east});
  node["tourism"="alpine_hut"]({south},{west},{north},{east});
  node["tourism"="wilderness_hut"]({south},{west},{north},{east});
  node["amenity"="drinking_water"]({south},{west},{north},{east});
  node["place"~"village|hamlet"]({south},{west},{north},{east});
  node["shop"]({south},{west},{north},{east});
);
out body 80;"""
    data = None
    for mirror in OVERPASS_MIRRORS:
        try:
            data = get_json(mirror + "?data=" + urllib.parse.quote(query), timeout=70)
            break
        except Exception as e:
            print(f"⚠️  Overpass {mirror.split('/')[2]}: {e} — пробую зеркало", file=sys.stderr)
    if data is None:
        print("⚠️  Все зеркала Overpass недоступны — блок инфраструктуры пропущен",
              file=sys.stderr)
        return []
    kind_map = {"spring": "родник", "alpine_hut": "хижина", "wilderness_hut": "хижина",
                "drinking_water": "питьевая вода"}
    pois = []
    for el in data.get("elements", []):
        t = el.get("tags", {})
        key = t.get("natural") or t.get("tourism") or t.get("amenity")
        kind = kind_map.get(key) or ("населённый пункт" if t.get("place") else "магазин")
        pois.append({"kind": kind, "name": t.get("name", ""),
                     "lat": el.get("lat"), "lon": el.get("lon")})
    return pois


def collect_facts(points, region=None, use_overpass=True, bbox=None):
    """Собрать факты по всем точкам: поиск + геопоиск Википедии, POI из OSM."""
    facts = {"region": region, "points": [], "pois": [], "sources": set()}

    queries = [region] if region else []
    queries += [p["name"] for p in points]
    for q in queries:
        if not q:
            continue
        for lang in WIKI_LANGS:
            hits = wiki_search(q, lang)
            if hits:
                ex = wiki_extract(hits[0][0], lang)
                if ex:
                    ex["query"] = q
                    facts["points"].append(ex)
                    facts["sources"].add(ex["url"])
                    break
        time.sleep(0.3)  # вежливость к API

    seen_titles = {f["title"] for f in facts["points"]}
    for p in points:
        if "lat" not in p:
            continue
        for lang in WIKI_LANGS:
            for title, dist in wiki_geosearch(p["lat"], p["lon"], lang):
                if title in seen_titles:
                    continue
                seen_titles.add(title)
                ex = wiki_extract(title, lang, limit=800)
                if ex:
                    ex["query"] = f"рядом с {p['name']} ({round(dist)} м)"
                    facts["points"].append(ex)
                    facts["sources"].add(ex["url"])
            time.sleep(0.3)

    if use_overpass and bbox:
        facts["pois"] = overpass_pois(*bbox)
        if facts["pois"]:
            facts["sources"].add("https://www.openstreetmap.org (Overpass API)")
    facts["sources"] = sorted(facts["sources"])
    return facts


def to_markdown(facts):
    """Дайджест фактов для LLM: по точкам + инфраструктура + источники."""
    L = ["# Факты по маршруту (собраны из открытых источников)", ""]
    if facts["points"]:
        L.append("## Статьи Википедии")
        for f in facts["points"]:
            L += ["", f"### {f['title']} ({f['lang']}) — запрос: {f['query']}",
                  f["text"], f"Источник: {f['url']}"]
    if facts["pois"]:
        L += ["", "## Инфраструктура (OpenStreetMap)", ""]
        for p in facts["pois"]:
            name = f" «{p['name']}»" if p["name"] else ""
            L.append(f"- {p['kind']}{name}: {p['lat']}, {p['lon']}")
    L += ["", "## Источники"] + [f"- {s}" for s in facts["sources"]]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("points", help="points.json маршрута")
    ap.add_argument("--out", required=True, help="папка результата (факты.json, Факты.md)")
    ap.add_argument("--region", help="название региона для общего поиска")
    ap.add_argument("--gpx", help="track.gpx — bbox для Overpass (иначе bbox точек)")
    ap.add_argument("--no-overpass", action="store_true", help="не опрашивать OSM")
    args = ap.parse_args()

    points = json.load(open(args.points, encoding="utf-8"))
    if args.gpx:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "gpx_analyze", Path(__file__).parent / "gpx_analyze.py")
        ga = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ga)
        trkpts, _ = ga.load_gpx(args.gpx)
        lats = [p[0] for p in trkpts]
        lons = [p[1] for p in trkpts]
    else:
        lats = [p["lat"] for p in points if "lat" in p]
        lons = [p["lon"] for p in points if "lon" in p]
    bbox = (min(lats) - 0.05, max(lats) + 0.05, min(lons) - 0.05, max(lons) + 0.05)

    facts = collect_facts(points, region=args.region,
                          use_overpass=not args.no_overpass, bbox=bbox)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "факты.json").write_text(
        json.dumps(facts, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (out / "Факты.md").write_text(to_markdown(facts) + "\n", encoding="utf-8")
    print(f"✓ {out / 'Факты.md'}: {len(facts['points'])} статей Википедии, "
          f"{len(facts['pois'])} объектов OSM", file=sys.stderr)


if __name__ == "__main__":
    main()
