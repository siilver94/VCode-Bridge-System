ㄴ#!/usr/bin/env python
# coding: utf-8

# In[1]:


# utils/loaders.py
from pathlib import Path
from PIL import Image
import pandas as pd
import re, inspect, sys
import streamlit as st

# In[2]:

# 안전 CSV 로더: UTF-8 → UTF-8-SIG → CP949 → EUC-KR 순서로 시도
def read_csv_safe(pathlike):
    p = pathlike if isinstance(pathlike, Path) else (DATA_DIR / pathlike)
    for enc in ("utf-8", "utf-8-sig", "cp949", "euc-kr"):
        try:
            return pd.read_csv(p, dtype=str, encoding=enc).fillna("")
        except UnicodeDecodeError:
            continue
    # 그래도 안 되면 에러를 올려 원인 확인
    return read_csv_safe(p, dtype=str, encoding="latin1").fillna("")


def _base_dir():
    """노트북/스크립트 어디서 불러도 프로젝트 최상단을 찾아줍니다."""
    # ① 이 파일이 모듈로 import 된 경우 → __file__ 사용
    if '__file__' in globals():
        return Path(__file__).resolve().parents[1]
    # ② Jupyter 셀에서 직접 실행된 경우 → 현재 노트북 위치 기준
    frame = inspect.currentframe()
    fname = inspect.getfile(frame)
    return Path(fname).resolve().parents[1]


# In[3]:


BASE_DIR = _base_dir()
DATA_DIR = BASE_DIR / "data"
IMG_DIR  = BASE_DIR / "images"

def load_images(part_type: str, max_imgs: int = 2):
    patt = re.compile(rf"^{re.escape(part_type)}(_\d+)?\.(png|jpe?g)$", re.I)
    files = [p for p in IMG_DIR.iterdir() if patt.match(p.name)]

    files = sorted(files)[:max_imgs]
    return [Image.open(p) for p in files]


# csv 읽어 올 함수
def load_matched():
    return pd.read_csv(DATA_DIR / "matched_parts.csv")

def load_catalog():
    """
    part_master.csv + category 컬럼을 읽어 DataFrame 반환
    """
    return read_csv_safe(DATA_DIR / "part_master.csv")

@st.cache_data
def load_code_schema(site: str = "IK") -> pd.DataFrame:
    """
    site = 'IK' -> codeSchema_IK.csv, site = 'OK' -> codeSchema_OK.csv
    기대 컬럼: part_type, attr_name, lookup_table (없으면 빈 문자열)
    """
    fname = "codeSchema_IK.csv" if site.upper()=="IK" else "codeSchema_OK.csv"
    df = read_csv_safe(DATA_DIR / fname).fillna('')
    return df

@st.cache_data
def load_lookups() -> dict:
    """
    7종 lookup csv를 읽어 테이블명 -> {spec, common, value_col} 사전으로 반환
    (테이블명 예: material_lookup, surface_lookup ...)
    """
    files = [
        "material_lookup.csv", "surface_lookup.csv", "grade_lookup.csv",
        "seal_lookup.csv", "designation_lookup.csv",
        "screw_tolerance_lookup.csv", "type_assembly_lookup.csv",
    ]
    result = {}
    for f in files:
        p = DATA_DIR / f
        if not p.exists():
            continue
        df = pd.read_csv(p, dtype=str).fillna('')
        value_cols = [c for c in df.columns if c not in ("part_type","code")]
        value_col  = value_cols[0] if value_cols else "value"
        spec   = df[df.part_type != "*"].set_index(["part_type","code"])[value_col].to_dict()
        common = df[df.part_type == "*"].set_index("code")[value_col].to_dict()
        key = f.replace(".csv","")  # "material_lookup" 등
        result[key] = {"spec": spec, "common": common, "value_col": value_col}
    return result

def lookup_options(lookups: dict, table: str, part_type: str) -> dict:
    """
    특정 lookup_table과 part_type에 맞는 {코드: 라벨} 반환
    """
    obj = lookups.get(table)
    if not obj:
        return {}
    spec_codes = [code for (pt, code) in obj["spec"].keys() if pt == part_type]
    spec_map   = {code: obj["spec"][(part_type, code)] for code in spec_codes}
    return {**obj["common"], **spec_map}


def _detect_crossmap_cols(df: pd.DataFrame):
    """컬럼명이 제각각일 수 있어 자동 추론(우선순위: 명시 → 패턴)"""
    cols = [c.lower() for c in df.columns]
    # 1) 자주 쓰는 명칭
    ik_candidates = [c for c in df.columns if c.lower() in ("ik_part_type","iksan_part_type","v_part_type","vcode","ik_pt")]
    ok_candidates = [c for c in df.columns if c.lower() in ("ok_part_type","okcheon_part_type","km_part_type","kmcode","ok_km_code","ok_pt")]
    ik_col = ik_candidates[0] if ik_candidates else None
    ok_col = ok_candidates[0] if ok_candidates else None
    # 2) 패턴으로 보완
    if not ik_col:
        for c in df.columns:
            vals = df[c].astype(str)
            if (vals.str.match(r"^V\d{3}$", na=False)).mean() > 0.5:  # 절반 이상 V###
                ik_col = c; break
    if not ok_col:
        for c in df.columns:
            vals = df[c].astype(str)
            if (vals.str.match(r"^\d{4,5}$", na=False)).mean() > 0.5:
                ok_col = c; break
    return ik_col, ok_col


@st.cache_data
def load_crossmap():
    """Cross_Map.csv에서 IK↔OK 매핑 dict 2개 반환"""
    df = read_csv_safe(DATA_DIR / "Cross_Map.csv").fillna("")
    ik_col, ok_col = _detect_crossmap_cols(df)
    if not ik_col or not ok_col:
        raise ValueError("Cross_Map.csv에서 IK/OK 컬럼을 찾지 못했습니다. 컬럼명을 확인하세요.")
    ik2ok = dict(df[[ik_col, ok_col]].dropna().values)
    ok2ik = dict(df[[ok_col, ik_col]].dropna().values)
    return ik2ok, ok2ik

@st.cache_data
def load_matched_full():
    return read_csv_safe("matched_parts.csv")

