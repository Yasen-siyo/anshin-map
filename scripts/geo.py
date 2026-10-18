"""외부 라이브러리 없이 쓰는 지리 도구: shapefile 읽기, 町丁 이름 정규화, 가우시안 흐림."""
import re
import struct
import unicodedata

import numpy as np

KANJI_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def kanji_to_int(s):
    if s.isdigit():
        return int(s)
    n, cur = 0, 0
    for ch in s:
        v = KANJI_NUM[ch]
        if v == 10:
            n += (cur or 1) * 10
            cur = 0
        else:
            cur = v
    return n + cur


def norm_name(s):
    """경찰 자료(１丁目)와 e-Stat(一丁目) 표기 차이를 맞춘다."""
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"\s", "", s)
    s = s.replace("ヶ", "ケ").replace("ヵ", "カ").replace("が丘", "ケ丘").replace("之", "ノ")
    s = re.sub(r"^(大字|字)", "", s)
    s = re.sub(r"([一二三四五六七八九十]+|\d+)丁目", lambda m: f"{kanji_to_int(m.group(1))}丁目", s)
    return s


def read_dbf(path, encoding="cp932"):
    with open(path, "rb") as f:
        h = f.read(32)
        n = struct.unpack("<I", h[4:8])[0]
        hl, rl = struct.unpack("<HH", h[8:12])
        flds = []
        while True:
            d = f.read(32)
            if d[0] == 0x0D:
                break
            flds.append((d[:11].split(b"\0")[0].decode(), d[16]))
        f.seek(hl)
        rows = []
        for _ in range(n):
            r = f.read(rl)
            p, row = 1, {}
            for nm, ln in flds:
                row[nm] = r[p:p + ln].decode(encoding, errors="replace").strip()
                p += ln
            rows.append(row)
    return rows


def read_shp_polygons(path):
    """shp 의 각 도형을 [링(N×2 경위도 배열), ...] 목록으로 돌려준다 (레코드 순서 = dbf 순서)."""
    out = []
    with open(path, "rb") as f:
        f.seek(100)
        while True:
            hdr = f.read(8)
            if len(hdr) < 8:
                break
            ln = struct.unpack(">i", hdr[4:8])[0] * 2
            rec = f.read(ln)
            st = struct.unpack("<i", rec[:4])[0]
            if st == 0:
                out.append([])
                continue
            nparts, npts = struct.unpack("<ii", rec[36:44])
            parts = list(struct.unpack(f"<{nparts}i", rec[44:44 + 4 * nparts])) + [npts]
            pts = np.frombuffer(rec, dtype="<f8", count=npts * 2, offset=44 + 4 * nparts).reshape(-1, 2)
            out.append([pts[parts[i]:parts[i + 1]] for i in range(nparts)])
    return out


def gaussian(a, sigma):
    """scipy 없이 분리형 가우시안 필터 (경계는 0으로 채움)."""
    if sigma <= 0:
        return a
    r = int(3 * sigma + 0.5)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    out = a.astype(np.float32)
    for axis in (0, 1):
        pad = [(0, 0), (0, 0)]
        pad[axis] = (r, r)
        p = np.pad(out, pad)
        acc = np.zeros_like(out)
        n = out.shape[axis]
        for i, w in enumerate(k):
            acc += w * (p[i:i + n] if axis == 0 else p[:, i:i + n])
        out = acc
    return out
