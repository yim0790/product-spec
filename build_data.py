# Notion에서 받아둔 스펙 JSON을 읽어 상품스펙 비교 PWA(index.html)를 재생성하는 빌드 스크립트
# -*- coding: utf-8 -*-
"""
사용법:
  python build_data.py           → 전체 데이터로 index.html 생성 (update.bat 이 호출)
  python build_data.py --mock    → 샘플 데이터로 ../mockup.html 생성 (승인용 목업)

원본 JSON 경로는 이 파일 안에서 관리한다(배치파일에 한글 경로를 넣으면 cmd 가 깨진다).
"""

import sys, os, re, json, datetime

HERE     = os.path.dirname(os.path.abspath(__file__))
SRC_DIR  = os.path.abspath(os.path.join(HERE, ".."))          # 03)상품스펙 조회
SRC = {
    "dryer": os.path.join(SRC_DIR, "specs_dryer.json"),
    "iron":  os.path.join(SRC_DIR, "specs_iron.json"),
}
OUT_HTML = os.path.join(HERE, "index.html")
MOCK_HTML = os.path.join(SRC_DIR, "mockup.html")
TITLE = "상품스펙 조회"

# ── 제품 이미지 ──────────────────────────────────────────────────────
# 원본은 작업폴더의 '상품이미지' 에 두고, 빌드할 때 가로 600px WEBP 로 줄여
# 저장소의 img\ 로 복사한다. 원본은 건드리지 않는다.
IMG_SRC  = os.path.join(SRC_DIR, "상품이미지")
IMG_OUT  = os.path.join(HERE, "img")
IMG_MAXW = 600
IMG_EXT  = (".jpg", ".jpeg", ".png", ".webp", ".gif")
# 파일명 앞에 붙는 브랜드/시리즈 접두어 (매칭할 때 떼어낸다)
FILE_PREFIX_RE = re.compile(r"^(UN|UCI|HHD|PW|UB|UNL|UNS|UNT)-", re.I)
MODEL_PREFIX_RE = re.compile(r"^(UN|UCI|HHD|PW|UB)-", re.I)

# ── 모델명 표시 규칙 ─────────────────────────────────────────────────
# Notion '모델명' 셀에 모델코드와 부가메모(에어샷/라이카/입고완료 등)가 섞여 들어있다.
# 화면 표시용으로 모델코드를 뽑아 쓰되, 원본 표기는 아래 항목으로 그대로 보존한다.
RAW     = "모델명(원본 표기)"
CODE_RE = re.compile(r"(?:UN|UCI)-[A-Za-z0-9]+", re.I)


def split_name(raw):
    """(표시용 모델코드, 나머지 메모) 로 나눈다. 코드가 없으면 첫 줄을 코드로 본다."""
    raw = str(raw).strip()
    m = CODE_RE.search(raw)
    if m:
        code = m.group(0)
        rest = (raw[:m.start()] + " " + raw[m.end():])
    else:
        parts = raw.split("\n")
        code, rest = parts[0].strip(), " ".join(parts[1:])
    note = " ".join(rest.split())
    return code, note


def name_map(rows):
    """모델코드가 겹치면 메모 일부를 괄호로 덧붙여 유일한 이름을 만든다."""
    tmp = [split_name(r["모델명"]) for r in rows]
    dup = {c for c in [t[0] for t in tmp] if [t[0] for t in tmp].count(c) > 1}
    out, seen = [], {}
    for code, note in tmp:
        name = code
        if code in dup:
            # 괄호를 걷어내고 앞의 두 단어만 꼬리표로 쓴다 (예: UN-D1970 · KELI 모터)
            tag = " ".join(re.sub(r"[()]", " ", note).split()[:2])
            name = f"{code} · {tag}" if tag else code
        if name in seen:                      # 그래도 겹치면 번호를 붙여 반드시 유일하게
            seen[name] += 1
            name = f"{name} #{seen[name]}"
        else:
            seen[name] = 1
        out.append(name)
    return out


def _fcore(fname):
    """이미지 파일명에서 모델코드만 뽑는다. 'UN-1880S(SILVER).PNG' → '1880S'"""
    s = os.path.splitext(fname)[0]
    s = re.split(r"[ (_]", s)[0].upper()      # 색상·별칭 꼬리표 제거
    s = FILE_PREFIX_RE.sub("", s)
    return re.sub(r"[^A-Z0-9]", "", s)


def _mcore(code):
    return re.sub(r"[^A-Z0-9]", "", MODEL_PREFIX_RE.sub("", code.upper()))


def scan_images():
    """상품이미지 폴더를 훑어 {모델코드核: [파일명...]} 을 만든다."""
    if not os.path.isdir(IMG_SRC):
        return {}
    out = {}
    for f in sorted(os.listdir(IMG_SRC)):
        if not f.lower().endswith(IMG_EXT):
            continue
        c = _fcore(f)
        if len(c) < 3:          # 코드로 볼 수 없는 이름(예: '에어샷 휴대용케이스')은 건너뛴다
            continue
        out.setdefault(c, []).append(f)
    return out


def match_images(raw_name, fmap):
    """모델명에 적힌 코드(여러 개일 수 있다)로 이미지를 찾는다.
    정확히 일치하는 것을 먼저 쓰고, 없으면 접두가 겹치는 후보가 딱 하나일 때만 쓴다."""
    codes = re.findall(r"(?:UN|UCI)-[A-Za-z0-9]+", raw_name, re.I) \
            or [raw_name.split("\n")[0].strip()]
    cores = [_mcore(c) for c in codes]
    for c in cores:
        if c in fmap:
            return fmap[c], "exact"
    for c in cores:
        cand = [k for k in fmap if k.startswith(c) or c.startswith(k)]
        if len(cand) == 1:
            return fmap[cand[0]], "prefix"
    return [], "none"


def ensure_pillow():
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print("  Pillow 가 없어 자동 설치합니다...")
        os.system(f'"{sys.executable}" -m pip install pillow')
    from PIL import Image  # noqa: F401
    return Image


def make_thumb(Image, src, dst):
    """가로 IMG_MAXW 로 줄여 WEBP 로 저장. 투명배경은 그대로 살린다.
    원본이 더 최신일 때만 다시 만든다."""
    if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
        return False
    im = Image.open(src)
    if im.mode in ("P", "LA"):
        im = im.convert("RGBA")
    elif im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGB")
    if im.width > IMG_MAXW:
        im = im.resize((IMG_MAXW, round(im.height * IMG_MAXW / im.width)), Image.LANCZOS)
    im.save(dst, "WEBP", quality=82, method=4)
    return True


def build_images(data):
    """행마다 이미지를 찾아 썸네일을 만들고 rows[i]['_img'] 에 경로를 넣는다."""
    fmap = scan_images()
    if not fmap:
        print(f"  (상품이미지 폴더가 없어 이미지 없이 만듭니다: {IMG_SRC})")
        for d in data.values():
            for r in d["rows"]:
                r["_img"] = []
        return {"found": 0, "total": 0, "made": 0, "prefix": [], "missing": []}

    Image = ensure_pillow()
    os.makedirs(IMG_OUT, exist_ok=True)
    stat = {"found": 0, "total": 0, "made": 0, "prefix": [], "missing": []}
    keep = set()

    for d in data.values():
        for r in d["rows"]:
            stat["total"] += 1
            files, how = match_images(r[RAW].replace(" / ", "\n"), fmap)
            paths = []
            for f in files:
                name = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.splitext(f)[0]) + ".webp"
                dst = os.path.join(IMG_OUT, name)
                try:
                    if make_thumb(Image, os.path.join(IMG_SRC, f), dst):
                        stat["made"] += 1
                    paths.append("img/" + name)
                    keep.add(name)
                except Exception as e:
                    print(f"  [이미지 실패] {f}: {e}")
            r["_img"] = paths
            if paths:
                stat["found"] += 1
                if how == "prefix":
                    stat["prefix"].append(f"{r['모델명']} ← {files[0]}")
            else:
                stat["missing"].append(r["모델명"])

    # 더 이상 쓰지 않는 썸네일은 저장소에서 지운다
    for f in os.listdir(IMG_OUT):
        if f.endswith(".webp") and f not in keep:
            os.remove(os.path.join(IMG_OUT, f))
    return stat


# ── 대유형 정의 ───────────────────────────────────────────────────────
CATS = [
    {"key": "dryer", "label": "드라이어"},
    {"key": "iron",  "label": "고데기"},
]

# ── 스펙 항목 그룹 (화면 정리용. Notion 속성명과 정확히 일치해야 한다) ──
GROUPS = {
    "dryer": [
        ("기본정보", [RAW, "상품명(자사몰)", "색상 (바디 기준)", "출시년월", "출시일자",
                      "제조국", "제조사", "제조국/제조사", "참고 사항"]),
        ("전기·인증·안전", ["사용전압", "소비전력 (W)", "KC 인증정보", "전자파적합인증필증",
                            "이중 안전장치", "전자파 안심설계"]),
        ("본체·구조", ["무게", "제품사이즈", "코드길이", "모터사양", "팬 타입",
                       "손잡이 (핸들) 일체혈 접이식", "흡입망 탈착 여부", "흡입망 탈착 형식",
                       "흡입망 필터 유무"]),
        ("기능·스위치", ["음이온", "플라즈마", "센서", "T-CARE (온냉풍 자동 전환)", "FIT모드",
                         "냉풍 기능", "메인 스위치  아이콘 표시", "전원 스위치",
                         "풍속 스위치", "풍온 스위치", "쿨 스위치"]),
        ("노즐", ["노즐 구조", "노즐 착탈 형식", "1)노즐타입   2)노즐내경 사이즈  3)노즐무게", "부속품"]),
        ("성능 측정", ["풍속", "풍압", "풍온", "냉풍", "건조속도", "소음계",
                       "노즐 적용  1Cm 풍속최대 풍온 단계별",
                       "노즐 적용  2.54Cm 풍속최대 풍온 단계별",
                       "노즐 적용  10Cm 풍속최대 풍온 단계별",
                       "노즐 적용  10Cm 냉풍 최대",
                       "노즐 적용 가로 세로  저울 5Cm 냉풍최대",
                       "노즐미적용 10cM 최대 (헝겊이용) 시간측정"]),
    ],
    "iron": [
        ("기본정보", [RAW, "상품명(자사몰)", "상품상세명", "색상 (바디 기준)", "출시년월", "출시일자",
                      "제조국", "제조사", "제조국/제조사"]),
        ("전기·인증", ["사용전압", "소비전력 (W)", "KC 인증정보", "전자파적합인증필증"]),
        ("전원·배터리", ["유무선", "배터리", "배터리용량", "충전방식", "충전시간 사용시간",
                         "코드길이", "회전식 코드"]),
        ("발열판", ["발열판사이즈", "발열판 코팅", "발열판 무빙", "온도범위"]),
        ("본체·조작", ["무게", "제품사이즈  lock", "부속품", "기능성", "DISPLAY  형식",
                       "메인 스위치  아이콘 표시", "바디잠금기능", "자동전원차단", "슬립 모드"]),
    ],
}

# ── 처음 화면에서 미리 체크되어 있는 항목 ────────────────────────────
DEFAULT_ON = {
    "dryer": [RAW, "상품명(자사몰)", "색상 (바디 기준)", "출시년월", "제조국",
              "사용전압", "소비전력 (W)",
              "무게", "코드길이", "모터사양", "손잡이 (핸들) 일체혈 접이식", "흡입망 탈착 여부",
              "노즐 착탈 형식", "풍속", "풍압", "풍온", "냉풍", "건조속도", "소음계",
              "노즐 적용  10Cm 풍속최대 풍온 단계별", "음이온", "플라즈마",
              "T-CARE (온냉풍 자동 전환)", "냉풍 기능", "메인 스위치  아이콘 표시",
              "전원 스위치", "풍속 스위치", "풍온 스위치", "쿨 스위치"],
    "iron":  [RAW, "상품명(자사몰)", "색상 (바디 기준)", "출시년월", "제조국", "사용전압",
              "소비전력 (W)", "유무선", "배터리", "충전시간 사용시간", "코드길이",
              "발열판사이즈", "온도범위", "DISPLAY  형식", "메인 스위치  아이콘 표시",
              "바디잠금기능", "자동전원차단", "무게", "제품사이즈  lock", "부속품"],
}


def load():
    """JSON 을 읽어 대유형별 {rows, groups} 로 정리한다. 모델명이 빈 행은 제외."""
    out = {}
    for c in CATS:
        k = c["key"]
        with open(SRC[k], encoding="utf-8") as f:
            rows = json.load(f)

        rows = [r for r in rows if str(r.get("모델명", "")).strip()]
        for r in rows:
            r.pop("이미지", None)
            r.pop("url", None)
        names = name_map(rows)
        for r, nm in zip(rows, names):
            r[RAW] = " / ".join(x.strip() for x in str(r["모델명"]).split("\n") if x.strip())
            r["모델명"] = nm
        rows.sort(key=lambda r: r["모델명"])

        # 그룹 정의에 있는 항목 중 실제 데이터에 존재하는 것만 사용
        have = set()
        for r in rows:
            have |= set(r.keys())
        have.discard("_img")
        groups, used = [], set()
        for gname, items in GROUPS[k]:
            keep = [i for i in items if i in have]
            used |= set(keep)
            if keep:
                groups.append({"g": gname, "items": keep})
        # 그룹 정의에서 빠진 항목이 있으면 '기타'로 모아 절대 누락되지 않게 한다
        rest = sorted(have - used - {"모델명"})
        if rest:
            groups.append({"g": "기타", "items": rest})

        out[k] = {"label": c["label"], "rows": rows, "groups": groups}
    return out


def verify(data):
    """검산: 행수 / 항목 누락 / 전 행 공백 항목을 확인한다."""
    ok = True
    for k, d in data.items():
        keys = set()
        for r in d["rows"]:
            keys |= set(r.keys())
        keys.discard("모델명")
        keys.discard("_img")
        listed = {i for g in d["groups"] for i in g["items"]}
        miss = keys - listed
        blank = sorted(i for i in listed
                       if not any(str(r.get(i, "")).strip() for r in d["rows"]))
        dup = len(d["rows"]) != len({r["모델명"] for r in d["rows"]})
        print(f"  [{d['label']}] {len(d['rows'])}건 / 스펙항목 {len(listed)}개 "
              f"/ 그룹 {len(d['groups'])}개")
        print(f"    항목 누락        : {'없음' if not miss else miss}")
        print(f"    모델명 중복      : {'없음' if not dup else '있음 — 확인 필요'}")
        print(f"    전 행 공백 항목  : {'없음' if not blank else blank}")
        if miss or dup:
            ok = False
    print(f"  [검산] 종합 : {'OK' if ok else '불일치 — 확인 필요'}")
    return ok


def build_html(data, built):
    tpl = HTML_TEMPLATE
    tpl = tpl.replace("__TITLE__", TITLE)
    tpl = tpl.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    tpl = tpl.replace("__DEFAULTON__", json.dumps(DEFAULT_ON, ensure_ascii=False))
    tpl = tpl.replace("__RAW__", RAW)
    tpl = tpl.replace("__BUILD__", built)
    return tpl


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="manifest" href="manifest.json">
<meta name="theme-color" content="#7BC518">
<link rel="icon" type="image/png" sizes="192x192" href="icons/icon-192.png">
<link rel="apple-touch-icon" href="icons/icon-192.png">
<style>
  :root{
    --bg:#f5f1ea; --card:#fff; --line:#e2ddd4; --ink:#26262a; --mut:#7b7469;
    --a:#6aab13; --a2:#5c9410; --warm:#efe4d6; --diff:#fff8e6; --diffline:#e8b93d;
  }
  *{box-sizing:border-box}
  body{margin:0;padding:20px;background:var(--bg);color:var(--ink);
       font-family:'Malgun Gothic','맑은 고딕',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
       font-size:18px}
  .wrap{max-width:1900px;margin:0 auto}
  h1{font-size:30px;margin:0 0 4px}
  .sub{color:var(--mut);font-size:15px}
  /* 제목·1단계 왼쪽 / 사용 안내 오른쪽 세로 패널 */
  .top{display:grid;grid-template-columns:1fr 640px;gap:14px;align-items:stretch}
  .topL{display:flex;flex-direction:column}
  .topL .card{margin-top:14px;margin-bottom:0;flex:1 1 auto}
  .guide{background:var(--card);border:1px solid var(--line);border-radius:11px;
         padding:12px 16px;font-size:13px;color:var(--mut);line-height:1.65}
  .guide h4{margin:0 0 6px;font-size:14px;color:var(--a2)}
  .guide p{margin:0 0 5px}
  .guide p.ps{margin-top:8px;padding-top:8px;border-top:1px dashed var(--line)}
  .guide b{color:var(--ink)}
  .guide i.sw{display:inline-block;width:11px;height:11px;background:var(--diff);
              border:1px solid var(--diffline);border-radius:2px;margin-right:5px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:11px;
        padding:16px 18px;margin-bottom:12px}
  .step{display:flex;align-items:center;gap:10px;margin-bottom:12px}
  .step .no{width:26px;height:26px;border-radius:50%;background:var(--a);color:#fff;
            font-size:14px;font-weight:700;display:flex;align-items:center;justify-content:center;flex:0 0 auto}
  .step .t{font-size:17px;font-weight:700}
  .step .hint{font-size:14px;color:var(--mut);font-weight:400}

  /* 1) 대유형 */
  .cats{display:flex;gap:10px;flex-wrap:wrap}
  .cat{padding:12px 26px;border:1px solid var(--line);background:#fff;border-radius:9px;
       font-size:17px;font-weight:700;cursor:pointer;font-family:inherit;color:var(--ink)}
  .cat .c{font-weight:400;color:var(--mut);font-size:14px;margin-left:7px}
  .cat.on{background:var(--a);border-color:var(--a);color:#fff}
  .cat.on .c{color:rgba(255,255,255,.85)}

  /* 2) 상품 검색 */
  .srch{position:relative;max-width:560px}
  .srch input{width:100%;padding:12px 15px;font-size:17px;border:1px solid var(--line);
              border-radius:9px;outline:none;font-family:inherit;background:#fff}
  .srch input:focus{border-color:var(--a);box-shadow:0 0 0 3px rgba(106,171,19,.15)}
  .srch input:disabled{background:#f3f1ee;color:#aaa}
  .sug{position:absolute;z-index:30;left:0;right:0;top:calc(100% + 4px);background:#fff;
       border:1px solid var(--line);border-radius:9px;max-height:340px;overflow:auto;
       box-shadow:0 8px 22px rgba(0,0,0,.10);display:none}
  .sug.open{display:block}
  .sug div{padding:10px 15px;font-size:17px;cursor:pointer;border-bottom:1px solid #f3f1ee}
  .sug div:last-child{border-bottom:none}
  .sug div:hover,.sug div.act{background:#f4f8ec}
  .sug div.none{color:var(--mut);cursor:default}
  .sug b{color:var(--a2)}
  .chips{display:flex;gap:9px;flex-wrap:wrap;margin-top:12px;min-height:40px;align-items:center}
  .chip{display:inline-flex;align-items:center;gap:9px;background:var(--warm);
        border:1px solid #ddd0bc;border-radius:24px;padding:7px 10px 7px 17px;font-size:15px;font-weight:700}
  .chip button{border:none;background:#cbbba3;color:#fff;width:21px;height:21px;border-radius:50%;
               cursor:pointer;font-size:13px;line-height:1;padding:0;font-family:inherit}
  .chip button:hover{background:#a8968a}
  .chips .ph{font-size:15px;color:var(--mut)}

  /* 3) 스펙 항목 */
  .mini{padding:7px 14px;border:1px solid var(--line);background:#fff;border-radius:8px;
        font-size:15px;cursor:pointer;font-family:inherit;color:var(--ink)}
  .mini:hover{border-color:var(--a);color:var(--a2)}
  .mini.on{background:var(--a);border-color:var(--a);color:#fff}
  .tools{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-left:auto}
  select.mini{padding:7px 10px}
  /* 그룹 카드는 개수만큼 한 줄에 나란히 놓는다(--gcols 는 JS 가 넣는다) */
  .grps{display:grid;grid-template-columns:repeat(var(--gcols,6),minmax(0,1fr));gap:9px;margin-top:4px}
  .grp{border:1px solid var(--line);border-radius:9px;padding:9px 10px;background:#fcfbf9;min-width:0}
  .grp h4{margin:0 0 7px;font-size:14px;color:var(--a2);display:flex;justify-content:space-between;
          align-items:center;gap:6px;white-space:nowrap}
  .grp h4 b{overflow:hidden;text-overflow:ellipsis}
  .grp h4 span{font-weight:400;color:var(--mut);font-size:13px;cursor:pointer;flex:0 0 auto}
  .grp h4 span:hover{color:var(--a2)}
  .grp label{display:flex;gap:7px;align-items:flex-start;font-size:13px;padding:3px 0;cursor:pointer;line-height:1.35}
  .grp label.void{color:#b8b2a8}
  .grp input{margin:4px 0 0;width:15px;height:15px;accent-color:var(--a);flex:0 0 auto}

  /* 결과 */
  .rbar{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:10px}
  .rbar .n{font-size:17px;font-weight:700}
  .rbar .n em{font-style:normal;color:var(--a2)}
  /* 엑셀 '틀 고정' 방식: 표 안에서만 스크롤되고 헤더행·첫 열이 그대로 붙어 있는다 */
  .tw{overflow:auto;max-height:72vh;border:1px solid var(--line);border-radius:11px;background:#fff}
  table{border-collapse:separate;border-spacing:0;width:100%;min-width:640px}
  th,td{border-bottom:1px solid var(--line);border-right:1px solid var(--line);
        padding:11px 14px;font-size:16px;vertical-align:top;text-align:left;
        white-space:pre-wrap;word-break:break-word;line-height:1.5}
  th:last-child,td:last-child{border-right:none}
  thead th{position:sticky;top:0;z-index:12;background:#efece6;font-size:15px;
           font-weight:700;white-space:normal;box-shadow:inset 0 -1px 0 var(--line)}
  thead th.mdl{font-size:17px}
  th.k,td.k{position:sticky;left:0;z-index:10;background:#faf8f4;font-weight:700;
            color:var(--mut);min-width:225px;max-width:285px;white-space:normal;font-size:15px;
            box-shadow:inset -1px 0 0 var(--line)}
  thead th.k{z-index:14;background:#efece6;color:var(--ink);
             box-shadow:inset -1px 0 0 var(--line), inset 0 -1px 0 var(--line)}
  tr.gh td{background:var(--warm);font-weight:700;font-size:15px;color:#6b5c45;padding:7px 14px}
  tr.gh td.k{background:var(--warm);color:#6b5c45}
  /* 차이가 있는 항목이 대다수라, 색은 '값이 같은 항목'에만 칠한다 */
  tr.same td{background:var(--diff)}
  tr.same td.k{background:#fdf3dd;box-shadow:inset 4px 0 0 var(--diffline), inset -1px 0 0 var(--line)}
  td.na{color:#c3bdb3}
  /* 헤더 안 제품 사진 */
  .th-img{position:relative;margin-top:6px;background:#fff;border:1px solid var(--line);
          border-radius:7px;padding:4px;height:96px;display:flex;align-items:center;justify-content:center}
  .th-img img{max-width:100%;max-height:88px;object-fit:contain;cursor:zoom-in;display:block}
  .th-img em{position:absolute;right:4px;bottom:4px;background:rgba(0,0,0,.55);color:#fff;
             font-style:normal;font-size:11px;padding:1px 5px;border-radius:9px}
  .th-img.none{color:#c3bdb3;font-size:12px;font-weight:400;background:#faf8f4}
  /* 사진 크게 보기 */
  .lb{display:none;position:fixed;inset:0;z-index:80;background:rgba(20,18,15,.88);
      align-items:center;justify-content:center}
  .lb.open{display:flex}
  .lb img{max-width:86vw;max-height:82vh;object-fit:contain;background:#fff;border-radius:10px;padding:10px}
  .lb-x{position:absolute;top:14px;right:18px;font-size:24px;line-height:1}
  .lb-nav{position:absolute;top:50%;transform:translateY(-50%);font-size:34px;line-height:1;padding:6px 16px}
  .lb-nav.prev{left:14px} .lb-nav.next{right:14px}
  .lb-x,.lb-nav{background:rgba(255,255,255,.14);color:#fff;border:none;border-radius:9px;
                cursor:pointer;font-family:inherit}
  .lb-x:hover,.lb-nav:hover{background:rgba(255,255,255,.28)}
  .lb-cap{position:absolute;bottom:18px;left:0;right:0;text-align:center;color:#fff;font-size:15px}
  tbody tr:last-child td{border-bottom:none}
  .msg{padding:44px 16px;text-align:center;color:var(--mut);font-size:17px;line-height:1.8}
  #off{display:none;background:#fdf3dd;border:1px solid var(--diffline);color:#7a5c14;
       border-radius:8px;padding:10px 14px;font-size:15px;margin-bottom:12px}
  @media (max-width:1300px){
    .grps{grid-template-columns:repeat(3,minmax(0,1fr))}
    .top{grid-template-columns:1fr}
    .topL .card{flex:0 0 auto}
  }
  @media (max-width:760px){
    body{padding:12px;font-size:15px}
    h1{font-size:24px}
    .grps{grid-template-columns:1fr}
    .guide{font-size:12px;padding:9px 12px}
    .tools{margin-left:0;width:100%}
    .tw{max-height:70vh}
    /* 폰에서는 표 최소폭을 풀어 값이 화면 안에 들어오게 한다.
       상품이 2개 이상일 때만 모델 열 최소폭 때문에 가로 스크롤이 생긴다. */
    table{min-width:0}
    th.k,td.k{min-width:98px;max-width:98px;font-size:13px;padding:8px 7px}
    thead th.mdl{min-width:145px}
    th,td{font-size:14px;padding:8px 9px}
    .th-img{height:74px;margin-top:5px}
    .th-img img{max-height:66px}
    .lb img{max-width:94vw;padding:6px}
    .lb-nav{font-size:28px;padding:4px 12px}
  }
</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <div class="topL">
      <h1>__TITLE__</h1>
      <div class="sub">유닉스 제품 스펙 비교 &middot; 갱신 __BUILD__ &middot; 출처 Notion '유닉스 제품 스펙 현황'</div>
      <div id="off">오프라인 상태입니다. 마지막으로 열었던 내용이라 최신이 아닐 수 있습니다.</div>
      <div class="card">
        <div class="step"><span class="no">1</span><span class="t">대유형 선택</span></div>
        <div class="cats" id="cats"></div>
      </div>
    </div>

    <div class="guide">
      <h4>사용 안내</h4>
      <p>모델명 <b>부분일치</b> 검색 &middot; 최소 1개 ~ 최대 <b>5개</b> 비교</p>
      <p><i class="sw"></i>노란 줄 = 값이 <b>모두 같은</b> 항목 &nbsp;/&nbsp; 흰 줄 = 값이 <b>다른</b> 항목</p>
      <p><b>[차이나는 항목만 보기]</b> = 노란 줄을 숨겨 차이만 봅니다 &middot; 값이 없으면 <b>—</b></p>
      <p><b>[사진 보기]</b> = 모델명 아래 제품 사진 &middot; 사진을 누르면 크게 열립니다</p>
      <p class="ps"><b>프리셋</b> — 자주 보는 스펙 항목 조합을 저장해 두고 꺼내 쓰는 기능입니다.<br>
        ① 항목을 체크한 뒤 <b>[현재 조합 저장]</b> → 이름 입력 (예: 기본세트)<br>
        ② 다음부터는 <b>[프리셋 불러오기]</b>에서 이름만 고르면 그 조합으로 바뀝니다<br>
        ③ 지울 때는 목록에서 고른 뒤 <b>[프리셋 삭제]</b><br>
        드라이어 &middot; 고데기 각각 따로 저장되며, <b>이 브라우저(기기)</b>에만 남습니다</p>
    </div>
  </div>

  <div class="card">
    <div class="step"><span class="no">2</span><span class="t">비교 상품 선택</span>
      <span class="hint">부분일치 검색 · 최소 1개 ~ 최대 5개</span></div>
    <div class="srch">
      <input type="text" id="q" placeholder="모델명 일부 입력 (예: 7300, 에어샷, A19)" autocomplete="off">
      <div class="sug" id="sug"></div>
    </div>
    <div class="chips" id="chips"></div>
  </div>

  <div class="card">
    <div class="step"><span class="no">3</span><span class="t">조회 스펙 항목 선택</span>
      <span class="hint" id="selCnt"></span>
      <div class="tools">
        <button class="mini" id="bAll">전체선택</button>
        <button class="mini" id="bNone">전체해제</button>
        <button class="mini" id="bDef">기본값</button>
        <select class="mini" id="presetSel"><option value="">프리셋 불러오기</option></select>
        <button class="mini" id="bSave">현재 조합 저장</button>
        <button class="mini" id="bDel">프리셋 삭제</button>
      </div>
    </div>
    <div class="grps" id="grps"></div>
  </div>

  <div class="rbar">
    <span class="n">비교표 <em id="rn">0</em>개 상품</span>
    <div class="tools">
      <button class="mini on" id="bImg">사진 보기</button>
      <button class="mini" id="bDiff">차이나는 항목만 보기</button>
      <button class="mini" id="bCsv">CSV 내보내기</button>
    </div>
  </div>
  <div class="tw" id="out"></div>

  <div class="lb" id="lb">
    <button class="lb-x" id="lbX" title="닫기">✕</button>
    <button class="lb-nav prev" id="lbP" title="이전">‹</button>
    <img id="lbImg" alt="">
    <button class="lb-nav next" id="lbN" title="다음">›</button>
    <div class="lb-cap" id="lbCap"></div>
  </div>

</div>

<script>
const DATA = __DATA__;
const DEF  = __DEFAULTON__;
const RAW  = "__RAW__";
const LSK  = 'specviewer.presets.v1';
const MAX  = 5;

let cat   = 'dryer';
let picks = [];                 // 선택 모델명
let cols  = {};                 // 대유형별 체크된 항목 Set
let diffOnly = false;
let showImg  = true;
let sugIdx = -1;

const esc  = s => String(s==null?'':s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const norm = s => String(s||'').toLowerCase().replace(/\s+/g,'');
const rowOf = m => DATA[cat].rows.find(r => r['모델명'] === m);
const allItems = () => DATA[cat].groups.flatMap(g => g.items);
const isVoid = k => !DATA[cat].rows.some(r => String(r[k]||'').trim());

/* ── 1) 대유형 ───────────────────────────────────────────── */
function drawCats(){
  document.getElementById('cats').innerHTML = Object.keys(DATA).map(k =>
    `<button class="cat${k===cat?' on':''}" data-k="${k}">${DATA[k].label}` +
    `<span class="c">${DATA[k].rows.length}종</span></button>`).join('');
  document.querySelectorAll('.cat').forEach(b => b.onclick = () => {
    if (b.dataset.k === cat) return;
    cat = b.dataset.k; picks = []; closeSug();
    document.getElementById('q').value = '';
    drawCats(); drawGroups(); drawChips(); render();
  });
}

/* ── 2) 검색 / 칩 ────────────────────────────────────────── */
function cands(){
  const q = norm(document.getElementById('q').value);
  if (!q) return [];
  // 모델코드뿐 아니라 원본 표기(에어샷·타일리·takeout 등)로도 부분일치 검색된다
  return DATA[cat].rows
           .filter(r => !picks.includes(r['모델명']) &&
                        (norm(r['모델명']) + norm(r[RAW])).includes(q))
           .map(r => r['모델명']).slice(0, 40);
}
function drawSug(){
  const box = document.getElementById('sug');
  const raw = document.getElementById('q').value.trim();
  if (!raw){ closeSug(); return; }
  const list = cands();
  if (picks.length >= MAX){
    box.innerHTML = `<div class="none">최대 ${MAX}개까지 비교할 수 있습니다. 먼저 하나를 빼주세요.</div>`;
  } else if (!list.length){
    box.innerHTML = `<div class="none">'${esc(raw)}' 를 포함하는 모델이 없습니다.</div>`;
  } else {
    box.innerHTML = list.map((m,i) => {
      // 원문에서 그대로 찾을 수 있을 때만 강조한다(공백 무시 매칭은 위치가 어긋날 수 있음)
      const p = m.toLowerCase().indexOf(raw.toLowerCase());
      const disp = p < 0 ? esc(m)
        : esc(m.slice(0,p)) + '<b>' + esc(m.slice(p, p+raw.length)) + '</b>' + esc(m.slice(p+raw.length));
      return `<div data-m="${esc(m)}" class="${i===sugIdx?'act':''}">${disp}</div>`;
    }).join('');
    box.querySelectorAll('div[data-m]').forEach(d => d.onclick = () => add(d.dataset.m));
  }
  box.classList.add('open');
}
function closeSug(){ document.getElementById('sug').classList.remove('open'); sugIdx = -1; }
function add(m){
  if (picks.length >= MAX || picks.includes(m)) return;
  picks.push(m);
  document.getElementById('q').value = '';
  closeSug(); drawChips(); render();
}
function drawChips(){
  const el = document.getElementById('chips');
  el.innerHTML = picks.length
    ? picks.map(m => `<span class="chip">${esc(m)}<button data-m="${esc(m)}" title="빼기">✕</button></span>`).join('')
    : `<span class="ph">아직 선택된 상품이 없습니다. 위 칸에 모델명 일부를 입력하세요.</span>`;
  el.querySelectorAll('button').forEach(b => b.onclick = () => {
    picks = picks.filter(x => x !== b.dataset.m); drawChips(); render();
  });
  document.getElementById('q').disabled = picks.length >= MAX;
  document.getElementById('q').placeholder = picks.length >= MAX
    ? `최대 ${MAX}개 선택됨` : '모델명 일부 입력 (예: 7300, 에어샷, A19)';
}

/* ── 3) 스펙 항목 ────────────────────────────────────────── */
function drawGroups(){
  if (!cols[cat]) cols[cat] = new Set(DEF[cat].filter(k => allItems().includes(k)));
  const on = cols[cat];
  const box = document.getElementById('grps');
  box.style.setProperty('--gcols', DATA[cat].groups.length);   // 그룹 수만큼 한 줄에 배치
  box.innerHTML = DATA[cat].groups.map((g, gi) =>
    `<div class="grp"><h4><b>${esc(g.g)}</b><span data-g="${gi}">전체</span></h4>` +
    g.items.map(k =>
      `<label class="${isVoid(k)?'void':''}"><input type="checkbox" data-k="${esc(k)}"` +
      `${on.has(k)?' checked':''}><span>${esc(k)}${isVoid(k)?' (데이터 없음)':''}</span></label>`
    ).join('') + `</div>`).join('');
  document.querySelectorAll('#grps input').forEach(c => c.onchange = () => {
    c.checked ? on.add(c.dataset.k) : on.delete(c.dataset.k);
    countSel(); render();
  });
  document.querySelectorAll('#grps h4 span').forEach(s => s.onclick = () => {
    const items = DATA[cat].groups[+s.dataset.g].items;
    const allOn = items.every(k => on.has(k));
    items.forEach(k => allOn ? on.delete(k) : on.add(k));
    drawGroups(); render();
  });
  countSel();
}
function countSel(){
  document.getElementById('selCnt').textContent =
    `${cols[cat].size} / ${allItems().length}개 선택`;
}
function setAll(mode){
  cols[cat] = new Set(mode==='all' ? allItems()
             : mode==='def' ? DEF[cat].filter(k => allItems().includes(k)) : []);
  drawGroups(); render();
}

/* ── 프리셋 (이 기기 브라우저에만 저장) ──────────────────── */
function presets(){ try { return JSON.parse(localStorage.getItem(LSK)) || {}; } catch(e){ return {}; } }
function savePresets(p){ try { localStorage.setItem(LSK, JSON.stringify(p)); } catch(e){ alert('이 브라우저에서는 저장이 제한되어 있습니다.'); } }
function drawPresets(){
  const p = presets()[cat] || {};
  document.getElementById('presetSel').innerHTML =
    '<option value="">프리셋 불러오기</option>' +
    Object.keys(p).map(n => `<option value="${esc(n)}">${esc(n)}</option>`).join('');
}

/* ── 비교표 ──────────────────────────────────────────────── */
function visibleRows(){
  const on = cols[cat], rows = picks.map(rowOf);
  const out = [];
  DATA[cat].groups.forEach(g => {
    const items = g.items.filter(k => {
      if (!on.has(k)) return false;
      if (diffOnly && rows.length > 1){
        const vals = rows.map(r => String(r[k]||'').trim());
        if (vals.every(v => v === vals[0])) return false;
      }
      return true;
    });
    if (items.length) out.push({ g: g.g, items });
  });
  return out;
}
function render(){
  document.getElementById('rn').textContent = picks.length;
  document.getElementById('bDiff').classList.toggle('on', diffOnly);
  document.getElementById('bImg').classList.toggle('on', showImg);
  const box = document.getElementById('out');

  if (!picks.length){
    box.innerHTML = `<div class="msg">비교할 상품을 <b>1개 이상</b> 선택하면 표가 나타납니다.<br>` +
                    `2단계 검색창에 모델명 일부를 입력해 보세요.</div>`;
    return;
  }
  if (!cols[cat].size){
    box.innerHTML = `<div class="msg">조회 스펙 항목이 하나도 선택되지 않았습니다.<br>` +
                    `3단계에서 항목을 체크하거나 [기본값]을 눌러주세요.</div>`;
    return;
  }
  const groups = visibleRows();
  if (!groups.length){
    box.innerHTML = `<div class="msg">선택한 항목에서 <b>상품 간 차이가 없습니다.</b><br>` +
                    `[차이나는 항목만 보기]를 끄면 전체 값을 볼 수 있습니다.</div>`;
    return;
  }
  const rows = picks.map(rowOf);
  const span = picks.length + 1;
  const anyImg = rows.some(r => (r._img || []).length);
  let h = `<table><thead><tr><th class="k">스펙 항목</th>` +
          picks.map((m, i) => {
            const im = rows[i]._img || [];
            let thumb = '';
            if (showImg && anyImg){
              thumb = im.length
                ? `<div class="th-img"><img src="${im[0]}" alt="${esc(m)}" loading="lazy"` +
                  ` data-i="${i}" data-n="0">` +
                  (im.length > 1 ? `<em>+${im.length - 1}</em>` : '') + `</div>`
                : `<div class="th-img none">사진 없음</div>`;
            }
            return `<th class="mdl">${esc(m)}${thumb}</th>`;
          }).join('') + `</tr></thead><tbody>`;
  groups.forEach(g => {
    h += `<tr class="gh"><td class="k">${esc(g.g)}</td>` +
         `<td colspan="${span-1}"></td></tr>`;
    g.items.forEach(k => {
      const vals = rows.map(r => String(r[k]||'').trim());
      const same = vals.length > 1 && vals.every(v => v === vals[0]);
      h += `<tr class="${same?'same':''}"><td class="k">${esc(k)}</td>` +
           vals.map(v => `<td class="${v?'':'na'}">${v?esc(v):'—'}</td>`).join('') + `</tr>`;
    });
  });
  h += `</tbody></table>`;
  box.innerHTML = h;
  box.querySelectorAll('.th-img img').forEach(im =>
    im.onclick = () => openLightbox(+im.dataset.i, +im.dataset.n));
}

/* ── 사진 크게 보기 ──────────────────────────────────────── */
let lbList = [], lbIdx = 0;
function openLightbox(i, n){
  const r = rowOf(picks[i]);
  lbList = (r._img || []).map(src => ({src, name: picks[i]}));
  if (!lbList.length) return;
  lbIdx = n;
  drawLightbox();
  document.getElementById('lb').classList.add('open');
}
function drawLightbox(){
  const it = lbList[lbIdx];
  document.getElementById('lbImg').src = it.src;
  document.getElementById('lbCap').textContent =
    it.name + (lbList.length > 1 ? `  (${lbIdx + 1}/${lbList.length})` : '');
  document.querySelectorAll('.lb-nav').forEach(b =>
    b.style.display = lbList.length > 1 ? 'block' : 'none');
}
function lbMove(d){ lbIdx = (lbIdx + d + lbList.length) % lbList.length; drawLightbox(); }
function closeLightbox(){ document.getElementById('lb').classList.remove('open'); }

/* ── CSV ─────────────────────────────────────────────────── */
function csv(){
  if (!picks.length) { alert('먼저 비교할 상품을 선택해 주세요.'); return; }
  const rows = picks.map(rowOf);
  const q = s => '"' + String(s==null?'':s).replace(/"/g,'""') + '"';
  const lines = [['구분','스펙 항목', ...picks].map(q).join(',')];
  visibleRows().forEach(g => g.items.forEach(k =>
    lines.push([g.g, k, ...rows.map(r => String(r[k]||''))].map(q).join(','))));
  const blob = new Blob(['﻿' + lines.join('\r\n')], {type:'text/csv;charset=utf-8;'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `상품스펙비교_${DATA[cat].label}_${new Date().toISOString().slice(0,10)}.csv`;
  document.body.appendChild(a); a.click(); a.remove();
}

/* ── 이벤트 ──────────────────────────────────────────────── */
const qEl = document.getElementById('q');
qEl.addEventListener('input', () => { sugIdx = -1; drawSug(); });
qEl.addEventListener('focus', drawSug);
qEl.addEventListener('keydown', e => {
  const list = cands();
  if (e.key === 'ArrowDown'){ sugIdx = Math.min(sugIdx+1, list.length-1); drawSug(); e.preventDefault(); }
  else if (e.key === 'ArrowUp'){ sugIdx = Math.max(sugIdx-1, 0); drawSug(); e.preventDefault(); }
  else if (e.key === 'Enter'){ if (list.length) add(list[sugIdx >= 0 ? sugIdx : 0]); }
  else if (e.key === 'Escape'){ closeSug(); }
});
document.addEventListener('click', e => { if (!e.target.closest('.srch')) closeSug(); });

document.getElementById('bAll').onclick  = () => setAll('all');
document.getElementById('bNone').onclick = () => setAll('none');
document.getElementById('bDef').onclick  = () => setAll('def');
document.getElementById('bDiff').onclick = () => { diffOnly = !diffOnly; render(); };
document.getElementById('bImg').onclick  = () => { showImg = !showImg; render(); };
document.getElementById('lbX').onclick = closeLightbox;
document.getElementById('lbP').onclick = () => lbMove(-1);
document.getElementById('lbN').onclick = () => lbMove(1);
document.getElementById('lb').onclick  = e => { if (e.target.id === 'lb') closeLightbox(); };
document.addEventListener('keydown', e => {
  if (!document.getElementById('lb').classList.contains('open')) return;
  if (e.key === 'Escape') closeLightbox();
  if (e.key === 'ArrowLeft')  lbMove(-1);
  if (e.key === 'ArrowRight') lbMove(1);
});
document.getElementById('bCsv').onclick  = csv;
document.getElementById('bSave').onclick = () => {
  if (!cols[cat].size){ alert('선택된 항목이 없습니다.'); return; }
  const n = (prompt('프리셋 이름을 입력하세요 (예: 기본세트)') || '').trim();
  if (!n) return;
  const p = presets(); p[cat] = p[cat] || {}; p[cat][n] = [...cols[cat]];
  savePresets(p); drawPresets();
  document.getElementById('presetSel').value = n;
};
document.getElementById('bDel').onclick = () => {
  const sel = document.getElementById('presetSel').value;
  if (!sel){ alert('삭제할 프리셋을 목록에서 먼저 고르세요.'); return; }
  if (!confirm(`'${sel}' 프리셋을 삭제할까요?`)) return;
  const p = presets(); delete (p[cat]||{})[sel]; savePresets(p); drawPresets();
};
document.getElementById('presetSel').onchange = e => {
  const n = e.target.value; if (!n) return;
  const saved = (presets()[cat] || {})[n] || [];
  cols[cat] = new Set(saved.filter(k => allItems().includes(k)));
  drawGroups(); render();
};

drawCats(); drawGroups(); drawChips(); drawPresets(); render();

function offBadge(){ document.getElementById('off').style.display = navigator.onLine ? 'none' : 'block'; }
window.addEventListener('online', offBadge);
window.addEventListener('offline', offBadge);
offBadge();

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(() => {}));
}
</script>
</body>
</html>
"""


def main():
    mock = "--mock" in sys.argv
    print("=" * 60)
    print("상품스펙 조회 PWA 빌드" + (" (목업 — 내용은 실제와 동일)" if mock else ""))
    print("=" * 60)

    for k, p in SRC.items():
        if not os.path.exists(p):
            raise SystemExit(f"[중단] 원본 JSON 이 없습니다: {p}")

    print("[1/4] 원본 읽기")
    data = load()

    print("[2/4] 제품 이미지")
    st = build_images(data)
    if st["total"]:
        print(f"  {st['total']}건 중 이미지 있음 {st['found']}건 "
              f"({st['found'] / st['total'] * 100:.0f}%) / 새로 만든 썸네일 {st['made']}장")
        if st["prefix"]:
            print(f"  [확인] 이름이 완전히 같지 않아 추정 매칭한 {len(st['prefix'])}건:")
            for x in st["prefix"]:
                print("        ", x)
        if st["missing"]:
            print(f"  [알림] 사진이 없는 {len(st['missing'])}건: {', '.join(st['missing'])}")

    print("[3/4] 검산")
    verify(data)

    built = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    html = build_html(data, built)
    out = MOCK_HTML if mock else OUT_HTML
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[4/4] 생성 완료: {os.path.basename(out)} ({len(html.encode('utf-8')):,} bytes)")
    if not mock:
        print("완료. 이어서 GitHub 에 업로드합니다.")


if __name__ == "__main__":
    main()
