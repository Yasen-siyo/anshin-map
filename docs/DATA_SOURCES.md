# 데이터 출처

수집 시점: 2026년 10월. 원자료는 용량 때문에 저장소에 넣지 않았고, `scripts/fetch_data.sh` 와 `scripts/fetch_osm.py` 로 다시 받을 수 있습니다.

| 데이터 | 출처 | 형식 | 이용 조건 |
|---|---|---|---|
| 유흥·도박·성인 시설 | OpenStreetMap, Overpass API (overpass-api.de) | JSON | © OpenStreetMap contributors, [ODbL](https://opendatacommons.org/licenses/odbl/) |
| 도쿄 범죄 | 경시청 「区市町村の町丁別、罪種別及び手口別認知件数」 2025년 (R7.csv) | CSV, Shift_JIS | 경시청 웹사이트 이용 규약 |
| 가나가와 범죄 | 가나가와현경 오픈데이터, 수법별 발생 목록 2025년 (kanagawa_2025*.csv) | CSV, Shift_JIS | 가나가와현경 웹사이트 이용 규약 |
| 지바 범죄 | 지바현경 「犯罪発生情報」 지도 (map.police.chiba.dsvc.jp) 의 발생 목록 중 2025년분 | TSV | 지바현경 웹사이트 이용 규약 |
| 町丁 경계 | e-Stat 境界データ, 2020년 국세조사 小地域, 세계측지계 위경도 Shapefile (12·13·14, 이웃 현 08·11·19·22) | Shapefile | [e-Stat 이용 규약](https://www.e-stat.go.jp/terms-of-use) (출처 표기) |

지도 페이지에서 불러오는 외부 서비스:

| 용도 | 서비스 |
|---|---|
| 지도 라이브러리 | Leaflet 1.9.4 (cdnjs) |
| 배경 지도 | Esri World Street Map / Light Gray Canvas, 국토지리원 연한 지도, OpenStreetMap 타일 |
| 지명 검색 | OpenStreetMap Nominatim, 국토지리원 주소 검색 |

## 원자료 형식 메모

- 지바 TSV 열: id, 수법 대분류, 수법 소분류, 경찰서 코드, 발생일, 町丁 이름, 町丁 코드(= e-Stat KEY_CODE, 丁目 없는 町은 끝 00), 갱신 시각.
  수법 대분류 코드: 11 侵入強盗, 12 路上強盗, 13 侵入窃盗, 14 自動車盗, 15 オートバイ盗, 16 自転車盗, 17 部品ねらい, 18 車上ねらい, 19 自動販売機ねらい, 20 電話de詐欺, 21 SNS型投資・ロマンス詐欺.
- 경찰 자료는 「１丁目」, e-Stat 은 「一丁目」 표기라 `geo.norm_name` 에서 맞춥니다. 경계와 일치한 비율: 도쿄 99.6%, 가나가와 97.2%, 지바 100%.
- e-Stat 경계에서 HCODE 8154 (수면) 구역은 제외합니다.
