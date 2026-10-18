# GitHub Pages 에 올리기

1. GitHub 에서 새 저장소를 만듭니다 (예: `anshin-map`, Public).
   무료 계정에서 Pages 를 쓰려면 Public 이어야 합니다.
2. 이 폴더의 파일을 모두 올립니다.
   - 웹에서: 저장소 첫 화면의 "uploading an existing file" 을 눌러 폴더 안 파일과 폴더를 끌어다 놓고 Commit.
     (`.nojekyll`, `.gitignore` 처럼 점으로 시작하는 파일은 숨김 파일이라 탐색기에서 보이게 설정한 뒤 함께 올려 주세요.)
   - 터미널에서:
     ```bash
     git init -b main
     git add .
     git commit -m "숙박 안심도 지도"
     git remote add origin https://github.com/<사용자 이름>/anshin-map.git
     git push -u origin main
     ```
3. 저장소 Settings → Pages → Build and deployment 에서
   Source 는 "Deploy from a branch", Branch 는 `main` / `/ (root)` 를 고르고 Save.
4. 1~2분 뒤 `https://<사용자 이름>.github.io/anshin-map/` 에서 지도가 열립니다.
   아이폰·안드로이드 브라우저에서도 같은 주소로 볼 수 있습니다.
5. README.md 맨 위의 "지도 보기" 주소를 실제 주소로 바꿔 주세요.

## 업데이트할 때

`scripts/config.py` 를 고치고 `python3 scripts/score.py && python3 scripts/build_page.py` 를 실행하면
`index.html` 이 새로 만들어집니다. 바뀐 파일을 다시 올리면 Pages 도 자동으로 갱신됩니다.
