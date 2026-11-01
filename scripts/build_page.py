"""score.py 결과를 템플릿에 넣어, 더블클릭으로도 열 수 있는 단일 HTML(index.html)을 만든다."""
import base64
import hashlib
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import config as C  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEB = ROOT / "web"


def b64(path):
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def region(rid):
    d = WEB / rid
    return dict(
        meta=json.loads((d / "meta.json").read_text(encoding="utf-8")),
        heat=b64(d / "heatmap.png"), anshin=b64(d / "anshin.png"), cover=b64(d / "coverage.png"),
        poi=json.loads((d / "poi.geojson").read_text(encoding="utf-8")),
    )


def main():
    html = (WEB / "template.html").read_text(encoding="utf-8")
    regions = [region(rid) for rid in C.REGIONS if (WEB / rid / "meta.json").exists()]
    # 시설 이름에 "</script>" 같은 글자가 있어도 스크립트 태그가 끊기지 않게 "<" 를 이스케이프한다
    data = json.dumps(regions, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    html = html.replace("/*REGIONS*/null", data)
    # CSP 가 허용할 인라인 스크립트는 지금 만든 이 스크립트 하나뿐
    inline = re.findall(r"<script>(.*?)</script>", html, re.S)
    assert len(inline) == 1, "인라인 스크립트는 하나여야 CSP 해시가 맞는다"
    digest = base64.b64encode(hashlib.sha256(inline[0].encode("utf-8")).digest()).decode()
    html = html.replace("/*SCRIPT_HASH*/", "sha256-" + digest)
    out = ROOT / "index.html"  # GitHub Pages 시작 페이지
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
