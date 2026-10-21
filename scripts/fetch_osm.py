"""OpenStreetMap(Overpass)에서 유흥·도박·성인 시설 위치를 받아 data/raw/osm_poi.json 에 저장.

Overpass 서버가 불안정할 때가 많아 대상 범위를 작은 칸으로 나눠 받고,
실패한 칸은 다시 시도한다. 받은 칸은 data/raw/osm_tiles/ 에 남겨 두어
중간에 끊겨도 다음 실행에서 이어 받는다.
"""
import json
import pathlib
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import config as C  # noqa: E402

RAW = pathlib.Path(__file__).resolve().parent.parent / "data/raw"
OUT = RAW / "osm_poi.json"
TILES = RAW / "osm_tiles"
STEP = 0.25  # 칸 크기 (도)

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
]

QUERY = """
[out:json][timeout:180][bbox:{s},{w},{n},{e}];
(
 nwr["amenity"~"^(bar|pub|nightclub|stripclub|gambling|casino|brothel|love_hotel|hookah_lounge)$"];
 nwr["leisure"="adult_gaming_centre"];
 nwr["shop"~"^(erotic|adult)$"];
 nwr["tourism"="hotel"]["hotel"~"^(love|love_hotel)$"];
 nwr["love_hotel"];
 nwr["name"~"パチンコ|パチスロ|スロット"];
);
out center tags;
"""


def fetch(q):
    data = urllib.parse.urlencode({"data": q}).encode()
    last = None
    for url in ENDPOINTS:
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": "anshin-map/0.1"})
            with urllib.request.urlopen(req, timeout=240) as r:
                j = json.loads(r.read())
            if "error" in j.get("remark", "").lower():
                raise RuntimeError(j["remark"])
            return j
        except Exception as ex:  # noqa: BLE001
            last = ex
    raise RuntimeError(last)


def tiles():
    b = C.BBOX
    s = b["south"]
    while s < b["north"]:
        w = b["west"]
        while w < b["east"]:
            yield round(s, 3), round(w, 3), round(min(s + STEP, b["north"]), 3), round(min(w + STEP, b["east"]), 3)
            w += STEP
        s += STEP


def merge(missing):
    seen, elems = set(), []
    for f in sorted(TILES.glob("*.json")):
        for e in json.loads(f.read_text()):
            k = (e["type"], e["id"])
            if k not in seen:
                seen.add(k)
                elems.append(e)
    OUT.write_text(json.dumps({"elements": elems, "missing_tiles": missing}, ensure_ascii=False))
    print(f"saved {len(elems)} elements, {len(missing)} tiles missing -> {OUT}", flush=True)


def main(max_rounds=int(sys.argv[1]) if len(sys.argv) > 1 else 100):
    TILES.mkdir(parents=True, exist_ok=True)
    todo = [t for t in tiles() if not (TILES / f"{t[0]}_{t[1]}.json").exists()]
    for rnd in range(1, max_rounds + 1):
        if not todo:
            break
        left = []
        for t in todo:
            s, w, n, e = t
            try:
                j = fetch(QUERY.format(s=s, w=w, n=n, e=e))
                (TILES / f"{s}_{w}.json").write_text(json.dumps(j["elements"], ensure_ascii=False))
                print(f"tile {s},{w}: {len(j['elements'])}", flush=True)
            except Exception as ex:  # noqa: BLE001
                print(f"tile {s},{w} failed: {str(ex)[:100]}", flush=True)
                left.append(t)
                time.sleep(3)
        todo = left
        if todo:
            print(f"round {rnd}: {len(todo)} tiles left", flush=True)
            time.sleep(30)
    merge([list(t) for t in todo])


if __name__ == "__main__":
    main()
