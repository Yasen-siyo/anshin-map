"""알려진 지역의 안심도를 찍어 보는 검증용 스크립트."""
import json
import math
import pathlib

import numpy as np
from PIL import Image

WEB = pathlib.Path(__file__).resolve().parent.parent / "web"
PLACES = {
    "가부키초": (35.6945, 139.7030), "롯폰기": (35.6628, 139.7314), "이케부쿠로 서쪽": (35.7310, 139.7080),
    "가와사키역 동쪽": (35.5315, 139.7010), "우에노": (35.7105, 139.7745), "요코하마 간나이": (35.4440, 139.6370),
    "긴자": (35.6717, 139.7650), "도쿄역": (35.6812, 139.7671), "세이조": (35.6406, 139.5987),
    "덴엔초후": (35.5966, 139.6676), "요코하마 미나토미라이": (35.4580, 139.6320), "지바역": (35.6130, 140.1130),
    "마쿠하리": (35.6480, 140.0420), "후나바시역": (35.7015, 139.9850),
}


def main():
    meta = json.loads((WEB / "meta.json").read_text())
    a = np.asarray(Image.open(WEB / "anshin.png"))[..., 0]
    (s, w), (n, e) = meta["bounds"]
    y = lambda lat: math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))  # noqa: E731
    for name, (lat, lon) in PLACES.items():
        j = int((lon - w) / (e - w) * meta["nx"])
        i = int((y(n) - y(lat)) / (y(n) - y(s)) * meta["ny"])
        win = a[max(i - 2, 0):i + 3, max(j - 2, 0):j + 3]
        print(f"{name:14s} {a[i, j]:3d}  (주변 250m 최저 {win.min()})")


if __name__ == "__main__":
    main()
