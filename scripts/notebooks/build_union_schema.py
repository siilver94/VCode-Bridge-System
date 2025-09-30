# notebooks/build_union_schema.py
# -*- coding: utf-8 -*-
"""
codeSchema_IK.csv / codeSchema_OK.csv / Cross_Map.csv → union_schema.csv 빌더 (단일 파일 완성본)

전제(권장 원본 형식, 두 스키마 공통):
- columns: part_type, pos_from, pos_to, attr_name, lookup_table
  * part_type     : 품명군 (예: V111, 2655)
  * pos_from/to   : 11자리 내 시작/끝 위치(1-based). 한 자리면 from=to
  * attr_name     : 속성키 (예: material_code, surface_code, nominal, length_mm, thread_grade ...)
  * lookup_table  : 룩업 테이블명(비어있으면 숫자형으로 간주)

Cross_Map.csv:
- 권장 columns: ik_part_type, ok_part_type
  (헤더명이 다르면 자동 탐지 후보군으로 찾아봄)

출력 union_schema.csv (최소 12컬럼):
- pair_id, ik_part_type, ok_part_type, key, dtype, lookup,
  required_ik, required_ok, ik_slot, ik_codec, ok_slot, ok_codec

동작 요약:
- required_* : 해당 측 스키마에 해당 attr 행이 있으면 True로 간주(가장 단순한 규칙)
- slot       : pos_from-pos_to 문자열로 자동 생성
- codec      : lookup_table이 있으면 "lookup:code", 아니면 자리수 기반 "int:width=N,pad=0"
- dtype      : lookup 존재 시 "lookup", 아니면 "int"
- 문자열 정규화(_norm_pt): " 2655.0 " → "2655", 전각 공백 제거
"""

from __future__ import annotations
import pandas as pd
import re
from typing import Tuple, Dict, Any

# -------------------------------
# 안전 처리 & 정규화 유틸
# -------------------------------
def _s(v: Any, default: str = "") -> str:
    """NaN/None도 빈문자열로 안전 캐스팅"""
    if v is None:
        return default
    try:
        if pd.isna(v):
            return default
    except Exception:
        pass
    return str(v)

def _to_int_like(x: Any, default: int = 0) -> int:
    """'5', '5.0', 5 모두 int로 안전 변환"""
    sx = _s(x).strip()
    if sx == "":
        return default
    try:
        return int(float(sx))
    except Exception:
        return default

def _norm_pt(x: Any) -> str:
    """
    품명군 코드 문자열을 정규화:
    - 좌우 공백 제거
    - 전각 공백 제거
    - 2655.0 -> 2655 로 변환
    """
    s = _s(x).strip().replace("\u3000", " ")
    return s.split(".")[0] if s.endswith(".0") else s

def _slot_to_range(slot: str):
    if not slot or str(slot).strip()=="" or str(slot)=="nan":
        return None
    s = str(slot).strip()
    # 모든 하이픈 계열을 일반 '-' 로 통일
    s = s.replace("\u2013", "-").replace("\u2011", "-")  # EN DASH, NB HYPHEN
    if "-" in s:
        a, b = s.split("-", 1)
        return (int(a), int(b))
    else:
        i = int(s)
        return (i, i)

# 빌더에 “중복이 있으면 하나로 압축(coalesce)”하고, 정의가 서로 달라 충돌할 땐 명확한 에러를 내도록 헬퍼
def _coalesce_rows(df_block, side, part_type, key):
    """
    동일 (part_type, key)에 대해 여러 행이 있을 때 처리:
    - pos_from/pos_to/lookup 값이 모두 동일하면 첫 행만 채택
    - 값이 서로 다르면 에러를 발생시켜 사용자가 스키마를 정리하도록 유도
    """
    if isinstance(df_block, pd.Series):
        return df_block  # 이미 단일행

    # df_block : 같은 key 로 필터된 DataFrame
    tmp = df_block.copy()
    tmp["pos_from"] = tmp["pos_from"].map(_to_int_like)
    tmp["pos_to"]   = tmp["pos_to"].map(_to_int_like)
    tmp["lookup"]   = tmp["lookup"].fillna("").astype(str)

    sig = tmp[["pos_from","pos_to","lookup"]].drop_duplicates()

    if len(sig) == 1:
        # 완전히 동일 → 첫 행만 사용
        return tmp.iloc[0]
    else:
        # 서로 다른 정의가 혼재 → 에러로 알려줌
        raise ValueError(
            f"[중복 충돌] {side} part_type={part_type}, key={key} 에 대해 "
            f"서로 다른 정의가 {len(tmp)}건 존재합니다.\n"
            f"{tmp[['pos_from','pos_to','lookup']].to_string(index=False)}"
        )

# -------------------------------
# 원본 스키마 → 얇은 표준형으로 슬림화
# -------------------------------
# 현재 네 CSV 헤더(5컬럼)에 맞춘 매핑
IK_COL = dict(part_type="part_type", start="pos_from", end="pos_to",
              key="attr_name", lookup="lookup_table")
OK_COL = dict(part_type="part_type", start="pos_from", end="pos_to",
              key="attr_name", lookup="lookup_table")

def _slim(df: pd.DataFrame, C: Dict[str, str], side: str) -> pd.DataFrame:
    """원본 스키마에서 필요한 컬럼만 추출하여 표준형으로 변환"""
    need = [C["part_type"], C["start"], C["end"], C["key"], C["lookup"]]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise ValueError(f"[{side}] 스키마에 필요한 컬럼이 없습니다: {missing} / 현재 컬럼: {list(df.columns)}")

    out = df[need].copy()
    out.columns = ["part_type", "pos_from", "pos_to", "key", "lookup"]

    # 타입 & 정규화
    out["part_type"] = out["part_type"].map(_norm_pt)
    out["pos_from"]  = out["pos_from"].map(_to_int_like)
    out["pos_to"]    = out["pos_to"].map(_to_int_like)
    out["key"]       = out["key"].astype(str)
    out["lookup"]    = out["lookup"].fillna("").astype(str)

    return out

# -------------------------------
# Cross_Map 슬림화 (헤더 자동 탐지)
# -------------------------------
def _slim_pairs(df_pairs: pd.DataFrame) -> pd.DataFrame:
    cand_ik = ["ik_part_type", "ik", "vcode", "익산", "익산품명군", "v_part_type", "V코드"]
    cand_ok = ["ok_part_type", "ok", "km", "kms", "옥천", "옥천품명군", "km_part_type", "KM코드"]

    def pick(df: pd.DataFrame, cands) -> str | None:
        cols_lc = {c.lower(): c for c in df.columns}
        for c in cands:
            k = c.lower()
            if k in cols_lc:
                return cols_lc[k]
        return None

    col_ik = pick(df_pairs, cand_ik)
    col_ok = pick(df_pairs, cand_ok)
    if not col_ik or not col_ok:
        raise ValueError(f"[Cross_Map] ik/ok 품명군 컬럼을 찾지 못했습니다. "
                         f"ik 후보={cand_ik}, ok 후보={cand_ok}, 현재={list(df_pairs.columns)}")

    out = df_pairs[[col_ik, col_ok]].copy()
    out.columns = ["ik_part_type", "ok_part_type"]
    out["ik_part_type"] = out["ik_part_type"].map(_norm_pt)
    out["ok_part_type"] = out["ok_part_type"].map(_norm_pt)
    return out

# -------------------------------
# dtype/lookup/codec 자동 추론
# -------------------------------
def _infer(row: pd.Series | None) -> Tuple[str, str, str]:
    """
    행(row)에서 dtype, lookup, codec을 추론해서 반환.
    - lookup이 있으면: ("lookup", lookup_table, "lookup:code")
    - 없으면 숫자형:   ("int", "", f"int:width={width},pad=0")
    - slot 폭(width)이 0이면 codec은 빈 문자열
    """
    if row is None:
        return "", "", ""
    lk = _s(row.get("lookup", "")).strip()
    p_from = _to_int_like(row.get("pos_from", 0))
    p_to   = _to_int_like(row.get("pos_to", 0))
    width  = max(0, p_to - p_from + 1)

    if lk:
        return "lookup", lk, "lookup:code"
    else:
        return ("int", "", f"int:width={width},pad=0") if width > 0 else ("int", "", "")

# -------------------------------
# 메인: 두 스키마 + Cross_Map → union_schema.csv
# -------------------------------
def build_union(ik_csv: str, ok_csv: str, cross_map_csv: str, out_csv: str = "data/union_schema.csv") -> pd.DataFrame:
    # CSV는 반드시 문자열로 읽어서 숫자/공백 이슈를 피한다
    ik    = pd.read_csv(ik_csv, dtype=str)
    ok    = pd.read_csv(ok_csv, dtype=str)
    pairs = pd.read_csv(cross_map_csv, dtype=str)

    A = _slim(ik, IK_COL, side="IK"); A["side"] = "IK"
    B = _slim(ok, OK_COL, side="OK"); B["side"] = "OK"
    P = _slim_pairs(pairs)

    rows = []
    for _, p in P.iterrows():
        ik_pt = p["ik_part_type"]
        ok_pt = p["ok_part_type"]

        Ai = A[A.part_type == ik_pt].set_index("key", drop=False)
        Bo = B[B.part_type == ok_pt].set_index("key", drop=False)

        keys = sorted(set(Ai.index) | set(Bo.index))
        for k in keys:
            # 변경 (중복 안전)
            if k in Ai.index:
                a = _coalesce_rows(Ai.loc[k], side="IK", part_type=ik_pt, key=k)
            else:
                a = None
            if k in Bo.index:
                b = _coalesce_rows(Bo.loc[k], side="OK", part_type=ok_pt, key=k)
            else:
                b = None

            # 쪽별 필수 여부: 해당 스키마에 행이 있으면 True
            required_ik = a is not None
            required_ok = b is not None

            # 슬롯 문자열
          # 변경 (엔대시 사용)
            DASH = "\u2013"  # EN DASH “–”
            ik_slot = f"{_to_int_like(a['pos_from'])}{DASH}{_to_int_like(a['pos_to'])}" if a is not None else ""
            ok_slot = f"{_to_int_like(b['pos_from'])}{DASH}{_to_int_like(b['pos_to'])}" if b is not None else ""

            # dtype/lookup/codec 자동 추론
            dtype_ik, lookup_ik, codec_ik = _infer(a)
            dtype_ok, lookup_ok, codec_ok = _infer(b)

            # 공통 dtype/lookup은 한쪽 정보라도 있으면 사용(lookup 우선)
            dtype  = "lookup" if (lookup_ik or lookup_ok) else "int"
            lookup = lookup_ik if lookup_ik else lookup_ok

            rows.append(dict(
                pair_id      = f"{ik_pt}_{ok_pt}",
                ik_part_type = ik_pt,
                ok_part_type = ok_pt,
                key          = k,
                dtype        = dtype,
                lookup       = lookup,
                required_ik  = required_ik,
                required_ok  = required_ok,
                ik_slot      = ik_slot,
                ik_codec     = codec_ik if required_ik else "",
                ok_slot      = ok_slot,
                ok_codec     = codec_ok if required_ok else "",
            ))

    union = pd.DataFrame(rows, columns=[
        "pair_id","ik_part_type","ok_part_type","key","dtype","lookup",
        "required_ik","required_ok","ik_slot","ik_codec","ok_slot","ok_codec"
    ])
    union.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"✅ union_schema.csv saved: {len(union)} rows → {out_csv}")
    return union

# -------------------------------
# (옵션) 품질 점검 헬퍼
# -------------------------------
def validate_union(union: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """필수인데 slot/codec 비었는 케이스, dtype/lookup 결손 체크"""
    out = {}
    for side in ("ik", "ok"):
        req = union[union[f"required_{side}"] == True]
        out[f"{side}_missing_slot"]  = req[req[f"{side}_slot"].astype(str).str.strip() == ""][["pair_id","key"]]
        out[f"{side}_missing_codec"] = req[req[f"{side}_codec"].astype(str).str.strip() == ""][["pair_id","key"]]
    out["missing_dtype"]  = union[union["dtype"].astype(str).str.strip()  == ""][["pair_id","key"]]
    out["missing_lookup"] = union[(union["dtype"] == "lookup") & (union["lookup"].astype(str).str.strip() == "")][["pair_id","key"]]
    return out

# -------------------------------
# 직접 실행 예시
# -------------------------------
if __name__ == "__main__":
    # 프로젝트 폴더 구조에 맞게 경로를 바꿔서 사용하세요.
    u = build_union(
        ik_csv        = "data/codeSchema_IK.csv",
        ok_csv        = "data/codeSchema_OK.csv",
        cross_map_csv = "data/Cross_Map.csv",
        out_csv       = "data/union_schema.csv"
    )
    probs = validate_union(u)
    for k, v in probs.items():
        print(f"[{k}] {len(v)} rows")
        if len(v):
            print(v.head())
