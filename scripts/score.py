"""격자별 위험 점수를 계산해 지도용 히트맵 이미지와 메타데이터를 만든다.

입력
  data/raw/osm_poi.json            fetch_osm.py 결과
  data/raw/crime_normalized.csv    (선택) prep_crime.py 결과: pref,city,town,<罪種...>
  data/raw/boundary/*.shp          (선택) e-Stat 小地域(町丁・字等) 경계 shapefile

출력 (web/ 아래, 지도 페이지가 그대로 읽음)
  heatmap.png   Web Mercator 정렬 RGBA 이미지 (빨강일수록 위험)
  meta.json     이미지 범위, 격자 정보, 카테고리 집계
  poi.geojson   확대 시 표시할 시설 점
"""
import csv
import glob
import json
import math
import pathlib
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import config as C  # noqa: E402
from geo import gaussian, norm_name, read_dbf, read_shp_polygons  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw"
WEB = ROOT / "web"
R = 6378137.0


def merc(lon, lat):
    x = np.radians(lon) * R
    y = np.log(np.tan(np.pi / 4 + np.radians(lat) / 2)) * R
    return x, y


def grid():
    b = C.BBOX
    x0, y0 = merc(b["west"], b["south"])
    x1, y1 = merc(b["east"], b["north"])
    # 메르카토르 단위는 위도에 따라 늘어나므로 중심 위도 기준으로 보정
    k = 1 / math.cos(math.radians((b["south"] + b["north"]) / 2))
    step = C.CELL_M * k
    nx = int(math.ceil((x1 - x0) / step))
    ny = int(math.ceil((y1 - y0) / step))
    return dict(x0=float(x0), y1=float(y1), step=step, nx=nx, ny=ny, k=k)


# ---------- 시설 ----------

def classify(tags):
    name = tags.get("name", "")
    if any(w in name for w in C.EXCLUDE_NAME):
        return None
    a = tags.get("amenity")
    g = tags.get("gambling", "")
    if a == "stripclub":
        return "stripclub"
    if a == "brothel":
        return "brothel"
    if a == "nightclub":
        return "nightclub"
    if any(w in name for w in ("換金", "宝くじ", "TUC")) or g == "lottery":
        return None
    if any(w in name for w in ("パチンコ", "パチスロ", "スロット", "ぱちんこ")) or "pachinko" in g \
            or tags.get("leisure") == "adult_gaming_centre":
        return "pachinko"
    if a in ("gambling", "casino"):
        return "gambling"
    if tags.get("shop") in ("erotic", "adult"):
        return "adult_shop"
    if a == "love_hotel" or tags.get("hotel") in ("love", "love_hotel") or "love_hotel" in tags:
        return "love_hotel"
    if a == "bar":
        return "bar"
    # 일본 OSM 에서 amenity=pub 은 대부분 이자카야 체인이라, 이름이 바·스낵 계열일 때만 센다
    if a == "pub" and any(w.lower() in name.lower() for w in C.PUB_AS_BAR_NAME):
        return "bar"
    if a == "hookah_lounge":
        return "hookah"
    return None


def load_pois():
    if not (RAW / "osm_poi.json").exists():
        print("osm_poi.json not found, facility layer empty")
        return []
    src = json.loads((RAW / "osm_poi.json").read_text())
    out = []
    for e in src["elements"]:
        tags = e.get("tags", {})
        cat = classify(tags)
        if not cat:
            continue
        lat = e.get("lat", e.get("center", {}).get("lat"))
        lon = e.get("lon", e.get("center", {}).get("lon"))
        if lat is None:
            continue
        out.append((lon, lat, cat, tags.get("name", "")))
    return out


def poi_layer(g, pois):
    acc = np.zeros((g["ny"], g["nx"]), dtype=np.float32)
    for lon, lat, cat, _ in pois:
        x, y = merc(lon, lat)
        i = int((g["y1"] - y) / g["step"])
        j = int((x - g["x0"]) / g["step"])
        if 0 <= i < g["ny"] and 0 <= j < g["nx"]:
            acc[i, j] += C.POI_WEIGHTS[cat]
    sigma = C.POI_SIGMA_M / C.CELL_M
    # 합이 보존되도록 정규화된 가우시안 → 단위: 가중 시설 수 / 셀
    return gaussian(acc, sigma) * (2 * math.pi * sigma * sigma)


# ---------- 범죄 ----------

TARGET_PREFS = [12, 13, 14]  # 지바·도쿄·가나가와
PREF_FINE = None  # 촘촘한 격자의 현 코드 (0 = 대상 3개 현 밖 또는 바다)
FINE = 4  # 町丁 경계를 격자보다 4배 촘촘하게 그린 뒤 평균 (작은 町丁이 사라지지 않게)


def crime_layer(g):
    """町丁별 가중 범죄 밀도(건/km²) 격자와, 범죄 자료가 없는 현이 차지하는 비율 격자를 돌려준다."""
    from PIL import ImageDraw

    csv_path = RAW / "crime_normalized.csv"
    shps = sorted(glob.glob(str(RAW / "boundary/*.shp")))
    if not csv_path.exists() or not shps:
        print("crime data not found, skipping crime layer")
        return None, None

    crimes = {}
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (norm_name(row["city"]), norm_name(row["town"]))
            w = sum(float(row.get(k) or 0) * v for k, v in C.CRIME_WEIGHTS.items())
            crimes[key] = crimes.get(key, 0) + w

    # 町丁 하나가 여러 도형으로 나뉜 경우가 있어 면적을 키별로 합친다
    areas, recs = [], []
    for shp in shps:
        rows = read_dbf(shp[:-4] + ".dbf")
        polys = read_shp_polygons(shp)
        for rec, rings in zip(rows, polys):
            if rec["HCODE"] == "8154":  # 수면(바다·호수) 구역은 제외
                continue
            recs.append((rec, rings))
    key_area = {}
    for rec, _ in recs:
        k = (norm_name(rec["CITY_NAME"]), norm_name(rec["S_NAME"]))
        key_area[k] = key_area.get(k, 0) + float(rec["AREA"] or 0)

    W, H = g["nx"] * FINE, g["ny"] * FINE
    step = g["step"] / FINE
    dens_img = Image.new("F", (W, H), 0.0)
    pref_img = Image.new("L", (W, H), 0)
    dd, pd = ImageDraw.Draw(dens_img), ImageDraw.Draw(pref_img)
    # 이웃 현(대상 밖)도 육지로 칠해 두어 "데이터 없음" 빗금을 바다와 구분한다
    for shp in sorted(glob.glob(str(RAW / "boundary/neighbors/*.shp"))):
        rows = read_dbf(shp[:-4] + ".dbf")
        for rec, rings in zip(rows, read_shp_polygons(shp)):
            if rec["HCODE"] == "8154":
                continue
            for ring in rings:
                if len(ring) < 3:
                    continue
                x, y = ring[:, 0], ring[:, 1]
                if x.max() < C.BBOX["west"] or x.min() > C.BBOX["east"] or y.max() < C.BBOX["south"] or y.min() > C.BBOX["north"]:
                    continue
                mx, my = merc(x, y)
                pd.polygon(list(zip(((mx - g["x0"]) / step).tolist(), ((g["y1"] - my) / step).tolist())), fill=int(rec["PREF"]))
    matched = 0
    # 큰 도형부터 그려서 안쪽에 들어 있는 작은 町丁이 위에 덮이게 한다 (구멍 링은 무시)
    recs.sort(key=lambda r: -float(r[0]["AREA"] or 0))
    for rec, rings in recs:
        k = (norm_name(rec["CITY_NAME"]), norm_name(rec["S_NAME"]))
        w = crimes.get(k)
        dens = 0.0
        if w is not None and key_area.get(k, 0) > 0:
            dens = w / (key_area[k] / 1e6)
            matched += 1
        pref = int(rec["PREF"])
        for ring in rings:
            if len(ring) < 3:
                continue
            # 시계 방향(외곽) 링만 그린다
            x, y = ring[:, 0], ring[:, 1]
            if np.sum((x[1:] - x[:-1]) * (y[1:] + y[:-1])) <= 0:
                continue
            mx, my = merc(x, y)
            px = (mx - g["x0"]) / step
            py = (g["y1"] - my) / step
            pts = list(zip(px.tolist(), py.tolist()))
            dd.polygon(pts, fill=float(dens))
            pd.polygon(pts, fill=pref)
    print(f"crime: {matched}/{len(recs)} boundary polygons have crime data, {len(crimes)} crime rows")

    def block_mean(a):
        return a.reshape(g["ny"], FINE, g["nx"], FINE).mean(axis=(1, 3))

    dens = block_mean(np.asarray(dens_img, dtype=np.float32))
    pref = np.asarray(pref_img)
    global PREF_FINE
    PREF_FINE = pref
    no_crime = np.zeros((g["ny"], g["nx"]), dtype=np.float32)
    land = block_mean((pref > 0).astype(np.float32))
    for code in C.NO_CRIME_PREFS:
        no_crime += block_mean((pref == int(code)).astype(np.float32))
    no_crime = np.where(land > 0, no_crime / np.maximum(land, 1e-6), 0)
    return gaussian(dens, 1.5), gaussian(no_crime, 1.5)


# ---------- 합성·렌더 ----------

def normalize(a, lo, hi):
    """로그 척도로 0~1 정규화. lo 이하(흔한 수준)는 0, hi 이상은 1."""
    v = np.log(np.maximum(a, lo) / lo) / np.log(hi / lo)
    return np.clip(v, 0, 1).astype(np.float32)


def combine(poi, crime):
    """둘 중 높은 쪽을 주로 보고(MAX_SHARE), 나머지는 MIX 가중 평균으로 더한다.
    시설이 몰린 유흥가나 범죄가 잦은 곳 어느 한쪽만 심해도 위험으로 잡히게."""
    mean = C.MIX["poi"] * poi + C.MIX["crime"] * crime
    return C.MAX_SHARE * np.maximum(poi, crime) + (1 - C.MAX_SHARE) * mean


def colorize(risk):
    # 초록(안전) → 노랑 → 빨강(위험). 위험이 낮으면 투명하게.
    stops = np.array([[46, 160, 67], [250, 204, 21], [234, 88, 12], [185, 28, 28]], dtype=np.float32)
    t = np.clip(risk, 0, 1) * (len(stops) - 1)
    lo = np.floor(t).astype(int).clip(0, len(stops) - 2)
    f = (t - lo)[..., None]
    rgb = stops[lo] * (1 - f) + stops[lo + 1] * f
    alpha = np.clip(risk * 1.6, 0, 1) * 220
    alpha[risk < 0.04] = 0
    return np.dstack([rgb, alpha]).astype(np.uint8)


def coverage(g, missing_poi):
    """데이터가 있는 곳/없는 곳을 나타내는 이미지와 점수표용 코드 격자를 만든다.

    코드: 0 = 대상 밖(점수 없음), 1 = 시설+범죄, 2 = 시설만(범죄 자료 없음)
    coverage.png: 범죄 자료가 없는 지역에 회색 빗금, 자료가 있는 지역 둘레에 진한 선 (격자의 2배 해상도)
    """
    pref = PREF_FINE
    half = FINE // 2
    no_crime_codes = [int(c) for c in C.NO_CRIME_PREFS]
    # 점수표용 코드 (100m 격자): 칸 안에서 가장 많은 쪽
    blocks = pref.reshape(g["ny"], FINE, g["nx"], FINE)
    land = np.isin(blocks, TARGET_PREFS).mean(axis=(1, 3))
    nc = np.isin(blocks, no_crime_codes).mean(axis=(1, 3))
    code = np.where(land < 0.25, 0, np.where(nc > land / 2, 2, 1)).astype(np.uint8)
    for s_, w_, n_, e_ in missing_poi:  # Overpass 에서 못 받은 칸은 데이터 없음으로
        x0, y0 = merc(w_, n_)
        x1, y1 = merc(e_, s_)
        j0, j1 = int((x0 - g["x0"]) / g["step"]), int((x1 - g["x0"]) / g["step"]) + 1
        i0, i1 = int((g["y1"] - y0) / g["step"]), int((g["y1"] - y1) / g["step"]) + 1
        code[max(i0, 0):i1, max(j0, 0):j1] = 0

    p2 = pref[::half, ::half]
    h, w = p2.shape
    code2 = np.repeat(np.repeat(code, 2, 0), 2, 1)[:h, :w]
    img = np.zeros((h, w, 4), dtype=np.uint8)
    ii, jj = np.indices((h, w))
    hatch = ((ii + jj) % 6) < 2
    # 빗금: 육지인데 점수가 없거나(대상 밖 이웃 현, 못 받은 칸) 범죄 자료가 없는 곳
    nod = (p2 > 0) & ((code2 == 0) | (code2 == 2))
    img[nod] = (110, 110, 120, 70)
    img[nod & hatch] = (70, 70, 80, 200)
    # 경계선: 범죄+시설 자료가 모두 있는 지역의 둘레
    cov = np.isin(p2, TARGET_PREFS) & (code2 == 1)
    edge = np.zeros_like(cov)
    for di, dj in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        edge |= cov & ~np.roll(np.roll(cov, di, 0), dj, 1)
    img[edge] = (15, 60, 120, 255)
    Image.fromarray(img, "RGBA").save(WEB / "coverage.png", optimize=True)
    return code


def main():
    g = grid()
    print(f"grid {g['nx']}x{g['ny']} cells of {C.CELL_M}m")
    pois = load_pois()
    poi = normalize(poi_layer(g, pois), *C.POI_RANGE)
    crime_raw, no_crime = crime_layer(g)
    if crime_raw is None:
        risk = poi
        mix = {"poi": 1.0, "crime": 0.0}
    elif not pois:
        risk = normalize(crime_raw, *C.CRIME_RANGE)
        mix = {"poi": 0.0, "crime": 1.0}
    else:
        mixed = combine(poi, normalize(crime_raw, *C.CRIME_RANGE))
        # 범죄 자료가 없는 현(지바)은 시설 점수만 쓴다
        risk = no_crime * poi + (1 - no_crime) * mixed
        mix = C.MIX

    WEB.mkdir(parents=True, exist_ok=True)
    missing = json.loads((RAW / "osm_poi.json").read_text()).get("missing_tiles", []) if pois else []
    code = coverage(g, missing)
    # 대상 밖(이웃 현·바다)에는 색을 칠하지 않는다
    Image.fromarray(colorize(np.where(code > 0, risk, 0)), "RGBA").save(WEB / "heatmap.png", optimize=True)

    # 지도 페이지에서 마우스 위치 점수를 보여주기 위한 저해상도 점수표 (0~100 안심도)
    # R = 안심도, G = 데이터 범위 코드 (coverage 참고)
    anshin = np.round(100 * (1 - risk)).astype(np.uint8)

    if not pois:  # 시설 자료가 아직 없으면 범죄 자료 없는 현은 점수 없음
        code[code == 2] = 0
    Image.fromarray(np.dstack([anshin, code, np.zeros_like(code)]), "RGB").save(WEB / "anshin.png", optimize=True)

    b = C.BBOX
    lon1 = math.degrees((g["x0"] + g["nx"] * g["step"]) / R)
    lat0 = math.degrees(2 * math.atan(math.exp((g["y1"] - g["ny"] * g["step"]) / R)) - math.pi / 2)
    counts = {}
    for *_, cat, _ in pois:
        counts[cat] = counts.get(cat, 0) + 1
    meta = dict(
        bounds=[[lat0, b["west"]], [b["north"], lon1]],
        cell_m=C.CELL_M, nx=g["nx"], ny=g["ny"],
        poi_counts=counts, mix=mix, weights=C.POI_WEIGHTS,
        no_crime_prefs=C.NO_CRIME_PREFS,
        sources=C.SOURCES_NOTE,
    )
    (WEB / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))

    feats = [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
         "properties": {"c": cat, "n": name}}
        for lon, lat, cat, name in pois
    ]
    (WEB / "poi.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False))
    print("poi counts:", counts)
    print("wrote", WEB)


if __name__ == "__main__":
    main()
