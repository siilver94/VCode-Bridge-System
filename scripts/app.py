#!/usr/bin/env python
# coding: utf-8
"""
V/KM-Code 통합 조회 Demo (최종 안정판)
- 카테고리 → 세부명칭(파트타입) 선택
- 한쪽(IK/OK) 속성만 입력 → 스키마 순서대로 11자리 코드 조립(자리수 자동 0-패딩)
- matched_parts.csv 로 상대 코드 조회(없으면 Cross_Map으로 part_type 페어 fallback)
- 좌/우(익산/옥천) 이미지 가로 출력
"""

import re
import streamlit as st

# 프로젝트용 로더/헬퍼 (utils/loaders.py에 구현되어 있다고 가정)
from utils.loaders import (
    load_catalog,           # part_master.csv (+category)
    load_images,            # images/<part_type>*.{jpg,png}
    load_code_schema,       # codeSchema_IK.csv / codeSchema_OK.csv
    load_lookups,           # 7종 lookup dict
    lookup_options,         # lookup 테이블에서 part_type별 옵션 dict 추출
    load_crossmap,          # Cross_Map.csv → (ik2ok, ok2ik)
    load_matched_full,      # matched_parts.csv (안전 로더)
)

# ---------------------------------------------------------------------
# 기본 페이지 설정 (wide + 제목/아이콘)
# ---------------------------------------------------------------------
st.set_page_config(page_title="V/KM-Code Viewer", page_icon="🔎", layout="wide")
st.title("V‑CODE · KM‑CODE 통합 조회 (Demo)")

# ---------------------------------------------------------------------
# 0) 공통 유틸
# ---------------------------------------------------------------------
def _norm(s: str) -> str:
    """코드 비교용 정규화: 공백/하이픈 제거 + 대문자화"""
    return re.sub(r"[\s\-]+", "", str(s or "")).upper()

def _attr_width_from_schema(site: str, part_type: str, attr_name: str):
    """
    스키마(codeSchema_{IK/OK}.csv)에서 해당 속성의 자리수 길이를 계산.
    길이 = pos_to - pos_from + 1
    """
    schema = load_code_schema(site.upper())
    r = schema[(schema.part_type == part_type) & (schema.attr_name == attr_name)]
    if r.empty:
        return None
    try:
        pf = int(r.iloc[0]["pos_from"])
        pt = int(r.iloc[0]["pos_to"])
        return max(1, pt - pf + 1)
    except Exception:
        return None

def normalize_selected_by_schema(site: str, part_type: str, selected: dict) -> dict:
    """
    사용자가 입력/선택한 속성 dict({attr: value})를
    스키마에 정의된 자리수 길이에 맞춰 '0'으로 왼쪽 패딩.
    - 혼합문자(예: 'A1')도 문자열 기준으로 패딩 (스키마는 자릿수만 보장)
    """
    if not selected:
        return {}
    out = {}
    for k, v in selected.items():
        s = str(v).strip()
        width = _attr_width_from_schema(site, part_type, k)
        if width and s:
            s = s.zfill(width)  # ← 핵심: 자리수 자동 0-패딩
        out[k] = s
    return out

def assemble_by_schema(site: str, part_type: str, selected: dict) -> str or None:
    """
    스키마 순서대로(현재 선택/입력된 키만) 세그먼트를 이어 붙여 11자리 코드 생성.
    - selected는 normalize_selected_by_schema()를 거친 값 사용 권장(자리수 보장)
    - 반환: 완성된 'part_type + 세그먼트' 또는 None
    """
    schema = load_code_schema(site.upper())
    rules  = schema[schema.part_type == part_type]
    if rules.empty or not selected:
        return None

    segs = []
    for _, r in rules.iterrows():
        attr = (r.get("attr_name", "") or "").strip()
        if not attr or attr not in selected:
            continue
        val = str(selected.get(attr, "")).strip()
        if not val:
            continue
        segs.append(val)

    return f"{part_type}{''.join(segs)}" if segs else None

# ---------------------------------------------------------------------
# 1) 빠른 검색 상태 보관 (카테고리/파트타입 프리필)
# ---------------------------------------------------------------------
if "pref_cat" not in st.session_state:
    st.session_state.pref_cat = None
if "pref_pt" not in st.session_state:
    st.session_state.pref_pt = None

# 카탈로그 로드 (site/category/part_type/remark 등)
df = load_catalog()

# ---------------------------------------------------------------------
# 2) 빠른 검색 (V*** 또는 ####/#####)
# ---------------------------------------------------------------------
with st.expander("🔎 빠른 검색 (V*** 또는 KM 4~5자리)"):
    q = st.text_input("품명코드(Part Type) 검색", placeholder="예: V111 또는 2655")
    if st.button("찾기", use_container_width=False):
        s = (q or "").strip().upper()
        if re.fullmatch(r"V\d{3}", s) or re.fullmatch(r"\d{4,5}", s):
            hit = df[df.part_type == s]
            if hit.empty:
                st.warning("해당 Part Type이 part_master에 없습니다.")
            else:
                st.session_state.pref_pt  = s
                st.session_state.pref_cat = hit.iloc[0]["category"]
                st.success(f"선택 이동: {s}")
        else:
            st.error("형식이 올바르지 않습니다. V### 또는 ####/#####")

# ---------------------------------------------------------------------
# 3) 대분류 → 세부명칭 (IK 우선 / Cross_Map 라벨 표시)
# ---------------------------------------------------------------------
cats = sorted(df["category"].dropna().unique())
cat_idx = cats.index(st.session_state.pref_cat) if st.session_state.pref_cat in cats else 0
cat = st.selectbox("대분류", cats, index=cat_idx)

df_sub = df[df.category == cat].copy()
if df_sub.empty:
    st.warning("이 대분류에 등록된 품목이 없습니다.")
    st.stop()

# IK 우선 노출 (없으면 OK만)
is_iksan = df_sub["part_type"].astype(str).str.startswith("V", na=False)
df_ik    = df_sub[is_iksan]
df_show  = df_ik if not df_ik.empty else df_sub[~is_iksan]

# Cross_Map을 라벨링에 활용 (V111 ↔ 2655 형태)
ik2ok, ok2ik = load_crossmap()

label_map = {}  # "라벨" → (sel_pt, paired_pt)
for _, r in df_show.iterrows():
    pt = str(r.part_type)
    if pt.startswith("V"):
        paired   = ik2ok.get(pt, "")
        pair_txt = f"{pt} ↔ {paired}" if paired else pt
    else:
        paired   = ok2ik.get(pt, "")
        pair_txt = f"{paired} ↔ {pt}" if paired else pt
    label_map[f"{r.remark} ({pair_txt})"] = (pt, paired)

labels = list(label_map.keys())
if not labels:
    st.error("선택 가능한 세부명칭이 없습니다.")
    st.stop()

# 빠른검색 프리필 인덱스 처리
if st.session_state.pref_pt:
    pre = next(
        (k for k, (pt, op) in label_map.items()
         if pt == st.session_state.pref_pt or op == st.session_state.pref_pt),
        None
    )
    sel_idx = labels.index(pre) if pre in labels else 0
else:
    sel_idx = 0

sel_label         = st.selectbox("세부명칭", labels, index=sel_idx)
sel_pt, paired_pt = label_map[sel_label]

# 좌/우 패널에 고정할 IK/OK part_type 확정
ik_pt = sel_pt if sel_pt.startswith("V") else (paired_pt or "")
ok_pt = (paired_pt or "") if sel_pt.startswith("V") else sel_pt

st.caption(f"선택된 Pair  |  IK: {ik_pt or '-'}  /  OK: {ok_pt or '-'}")

# ---------------------------------------------------------------------
# 4) 입력 기준 선택 (한쪽만 입력, 다른쪽은 자동 조회)
# ---------------------------------------------------------------------
basis = st.radio(
    "입력 기준을 선택하세요",
    ["익산 코드 입력 → 옥천 자동 조회", "옥천 코드 입력 → 익산 자동 조회"],
    horizontal=True,
)
basis_ik = basis.startswith("익산")  # True: IK가 입력측, False: OK가 입력측

# ---------------------------------------------------------------------
# 5) 동적 속성 패널 렌더러
# - 스키마 + 룩업 기반으로 해당 part_type의 속성 위젯을 자동 생성
# ---------------------------------------------------------------------
def render_attributes(site: str, part_type: str) -> dict:
    """
    반환: {attr_name: 선택/입력된 코드값(문자열)}
    - 룩업 테이블이 있으면 selectbox(코드-라벨 포맷)
    - 룩업이 없으면 자유 입력(text_input)
    """
    schema  = load_code_schema("IK" if site.upper() == "IK" else "OK")
    lookups = load_lookups()
    rules   = schema[schema.part_type == part_type]

    if rules.empty:
        st.info("이 품목에 대한 스키마가 없습니다.")
        return {}

    selected = {}
    for _, r in rules.iterrows():
        attr  = (r.get("attr_name", "") or "attr").strip()
        table = (r.get("lookup_table", "") or "").strip()

        # 룩업 기반 selectbox
        if table and table in lookups:
            opts = lookup_options(lookups, table, part_type)  # {code: label}
            if not opts:
                st.warning(f"{attr} : 옵션 없음")
                continue

            def _fmt(c):
                return f"{c} - {opts.get(c, '')}" if opts.get(c) else c

            sel = st.selectbox(attr, list(opts.keys()), format_func=_fmt,
                               key=f"{site}:{part_type}:{attr}")
            selected[attr] = sel

        # 자유 입력
        else:
            sel = st.text_input(attr, key=f"{site}:{part_type}:{attr}")
            selected[attr] = str(sel).strip()

    return selected

# ---------------------------------------------------------------------
# 6) 좌/우 패널 (입력쪽만 속성 표시, 반대쪽은 '자동 조회 대상' 표시)
# ---------------------------------------------------------------------
ik_selected, ok_selected = {}, {}
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("익산")
    if basis_ik and ik_pt:
        ik_selected = render_attributes("IK", ik_pt)
        st.caption(f"part_type: {ik_pt}")
    else:
        st.caption(f"part_type: {ik_pt or '-'} (자동 조회 대상)")

with col_right:
    st.subheader("옥천")
    if (not basis_ik) and ok_pt:
        ok_selected = render_attributes("OK", ok_pt)
        st.caption(f"part_type: {ok_pt}")
    else:
        st.caption(f"part_type: {ok_pt or '-'} (자동 조회 대상)")

# ---------------------------------------------------------------------
# 7) 조회: 스키마 기반 동적 조립 → matched_parts 조회(있으면) → 항상 좌/우 결과 표시
# ---------------------------------------------------------------------
st.divider()
if st.button("조회"):
    # matched_parts 로드 및 코드 컬럼 정규화 준비
    mdf = load_matched_full().copy()
    ik_col = next((c for c in mdf.columns if "ik" in c.lower() and "code" in c.lower()),
                  mdf.columns[0])
    ok_col = next((c for c in mdf.columns if ("ok" in c.lower() and "code" in c.lower())
                   or "km" in c.lower()),
                  mdf.columns[1] if mdf.shape[1] > 1 else mdf.columns[0])
    mdf["__ik_norm"] = mdf[ik_col].map(_norm)
    mdf["__ok_norm"] = mdf[ok_col].map(_norm)

    ik_code, ok_code = None, None

    # ─────────────────────────────────────────────────
    # (A) 익산 기준 입력 → IK 11자리 조립 → matched_parts로 OK 조회
    # ─────────────────────────────────────────────────
    if basis_ik:
        if not ik_pt:
            st.error("익산 part_type 없음")
            st.stop()

        # 미입력 항목 경고(조립은 가능한 만큼 진행)
        missing = [k for k, v in (ik_selected or {}).items() if not str(v).strip()]
        if missing:
            st.warning("익산 입력값 누락: " + ", ".join(missing))

        # 1) 자리수 자동 패딩
        ik_selected_norm = normalize_selected_by_schema("IK", ik_pt, ik_selected)
        # 2) 스키마 순서대로 조립
        ik_code = assemble_by_schema("IK", ik_pt, ik_selected_norm)

        # 3) matched_parts에서 상대(OK) 코드 조회 (없으면 part_type 매핑 fallback)
        if ik_code:
            st.success(f"IK 코드: `{ik_code}`")
            hit = mdf[mdf["__ik_norm"] == _norm(ik_code)]
        else:
            # 11자리 조립 불가 시: part_type 수준으로 매칭 시도
            hit = mdf[(mdf["__ik_norm"] == _norm(ik_pt)) | (mdf[ik_col] == ik_pt)]

        if hit.empty:
            # matched_parts에 정합쌍이 없을 때는 Cross_Map 페어 part_type로라도 안내
            ok_pair = load_crossmap()[0].get(ik_pt, ok_pt or "")
            if ok_pair:
                st.success(f"OK 결과(페어 part_type): `{ok_pair}`")
                ok_code = ok_pair
            else:
                st.info("OK 결과를 찾지 못했습니다.")
        else:
            ok_code = hit.iloc[0][ok_col]
            st.success(f"OK 결과: `{ok_code}`")

    # ─────────────────────────────────────────────────
    # (B) 옥천 기준 입력 → OK 11자리 조립 → matched_parts로 IK 조회
    # ─────────────────────────────────────────────────
    else:
        if not ok_pt:
            st.error("옥천 part_type 없음")
            st.stop()

        missing = [k for k, v in (ok_selected or {}).items() if not str(v).strip()]
        if missing:
            st.warning("옥천 입력값 누락: " + ", ".join(missing))

        ok_selected_norm = normalize_selected_by_schema("OK", ok_pt, ok_selected)
        ok_code = assemble_by_schema("OK", ok_pt, ok_selected_norm)

        if ok_code:
            st.success(f"OK 코드: `{ok_code}`")
            hit = mdf[mdf["__ok_norm"] == _norm(ok_code)]
        else:
            hit = mdf[(mdf["__ok_norm"] == _norm(ok_pt)) | (mdf[ok_col] == ok_pt)]

        if hit.empty:
            ik_pair = load_crossmap()[1].get(ok_pt, ik_pt or "")
            if ik_pair:
                st.success(f"IK 결과(페어 part_type): `{ik_pair}`")
                ik_code = ik_pair
            else:
                st.info("IK 결과를 찾지 못했습니다.")
        else:
            ik_code = hit.iloc[0][ik_col]
            st.success(f"IK 결과: `{ik_code}`")

# ---------------------------------------------------------------------
# 8) 이미지 출력 (좌=IK / 우=OK, 가로 배치, use_container_width 사용)
# ---------------------------------------------------------------------
st.divider()
col_l, col_r = st.columns(2)

with col_l:
    st.subheader("익산 이미지")
    if ik_pt:
        imgs = load_images(ik_pt)
        if imgs:
            # deprecated 경고 없는 파라미터 (열 너비 맞춤)
            st.image(imgs[:2], use_container_width=True)
        else:
            st.info("이미지 없음")
    else:
        st.info("IK part_type 미선택")

with col_r:
    st.subheader("옥천 이미지")
    if ok_pt:
        imgs2 = load_images(ok_pt)
        if imgs2:
            st.image(imgs2[:2], use_container_width=True)
        else:
            st.info("이미지 없음")
    else:
        st.info("OK part_type 미선택")
