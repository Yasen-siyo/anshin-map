"""경찰 町丁별 범죄 자료를 한 형식으로 정리해 data/raw/crime_normalized.csv 로 저장.

세 현이 공통으로 공개하는 범죄 종류만 쓴다 (경찰청 표준 오픈데이터 수준):
ひったくり, 車上ねらい, 自販機ねらい, 自動車盗, オートバイ盗, 自転車盗.
- 도쿄: 경시청 町丁별 罪種·手口별 認知件数 (data/raw/crime/tokyo_R7.csv)
- 가나가와: 가나가와현경 오픈데이터 수법별 발생 건 목록 (data/raw/crime/kanagawa_2025*.csv)
- 지바: 지바현경 犯罪発生情報 지도(map.police.chiba.dsvc.jp)의 발생 목록 data/tsv/crime.tsv 중 2025년분
  (路上強盗 분류를 ひったくり 자리에 넣음. 지바는 날치기를 路上強盗로 묶어 공개)
"""
import csv
import glob
import io
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from geo import norm_name, read_dbf  # noqa: E402

RAW = pathlib.Path(__file__).resolve().parent.parent / "data/raw"
CATS = ["ひったくり", "車上ねらい", "自販機ねらい", "自動車盗", "オートバイ盗", "自転車盗"]
KANAGAWA_FILES = {
    "hittakuri": "ひったくり", "syazyounerai": "車上ねらい", "zidouhanbaikinerai": "自販機ねらい",
    "zidousyatou": "自動車盗", "ootobaitou": "オートバイ盗", "zitensyatou": "自転車盗",
}


def read_cp932(path):
    return list(csv.DictReader(io.StringIO(pathlib.Path(path).read_bytes().decode("cp932", errors="replace"))))


def tokyo(rows_out):
    cities = sorted({r["CITY_NAME"] for r in read_dbf(RAW / "boundary/r2ka13.dbf") if r["CITY_NAME"]},
                    key=len, reverse=True)
    skipped = 0
    for r in read_cp932(RAW / "crime/tokyo_R7.csv"):
        name = r["市区町丁"]
        city = next((c for c in cities if name.startswith(c)), None)
        town = name[len(city):] if city else ""
        if not city or town in ("計", "以下不詳") or not town:
            skipped += 1
            continue
        counts = {c: float(r.get("非侵入窃盗" + c) or 0) for c in CATS}
        rows_out.append(dict(pref="東京都", city=city, town=town, **counts))
    print(f"tokyo: {len(rows_out)} towns ({skipped} total/unknown rows skipped)")


def kanagawa(rows_out):
    acc = {}
    for path in sorted(glob.glob(str(RAW / "crime/kanagawa_2025*.csv"))):
        key = pathlib.Path(path).stem.replace("kanagawa_2025", "")
        cat = KANAGAWA_FILES.get(key)
        if not cat:
            continue
        for r in read_cp932(path):
            city, town = r["市区町村（発生地）"], r["町丁目（発生地）"]
            if not town:
                continue
            d = acc.setdefault((city, town), {c: 0.0 for c in CATS})
            d[cat] += 1
    for (city, town), d in acc.items():
        rows_out.append(dict(pref="神奈川県", city=city, town=town, **d))
    print(f"kanagawa: {len(acc)} towns")


# 지바 지도 데이터의 수법 대분류 코드 → 공통 범죄 종류
CHIBA_CODES = {12: "ひったくり", 14: "自動車盗", 15: "オートバイ盗", 16: "自転車盗", 18: "車上ねらい", 19: "自販機ねらい"}


def chiba(rows_out, year="2025"):
    recs = read_dbf(RAW / "boundary/r2ka12.dbf")
    names = {r["KEY_CODE"]: (r["CITY_NAME"], r["S_NAME"]) for r in recs}
    # 丁目 없이 町 단위(끝 2자리 00)로 기록된 사건은 그 町의 丁目들에 면적 비율로 나눈다
    children = {}
    for r in recs:
        if len(r["KEY_CODE"]) == 11 and r["S_NAME"]:
            children.setdefault(r["KEY_CODE"][:9], []).append(((r["CITY_NAME"], r["S_NAME"]), float(r["AREA"] or 0)))
    acc, seen, nomatch = {}, set(), 0
    for line in (RAW / "crime/chiba/crime.tsv").read_text(encoding="utf-8").splitlines():
        f = line.split("\t")
        if len(f) < 7 or not f[4].startswith(year) or f[0] in seen:
            continue
        seen.add(f[0])
        cat = CHIBA_CODES.get(int(f[1]))
        if not cat:
            continue
        key = names.get(f[6]) or (names.get(f[6][:9]) if f[6].endswith("00") else None)
        if key is not None:
            targets = [(key, 1.0)]
        else:
            kids = children.get(f[6][:9], [])
            tot = sum(a for _, a in kids)
            targets = [(k, a / tot) for k, a in kids] if tot > 0 else []
        if not targets:
            nomatch += 1
            continue
        for k, share in targets:
            d = acc.setdefault(k, {c: 0.0 for c in CATS})
            d[cat] += share
    for (city, town), d in acc.items():
        rows_out.append(dict(pref="千葉県", city=city, town=town, **d))
    print(f"chiba: {len(acc)} towns, {nomatch} incidents with unknown town code")


def main():
    rows = []
    tokyo(rows)
    n = len(rows)
    kanagawa(rows)
    n2 = len(rows)
    chiba(rows)
    with open(RAW / "crime_normalized.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["pref", "city", "town", *CATS])
        w.writeheader()
        w.writerows(rows)
    # 경계 이름과 얼마나 맞는지 확인
    keys = set()
    for p in ("12", "13", "14"):
        for r in read_dbf(RAW / f"boundary/r2ka{p}.dbf"):
            keys.add((norm_name(r["CITY_NAME"]), norm_name(r["S_NAME"])))
    for label, part in (("tokyo", rows[:n]), ("kanagawa", rows[n:n2]), ("chiba", rows[n2:])):
        tot = sum(sum(r[c] for c in CATS) for r in part)
        hit = sum(sum(r[c] for c in CATS) for r in part if (norm_name(r["city"]), norm_name(r["town"])) in keys)
        miss = [r["city"] + r["town"] for r in part if (norm_name(r["city"]), norm_name(r["town"])) not in keys]
        print(f"{label}: {hit / max(tot, 1):.1%} of incidents match a boundary; unmatched e.g. {miss[:8]}")


if __name__ == "__main__":
    main()
