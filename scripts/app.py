#!/usr/bin/env python
# coding: utf-8
"""
V/KM-Code 통합 조회 Demo (union_schema + vcode_codec 통합 확장판)
- 카테고리 → 세부명칭(파트타입) 선택
- 기준 측(IK/OK)을 고르면: 기준 필수 + 상대측 부족분만 입력 UI 자동 생성
- 입력 한 번 → IK/OK 11자리 동시에 생성 (encode_both)
- matched_parts.csv 있으면 결과 확인/보강
- 좌/우(익산/옥천) 이미지 가로 출력
"""

import re
import streamlit as st

# 프로젝트용 로더/헬퍼
from utils.loaders import (
    load_catalog,           # part_master.csv (+category)
    load_images,            # images/<part_type>*.{jpg,png}
    load_code_schema,       # codeSchema_IK.csv / codeSchema_OK.csv (참고: 일부 util에서만 사용)
    load_lookups,           # 7종 lookup dict
    lookup_options,         # lookup 테이블에서 part_type별 옵션 dict 추출 {code: label}
    load_crossmap,          # Cross_Map.csv → (ik2ok, ok2ik)
    load_matched_full,      # matched_parts.csv (안전 로더)
    load_union_schema,      # union_schema.csv 로더
)

# vcode_codec (11자리 조립/해석기)
from notebooks.vcode_codec import (
    encode_both, required_keys, extra_keys_from_other_side, missing_required_keys, _slot_to_range,
    decode_attrs_from_code,
)

# ---------------------------------------------------------------------
# 기본 페이지 설정 (wide + 제목/아이콘)
# ---------------------------------------------------------------------
st.set_page_config(page_title="V/KM-Code Viewer", page_icon="🔎", layout="wide")
st.title("V-CODE · KM-CODE 통합 조회 (Demo)")

# ---------------------------------------------------------------------
# 0) 공통 유틸
# ---------------------------------------------------------------------
def _norm(s: str) -> str:
    """코드 비교용 정규화: 공백/하이픈 제거 + 대문자화"""
    return re.sub(r"[\s\-]+", "", str(s or "")).upper()

# (참고 util) 스키마 기반 폭 산출/패딩 — 현재는 직접 사용하지 않지만 호환성 위해 보관
def _attr_width_from_schema(site: str, part_type: str, attr_name: str):
    schema = load_code_schema(site.upper())
    r = schema[(schema.part_type == part_type) & (schema.attr_name == attr_name)]
    if r.empty:
        return None
    try:
        pf = int(r.iloc[0]["pos_from"]); pt = int(r.iloc[0]["pos_to"])
        return max(1, pt - pf + 1)
    except Exception:
        return None

def normalize_selected_by_schema(site: str, part_type: str, selected: dict) -> dict:
    if not selected:
        return {}
    out = {}
    for k, v in selected.items():
        s = str(v).strip()
        width = _attr_width_from_schema(site, part_type, k)
        if width and s:
            s = s.zfill(width)
        out[k] = s
    return out

def assemble_by_schema(site: str, part_type: str, selected: dict) -> str | None:
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
# 1) 상태: 카테고리/파트타입 프리필 + 11자리 프리필 attrs
# ---------------------------------------------------------------------
if "pref_cat" not in st.session_state:
    st.session_state.pref_cat = None
if "pref_pt" not in st.session_state:
    st.session_state.pref_pt = None
# ★ 변경: 11자리 해석으로 얻은 attrs 저장용
if "prefill_attrs" not in st.session_state:
    st.session_state.prefill_attrs = {}
if "__basis_override" not in st.session_state:
    st.session_state.__basis_override = None

# 카탈로그 로드 (site/category/part_type/remark 등)
df = load_catalog()

# ---------------------------------------------------------------------
# 2) 빠른 검색 (V*** / ####/##### / ★ 11자리)
# ---------------------------------------------------------------------
with st.expander("🔎 빠른 검색 (V*** 또는 KM 4~5자리)"):
    q = st.text_input("품명코드(Part Type) 검색", placeholder="예: V111 / 2655 / V111260408")
    if st.button("찾기", use_container_width=False):
        s = (q or "").strip().upper()

        # (A) 11자리 완전코드 → 자동 프리필
        if re.fullmatch(r"[A-Z0-9]{11}", s):
            udf_local = load_union_schema()
            side = "IK" if s.startswith("V") else "OK"
            pair_id, attrs, pt = decode_attrs_from_code(udf_local, side, s)

            # 카탈로그에서 part_type 찾아 화면 이동
            hit = df[df.part_type.astype(str) == pt]
            if hit.empty and side == "OK":
                # OK 5자리 우선이라면 4자리 보정
                hit = df[df.part_type.astype(str) == s[:4]]

            if hit.empty:
                st.warning("카탈로그에서 해당 part_type을 찾지 못했습니다.")
            else:
                st.session_state.pref_pt  = hit.iloc[0]["part_type"]
                st.session_state.pref_cat = hit.iloc[0]["category"]

            # ★ 변경: 프리필 값과 기준방향 세션 저장
            st.session_state.prefill_attrs = {k: ("" if attrs.get(k) is None else str(attrs.get(k))) for k in attrs}
            st.session_state.__basis_override = ("익산 코드 입력 → 옥천 자동 조회" if side=="IK"
                                                 else "옥천 코드 입력 → 익산 자동 조회")

            st.success(f"선택 이동: {pt} (코드 프리필 완료)")
            try:
                st.rerun()
            except Exception:
                st.experimental_rerun()

        # (B) part_type만 검색 (V### 또는 ####/#####)
        elif re.fullmatch(r"V\d{3}", s) or re.fullmatch(r"\d{4,5}", s):
            hit = df[df.part_type == s]
            if hit.empty:
                st.warning("해당 Part Type이 part_master에 없습니다.")
            else:
                st.session_state.pref_pt  = s
                st.session_state.pref_cat = hit.iloc[0]["category"]
                # ★ 변경: 프리필 초기화
                st.session_state.prefill_attrs = {}
                st.session_state.__basis_override = None
                st.success(f"선택 이동: {s}")
        else:
            st.error("형식이 올바르지 않습니다. V### / #### / ##### / 또는 11자리 코드")

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

# Cross_Map 라벨: "V111 ↔ 2655"
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

# 좌/우 part_type 확정
ik_pt = sel_pt if sel_pt.startswith("V") else (paired_pt or "")
ok_pt = (paired_pt or "") if sel_pt.startswith("V") else sel_pt
st.caption(f"선택된 Pair  |  IK: {ik_pt or '-'}  /  OK: {ok_pt or '-'}")

# union 스키마 + pair_id
udf = load_union_schema()
pair_id = f"{ik_pt}_{ok_pt}" if (ik_pt and ok_pt) else None

if pair_id and udf[udf["pair_id"] == pair_id].empty:
    st.warning(f"union_schema에 pair_id '{pair_id}' 행이 없습니다. (빌더 최신화 확인)")

# ---------------------------------------------------------------------
# 4) 입력 기준 선택
# ---------------------------------------------------------------------
basis = st.radio(
    "입력 기준을 선택하세요",
    ["익산 코드 입력 → 옥천 자동 조회", "옥천 코드 입력 → 익산 자동 조회"],
    horizontal=True,
)
# ★ 변경: 11자리 프리필에서 기준 자동 전환
if st.session_state.__basis_override in ["익산 코드 입력 → 옥천 자동 조회","옥천 코드 입력 → 익산 자동 조회"]:
    basis = st.session_state.__basis_override

basis_ik   = basis.startswith("익산")
base_side  = "IK" if basis_ik else "OK"
other_side = "OK" if basis_ik else "IK"

# ---------------------------------------------------------------------
# 5) 속성 렌더러 (slot 순 정렬 + 프리필 주입)
# ---------------------------------------------------------------------
def _slot_range(slot: str):
    try:
        rng = _slot_to_range(slot)
        if not rng:
            return (999, 999)
        return rng
    except Exception:
        return (999, 999)

def _order_keys_by_slot(udf, pair_id: str, side: str, keys: list[str]) -> list[str]:
    col_slot = "ik_slot" if side.upper()=="IK" else "ok_slot"
    S = udf[udf["pair_id"] == pair_id].set_index("key")
    pairs = []
    for k in keys:
        if k in S.index:
            a,b = _slot_range(str(S.loc[k][col_slot] or ""))
            pairs.append((a, b, k))
        else:
            pairs.append((999, 999, k))
    pairs.sort()
    return [k for _,__,k in pairs]

# ★ 변경: 프리필을 실제 위젯 기본값으로 주입하는 헬퍼
def _prime_default(widget_key: str, value: str):
    """해당 위젯 key가 아직 세션에 없을 때만 초기값을 주입."""
    if value is None:
        return
    if widget_key not in st.session_state:
        st.session_state[widget_key] = str(value)

def _render_inputs_for_side(
    udf, pair_id: str, side: str, pt_for_lookup: str,
    keys: list[str], tag_suffix: str=""
) -> dict:
    lookups = load_lookups()
    S = udf[udf["pair_id"] == pair_id].copy().set_index("key")
    keys_sorted = _order_keys_by_slot(udf, pair_id, side, keys)

    # ★ 변경: 11자리에서 해석해 온 프리필 딕셔너리
    prefill = st.session_state.get("prefill_attrs", {}) or {}

    attrs = {}
    cols = st.columns(2)
    i = 0
    for k in keys_sorted:
        if k not in S.index:
            st.warning(f"{k} : union_schema에 없음")
            continue
        r = S.loc[k]
        dtype   = str(r.get("dtype","") or "").strip()
        lookup  = str(r.get("lookup","") or "").strip()
        ik_slot = str(r.get("ik_slot","") or "")
        ok_slot = str(r.get("ok_slot","") or "")

        slot = ik_slot if side.upper()=="IK" else ok_slot
        a,b = _slot_range(slot)
        width_hint = 0 if a==999 else (b-a+1)

        c = cols[i % 2]; i += 1
        label = f"{k}{tag_suffix}"
        key = f"U:{pair_id}:{side}:{k}"

        # 프리필 값(문자열) 준비
        pre_val = "" if prefill.get(k) is None else str(prefill.get(k)).strip()

        if dtype == "lookup" and lookup:
            opts = lookup_options(lookups, lookup, pt_for_lookup)  # {code: label}
            if opts:
                codes = list(opts.keys())
                # ★ 변경: selectbox 기본값 주입
                if pre_val and pre_val in codes:
                    _prime_default(key, pre_val)
                    sel = c.selectbox(label, codes, format_func=lambda code: f"{code} - {opts.get(code,'')}",
                                      key=key)
                else:
                    sel = c.selectbox(label, codes, format_func=lambda code: f"{code} - {opts.get(code,'')}",
                                      key=key)
                attrs[k] = sel
            else:
                # 룩업 테이블이 비어있으면 코드 직접 입력
                _prime_default(key, pre_val)
                attrs[k] = c.text_input(f"{label} [코드]", key=key)
        else:
            # 자유 입력 — 자리 힌트 제공
            _prime_default(key, pre_val)  # ★ 변경: text_input 기본값
            ph = f"{width_hint}자리 숫자" if width_hint>0 else ""
            attrs[k] = c.text_input(label, key=key, placeholder=ph)

    return attrs

def get_required_sets(udf, pair_id: str, base_side: str):
    need_base  = required_keys(udf, pair_id, base_side)
    need_extra = extra_keys_from_other_side(udf, pair_id, base_side)
    if not need_base and not need_extra:
        all_keys = udf[udf["pair_id"] == pair_id]["key"].dropna().unique().tolist()
        need_base = all_keys
    return need_base, need_extra

# ---------------------------------------------------------------------
# 6) 좌/우 패널 렌더
# ---------------------------------------------------------------------
ik_selected, ok_selected = {}, {}
col_left, col_right = st.columns(2)

need_base, need_extra = ([], [])
if pair_id:
    need_base, need_extra = get_required_sets(udf, pair_id, base_side)

with col_left:
    st.subheader("익산")
    if ik_pt and ok_pt and pair_id:
        if basis_ik:
            ik_selected = _render_inputs_for_side(udf, pair_id, "IK", ik_pt, need_base)
            st.caption(f"part_type: {ik_pt}  (기준 측)")
        else:
            ik_selected = _render_inputs_for_side(udf, pair_id, "IK", ik_pt, need_extra, tag_suffix=" (추가)")
            st.caption(f"part_type: {ik_pt}  (상대측 추가)")
    else:
        st.caption(f"part_type: {ik_pt or '-'} (자동 조회 대상)")

with col_right:
    st.subheader("옥천")
    if ik_pt and ok_pt and pair_id:
        if basis_ik:
            ok_selected = _render_inputs_for_side(udf, pair_id, "OK", ok_pt, need_extra, tag_suffix=" (추가)")
            st.caption(f"part_type: {ok_pt}  (상대측 추가)")
        else:
            ok_selected = _render_inputs_for_side(udf, pair_id, "OK", ok_pt, need_base)
            st.caption(f"part_type: {ok_pt}  (기준 측)")
    else:
        st.caption(f"part_type: {ok_pt or '-'} (자동 조회 대상)")

# ---------------------------------------------------------------------
# 7) 조회/생성
# ---------------------------------------------------------------------
st.divider()
if st.button("조회"):
    if not pair_id:
        st.error("IK/OK pair가 확정되지 않았습니다.")
        st.stop()

    # 좌/우 입력 병합
    attrs = {}
    attrs.update(ik_selected or {})
    attrs.update(ok_selected or {})

    # 필수 누락 점검
    miss_base  = missing_required_keys(udf, pair_id, base_side,  attrs)
    miss_other = missing_required_keys(udf, pair_id, other_side, attrs)
    if miss_base:
        st.error(f"기준({base_side}) 필수 누락: {miss_base}")
        st.stop()
    if miss_other:
        st.warning(f"상대({other_side}) 필수 누락: {miss_other} — 이 키들까지 입력하면 완전한 11자리 생성")

    # 11자리 동시 생성
    ik_code, ok_code = encode_both(udf, pair_id, attrs)
    if ik_code: st.success(f"IK 코드: `{ik_code}`")
    if ok_code: st.success(f"OK 코드: `{ok_code}`")

    # matched_parts 확인/보강
    mdf = load_matched_full().copy()
    if not mdf.empty:
        ik_col = next((c for c in mdf.columns if "ik" in c.lower() and "code" in c.lower()),
                      mdf.columns[0])
        ok_col = next((c for c in mdf.columns if ("ok" in c.lower() and "code" in c.lower())
                       or "km" in c.lower()),
                      mdf.columns[1] if mdf.shape[1] > 1 else mdf.columns[0])
        mdf["__ik_norm"] = mdf[ik_col].map(_norm)
        mdf["__ok_norm"] = mdf[ok_col].map(_norm)

        if ik_code:
            hit = mdf[mdf["__ik_norm"] == _norm(ik_code)]
            if not hit.empty:
                ok_code = hit.iloc[0][ok_col]
                st.info(f"matched_parts 기준 OK: `{ok_code}`")
        elif ok_code:
            hit = mdf[mdf["__ok_norm"] == _norm(ok_code)]
            if not hit.empty:
                ik_code = hit.iloc[0][ik_col]
                st.info(f"matched_parts 기준 IK: `{ik_code}`")

# ---------------------------------------------------------------------
# 8) 이미지 출력 (좌=IK / 우=OK)
# ---------------------------------------------------------------------
st.divider()
col_l, col_r = st.columns(2)

with col_l:
    st.subheader("익산 이미지")
    if ik_pt:
        imgs = load_images(ik_pt)
        if imgs:
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
