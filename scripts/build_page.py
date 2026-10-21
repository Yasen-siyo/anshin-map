"""score.py 결과를 템플릿에 넣어, 더블클릭으로도 열 수 있는 단일 HTML(index.html)을 만든다."""
import base64
import hashlib
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEB = ROOT / "web"


def b64(name):
    return "data:image/png;base64," + base64.b64encode((WEB / name).read_bytes()).decode()


def js_json(name):
    # 시설 이름에 "</script>" 같은 글자가 있어도 스크립트 태그가 끊기지 않게 "<" 를 이스케이프한다
    return (WEB / name).read_text(encoding="utf-8").replace("<", "\\u003c")


def main():
    html = (WEB / "template.html").read_text(encoding="utf-8")
    html = (html.replace("/*META*/null", js_json("meta.json"))
                .replace('"/*HEAT*/"', '"' + b64("heatmap.png") + '"')
                .replace('"/*ANSHIN*/"', '"' + b64("anshin.png") + '"')
                .replace('"/*COVER*/"', '"' + b64("coverage.png") + '"')
                .replace("/*POI*/null", js_json("poi.geojson")))
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
