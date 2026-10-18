#!/usr/bin/env bash
# 경찰 범죄 통계(2025년)와 e-Stat 町丁 경계를 data/raw/ 아래로 내려받는다.
set -euo pipefail
cd "$(dirname "$0")/.."
RAW=data/raw
mkdir -p "$RAW/crime/chiba" "$RAW/boundary/neighbors"

get() {  # 실패하면 몇 번 다시 시도 (경찰 사이트가 가끔 연결을 끊음)
  for i in 1 2 3 4 5; do curl -sSfL -m 180 -o "$2" "$1" && return 0; sleep 3; done
  echo "failed: $1" >&2; return 1
}

echo "도쿄 (경시청)"
get https://www.keishicho.metro.tokyo.lg.jp/about_mpd/jokyo_tokei/jokyo/ninchikensu.files/R7.csv "$RAW/crime/tokyo_R7.csv"

echo "가나가와 (현경 오픈데이터)"
for t in hittakuri syazyounerai buhinnerai zidouhanbaikinerai zidousyatou ootobaitou zitensyatou; do
  get "https://www.police.pref.kanagawa.jp/assets/entry/kanagawa_2025$t.csv" "$RAW/crime/kanagawa_2025$t.csv"
done

echo "지바 (현경 犯罪発生情報 지도)"
get https://map.police.chiba.dsvc.jp/data/tsv/crime.tsv "$RAW/crime/chiba/crime.tsv"

echo "e-Stat 町丁 경계 (2020 국세조사 小地域)"
estat() {  # $1 = 현 코드, $2 = 저장 폴더
  local z; z=$(mktemp)
  get "https://www.e-stat.go.jp/gis/statmap-search/data?dlserveyId=A002005212020&code=$1&coordSys=1&format=shape&downloadType=5&datum=2000" "$z"
  unzip -oq "$z" -d "$2"; rm -f "$z"
}
for c in 12 13 14; do estat $c "$RAW/boundary"; done
for c in 08 11 19 22; do estat $c "$RAW/boundary/neighbors"; done   # 데이터 없음 표시용 이웃 현

echo "완료. 다음: python3 scripts/fetch_osm.py"
