# 상품스펙 조회 PWA

유닉스 드라이어·고데기의 상품 간 스펙을 비교하는 웹앱. 폰·PC 홈 화면에 설치해서 쓴다.

## 폴더 구조

```
03)상품스펙 조회\
├ specs_dryer.json      ← Notion 드라이어 스펙 원본 (클론이 갱신)
├ specs_iron.json       ← Notion 고데기 스펙 원본 (클론이 갱신)
├ mockup.html           ← 승인용 목업 (배포와 무관)
└ 상품스펙_PWA\         ← 이 폴더가 GitHub 저장소
   ├ build_data.py      JSON 2개 → index.html 생성 + 검산
   ├ index.html         결과물 (데이터가 이 안에 통째로 들어있다)
   ├ manifest.json / sw.js / icons\
   ├ config.cmd         GitHub 계정·저장소 이름 (깃에 올라가지 않음)
   ├ setup_github.bat   최초 1회만 실행
   ├ update.bat         평상시 업데이트 (바탕화면 아이콘이 이것을 실행)
   └ make_shortcut.bat  바탕화면 바로가기 만들기
```

## 최초 1회 설치

1. GitHub 에서 빈 저장소 `product-spec` 을 만든다 (Public, README 체크 해제).
2. `setup_github.bat` 더블클릭 → 첫 업로드.
3. GitHub 저장소 → Settings → Pages → Branch: `main` / `(root)` → Save.
4. `make_shortcut.bat` 더블클릭 → 바탕화면에 **상품스펙 업데이트** 아이콘 생성.
5. 1~2분 뒤 `https://yim0790.github.io/product-spec/` 접속 → 폰이면 '홈 화면에 추가'.

## 평상시 업데이트 (반자동)

| 순서 | 하는 일 | 누가 |
|---|---|---|
| 1 | Notion 스펙 DB 수정 | 비니 |
| 2 | 세션에서 "스펙 데이터 갱신해줘" → specs_*.json 덮어쓰기 | 클론 |
| 3 | 바탕화면 **상품스펙 업데이트** 더블클릭 | 비니 |
| 4 | 빌드 → 검산 → git push → GitHub Pages 반영 (약 1분) | 자동 |

화면 구성이나 기본 체크 항목을 바꿀 때는 2단계 대신 클론에게 요청한다
(`build_data.py` 상단의 `GROUPS` / `DEFAULT_ON` 수정). 3단계는 동일하다.

## 검산

`build_data.py` 는 매 실행마다 다음을 출력한다. 하나라도 '불일치'가 뜨면 push 전에 확인할 것.

- 대유형별 건수 / 스펙 항목 수 / 그룹 수
- 항목 누락 (그룹 정의에서 빠진 속성이 있는지)
- 모델명 중복
- 전 행이 공백인 항목

## 알아둘 점

- 스펙 데이터는 `index.html` 안에 들어간다. 별도 JSON 을 웹에서 받아오지 않으므로 오프라인에서도 열린다.
- 서비스워커는 HTML 만 네트워크 우선이라, 업데이트하면 앱을 다시 열었을 때 바로 최신이 된다.
- Notion '모델명' 칸에 부가메모가 섞여 있어(예: `UN-A1741 / 에어샷`), 화면에는 모델코드만 쓰고
  원본은 '모델명(원본 표기)' 항목에 그대로 보존한다. 검색은 양쪽 다 걸린다.
- 프리셋은 브라우저 localStorage 에 저장되므로 기기별로 따로 관리된다.
