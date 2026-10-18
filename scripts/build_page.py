"""score.py 결과를 템플릿에 넣어, 더블클릭으로 열 수 있는 단일 HTML(web/anshin-map.html)을 만든다."""
import base64
import pathlib

WEB = pathlib.Path(__file__).resolve().parent.parent / "web"


def b64(name):
    return "data:image/png;base64," + base64.b64encode((WEB / name).read_bytes()).decode()


def main():
    html = (WEB / "template.html").read_text(encoding="utf-8")
    html = (html.replace("/*META*/null", (WEB / "meta.json").read_text(encoding="utf-8"))
                .replace('"/*HEAT*/"', '"' + b64("heatmap.png") + '"')
                .replace('"/*ANSHIN*/"', '"' + b64("anshin.png") + '"')
                .replace('"/*COVER*/"', '"' + b64("coverage.png") + '"')
                .replace("/*POI*/null", (WEB / "poi.geojson").read_text(encoding="utf-8")))
    # web/anshin-map.html 과 저장소 루트의 index.html (GitHub Pages 시작 페이지) 두 곳에 쓴다
    for out in (WEB / "anshin-map.html", WEB.parent / "index.html"):
        out.write_text(html, encoding="utf-8")
        print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
