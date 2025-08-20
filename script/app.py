#!/usr/bin/env python
# coding: utf-8

import streamlit as st
import re

from utils.loaders import (
    load_catalog,           # part_master.csv (category 포함)
    load_images,            # images/<part_type>*.jpg|png
    load_code_schema,       # codeSchema_IK / OK
    load_lookups,           # 7종 lookup dict
    lookup_options,         # lookup 테이블에서 part_type별 옵션 추출
    load_crossmap,          # Cross_Map.csv → ik2ok, ok2ik
    load_matched_full,      # matched_parts.csv (safe csv loader 사용)
)

st.set_page_config(page_title="V/KM-Code Viewer", page_icon="🔎", layout="wide")

# ──────────────────────────────────────────────────────────────────────────────
# 0) 유틸
def _norm(s: str) -> str:
    """공백/하이픈 제거 + 대문자화(코드 비교용)"""
    return re.sub(r"[\s\-]+", "", str(s or "")).upper()

# ──────────────────────────────────────────────────────────────────────────────
# 1) 빠른 검색 상태값
if "pref_cat" not in st.session_state: st.session_state.pref_cat = None
if "pref_pt"  not in st.session_state: st.session_state.pref_pt  = None

st.title("V‑CODE · KM‑CODE 통합 조회 (Demo)")

# 카탈로그 로드
df = load_catalog()

# ──────────────────────────────────────────────────────────────────────────────
# 2) 빠른 검색 (V### 또는 ####/#####)
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

# ──────────────────────────────────────────────────────────────────────────────
# 3) 대분류 → 세부명칭 (IK 우선 / Cross_Map 라벨링)
cats = sorted(df["category"].dropna().unique())
cat_idx = cats.index(st.session_state.pref_cat) if st.session_state.pref_cat in cats else 0
cat = st.selectbox("대분류", cats, index=cat_idx)

df_sub = df[df.category == cat].copy()
if df_sub.empty:
    st.warning("이 대분류에 등록된 품목이 없습니다.")
    st.stop()

# IK 우선 노출(없으면 OK)
is_iksan = df_sub['part_type'].astype(str).str.startswith('V', na=False)
df_ik    = df_sub[is_iksan]
df_show  = df_ik if not df_ik.empty else df_sub[~is_iksan]

ik2ok, ok2ik = load_crossmap()

label_map = {}
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

# 프리필 인덱스
if st.session_state.pref_pt:
    pre = next((k for k,(pt,op) in label_map.items()
                if pt == st.session_state.pref_pt or op == st.session_state.pref_pt), None)
    sel_idx = labels.index(pre) if pre in labels else 0
else:
    sel_idx = 0

sel_label          = st.selectbox("세부명칭", labels, index=sel_idx)
sel_pt, paired_pt  = label_map[sel_label]

# 좌/우에 쓸 IK/OK part_type 확정
ik_pt = sel_pt if sel_pt.startswith("V") else (paired_pt or "")
ok_pt = (paired_pt or "") if sel_pt.startswith("V") else sel_pt

st.caption(f"선택된 Pair  |  IK: {ik_pt or '-'}  /  OK: {ok_pt or '-'}")

# ──────────────────────────────────────────────────────────────────────────────
# 4) 입력 기준 선택 (한쪽만 입력, 다른쪽은 자동 조회)
basis = st.radio(
    "입력 기준을 선택하세요",
    ["익산 코드 입력 → 옥천 자동 조회", "옥천 코드 입력 → 익산 자동 조회"],
    horizontal=True
)
basis_ik = basis.startswith("익산")

# ──────────────────────────────────────────────────────────────────────────────
# 5) 동적 속성 패널 렌더러
def render_attributes(site: str, part_type: str) -> dict:
    """
    스키마(codeSchema_*) + 룩업(7종)을 이용해 해당 part_type의 속성 위젯을 동적으로 생성.
    반환: {attr_name: code_or_text}
    """
    schema  = load_code_schema("IK" if site.upper()=="IK" else "OK")
    lookups = load_lookups()

    rules = schema[schema.part_type == part_type]
    if rules.empty:
        st.info("이 품목에 대한 스키마가 없습니다.")
        return {}

    selected = {}
    for _, r in rules.iterrows():
        attr  = (r.get("attr_name", "") or "attr").strip()
        table = (r.get("lookup_table", "") or "").strip()

        if table and table in lookups:
            opts = lookup_options(lookups, table, part_type)  # {code: label}
            if not opts:
                st.warning(f"{attr} : 옵션 없음")
                continue
            def fmt(c): return f"{c} - {opts.get(c,'')}" if opts.get(c) else c
            sel = st.selectbox(attr, list(opts.keys()), format_func=fmt, key=f"{site}:{part_type}:{attr}")
            selected[attr] = sel
        else:
            sel = st.text_input(attr, key=f"{site}:{part_type}:{attr}")
            selected[attr] = str(sel).strip()

    return selected

# ──────────────────────────────────────────────────────────────────────────────
# 6) 좌/우 패널 (입력쪽만 속성 표시)
ik_selected, ok_selected = {}, {}
left, right = st.columns(2)

with left:
    st.subheader("익산")
    if basis_ik and ik_pt:
        ik_selected = render_attributes("IK", ik_pt)
        st.caption(f"part_type: {ik_pt}")
    else:
        st.caption(f"part_type: {ik_pt or '-'} (자동 조회 대상)")

with right:
    st.subheader("옥천")
    if (not basis_ik) and ok_pt:
        ok_selected = render_attributes("OK", ok_pt)
        st.caption(f"part_type: {ok_pt}")
    else:
        st.caption(f"part_type: {ok_pt or '-'} (자동 조회 대상)")

# ──────────────────────────────────────────────────────────────────────────────
# 7) 조회: 스키마 기반 동적 조립 → matched_parts 조회(있으면) → 항상 좌/우 결과 표시
st.divider()
if st.button("조회"):
    mdf = load_matched_full().copy()

    # IK/OK 코드 컬럼 자동 탐지 + 정규화 컬럼
    ik_col = next((c for c in mdf.columns if "ik" in c.lower() and "code" in c.lower()),
                  mdf.columns[0])
    ok_col = next((c for c in mdf.columns if ("ok" in c.lower() and "code" in c.lower()) or "km" in c.lower()),
                  mdf.columns[1] if mdf.shape[1] > 1 else mdf.columns[0])
    mdf["__ik_norm"] = mdf[ik_col].map(_norm)
    mdf["__ok_norm"] = mdf[ok_col].map(_norm)

    # ─ 헬퍼: 스키마 순서대로(현재 렌더된 키만) 연결
    def assemble_by_schema(site:str, pt:str, selected:dict) -> str | None:
        schema = load_code_schema(site.upper())
        rules  = schema[schema.part_type == pt]
        if rules.empty or not selected:
            return None
        segs = []
        for _, r in rules.iterrows():
            attr = (r.get("attr_name","") or "").strip()
            if not attr or attr not in selected:
                continue
            v = str(selected.get(attr,"")).strip()
            if not v:
                continue
            # 필요하면 여기서 길이 패딩 규칙(r.get("pad_len")) 등을 적용
            segs.append(v)
        return f"{pt}{''.join(segs)}" if segs else None

    ik_code, ok_code = None, None

    if basis_ik:
        # ─ 익산 입력 기준
        if not ik_pt:
            st.error("익산 part_type 없음"); st.stop()

        # 현재 렌더된 키 중 값이 비어있으면 '경고'만, 조립은 가능한 만큼
        missing = [k for k,v in (ik_selected or {}).items() if not str(v).strip()]
        if missing:
            st.warning("익산 입력값 누락: " + ", ".join(missing))

        ik_code = assemble_by_schema("IK", ik_pt, ik_selected)
        if ik_code:
            st.success(f"IK 코드: `{ik_code}`")
            hit = mdf[mdf["__ik_norm"] == _norm(ik_code)]
        else:
            # 11자리 조립 불가 → part_type 기준 매칭 시도
            hit = mdf[(mdf["__ik_norm"] == _norm(ik_pt)) | (mdf[ik_col] == ik_pt)]

        if hit.empty:
            # 11자리 매칭 실패여도 OK는 반드시 보여준다(페어 part_type)
            ok_pair = load_crossmap()[0].get(ik_pt, ok_pt or "")
            if ok_pair:
                st.success(f"OK 결과(페어 part_type): `{ok_pair}`")
                ok_code = ok_pair
            else:
                st.info("OK 결과를 찾지 못했습니다.")
        else:
            ok_code = hit.iloc[0][ok_col]
            st.success(f"OK 결과: `{ok_code}`")

    else:
        # ─ 옥천 입력 기준
        if not ok_pt:
            st.error("옥천 part_type 없음"); st.stop()

        missing = [k for k,v in (ok_selected or {}).items() if not str(v).strip()]
        if missing:
            st.warning("옥천 입력값 누락: " + ", ".join(missing))

        ok_code = assemble_by_schema("OK", ok_pt, ok_selected)
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

    # ─ 이미지 (part_type 기준 썸네일)
    imgL, imgR = st.columns(2)
    with imgL:
        st.subheader("익산 이미지")
        imgs = load_images(ik_pt) if ik_pt else []
        st.image(imgs, width=260) if imgs else st.info("이미지 없음")
    with imgR:
        st.subheader("옥천 이미지")
        imgs2 = load_images(ok_pt) if ok_pt else []
        st.image(imgs2, width=260) if imgs2 else st.info("이미지 없음")
