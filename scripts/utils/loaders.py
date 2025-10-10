#!/usr/bin/env python
# coding: utf-8

# In[1]:


# utils/loaders.py
from pathlib import Path              # OS 독립적인 경로 처리 유틸
from PIL import Image                 # 이미지 파일 열기/처리(Pillow)
import pandas as pd                   # 표 형식 데이터 처리(pandas)
import re, inspect, sys               # re: 정규식, inspect: 실행 프레임/파일 추적, sys: 인터프리터(현재 미사용)
import streamlit as st                # Streamlit 캐시/위젯용

# In[2]:
def _base_dir():
    """노트북/스크립트 어디서 불러도 프로젝트 최상단을 찾아줍니다.
    - 스크립트(import) 실행: __file__ 기준
    - 노트북/인터랙티브 셀 실행: 현재 프레임의 파일 경로 기준
    """
    # ① 이 파일이 모듈로 import 된 경우 → __file__ 사용
    if '__file__' in globals():
        return Path(__file__).resolve().parents[1]  # 파일 절대경로 → 상위 폴더의 상위(=프로젝트 루트 가정)
    # ② Jupyter 셀에서 직접 실행된 경우 → 현재 노트북 위치 기준
    frame = inspect.currentframe()                  # 현재 실행 중 프레임 객체
    fname = inspect.getfile(frame)                  # 해당 프레임의 파일 경로
    return Path(fname).resolve().parents[1]         # 노트북 파일 기준 상위의 상위 폴더 반환

BASE_DIR = _base_dir()               # 프로젝트 루트(어디서 실행하든 일관된 기준)
DATA_DIR  = BASE_DIR / "data"   
LOOKUP_DIR = BASE_DIR / "data" / "lookup"   # 데이터 폴더(입·출력 CSV 등)
IMG_DIR   = BASE_DIR / "images"      # 이미지 폴더

# 안전 CSV 로더: UTF-8 → UTF-8-SIG → CP949 → EUC-KR 순서로 시도
def read_csv_safe(pathlike):
    """여러 인코딩 후보를 순차 시도하여 CSV를 안전하게 읽습니다.
    - pathlike가 문자열이면 DATA_DIR/<pathlike>로 간주
    - 모든 시도가 실패해도 마지막에 errors='ignore'로 강제 로드(깨진 문자는 무시)
    - 항상 dtype=str + fillna("")로 문자열/결측치 정규화
    """
    p = pathlike if isinstance(pathlike, Path) else (DATA_DIR / pathlike)  # Path 인스턴스면 그대로, 아니면 DATA_DIR 상대경로
    for enc in ("utf-8", "utf-8-sig", "cp949", "euc-kr", "latin1"):        # 실무에서 자주 쓰는 인코딩 순으로 시도
        try:
            return pd.read_csv(p, dtype=str, encoding=enc).fillna("")
        except UnicodeDecodeError:
            continue                                                       # 디코딩 안 되면 다음 인코딩 시도
    # 그래도 안 되면 pandas 기본 디코딩으로 무시 옵션
    return pd.read_csv(p, dtype=str, errors="ignore").fillna("")           # 일부 문자가 깨져도 일단 로드


# In[3]:


def load_union_schema() -> pd.DataFrame:
    """IK/OK 통합 스키마(union_schema.csv)를 로드하고 컬럼 표준화를 수행합니다.
    - 모든 컬럼 문자열화(detype=str)
    - 주요 텍스트 컬럼 strip(공백 제거)
    - required_ik/required_ok 문자열 불리언("TRUE","1" 등) → 실제 bool 변환
    """
    # CSV는 항상 문자열로 읽고(엑셀 BOM 호환), 불리언/문자 정규화
    df = pd.read_csv(DATA_DIR / "union_schema.csv", dtype=str, encoding="utf-8-sig")

    # 트림 & 대소문자 정규화: 주요 키/속성 컬럼을 공백 제거/문자열화
    for c in ["pair_id", "ik_part_type", "ok_part_type", "key", "dtype", "lookup",
              "ik_slot", "ok_slot", "ik_codec", "ok_codec"]:
        if c in df.columns:
            df[c] = df[c].fillna("").astype(str).str.strip()

    # ★ 문자열 "TRUE"/"FALSE"/"1"/"0" → bool 로 변환 (빈 문자열은 False)
    def _to_bool_series(s):
        return s.fillna("").astype(str).str.strip().str.upper().map({
            "TRUE": True, "FALSE": False, "1": True, "0": False, "": False
        }).fillna(False)

    # 필수 여부 컬럼을 불리언으로 캐스팅
    for c in ["required_ik", "required_ok"]:
        if c in df.columns:
            df[c] = _to_bool_series(df[c])

    return df

def load_images(part_type: str, max_imgs: int = 2):
    """
    images/<part_type>*.{png,jpg,jpeg} 를 찾아 PIL Image 리스트로 반환.
    - 전역 IMG_DIR 의존 제거: 함수 내부에서 항상 안전하게 경로 계산(외부 실행 대비)
    - 디렉토리/파일이 없으면 [] 반환 → 호출측(UI)에서 '이미지 없음' 출력 가능
    - 파일명 패턴: ^<part_type>(_<숫자>)?\\.(png|jpe?g)$ (대소문자 무시)
    """
    # 1) 기본 경로 계산 (전역이 있으면 사용, 없으면 다시 계산)
    try:
        base_dir = BASE_DIR                   # 전역 상수 사용(정상 케이스)
    except NameError:
        base_dir = _base_dir()                # 전역이 없다면 동적으로 계산

    img_dir = base_dir / "images"
    if not img_dir.exists():
        # 프로젝트 외부 실행 혹은 상대경로 실행 대비: ./images 폴더도 한 번 더 체크
        alt = Path("images")
        img_dir = alt if alt.exists() else img_dir  # 둘 다 없으면 아래서 [] 리턴

    if not img_dir.exists():
        return []                              # 이미지 폴더 자체가 없으면 빈 리스트

    # 2) 파일 매칭: part_type 또는 part_type_1, part_type_2 ... 와 확장자 png/jpg/jpeg
    patt = re.compile(rf"^{re.escape(str(part_type))}(_\d+)?\.(png|jpe?g)$", re.I)
    files = sorted([p for p in img_dir.iterdir() if patt.match(p.name)])[:max_imgs]

    # 3) 이미지 열기 (깨진 파일은 건너뜀)
    out = []
    for p in files:
        try:
            out.append(Image.open(p))         # PIL 이미지 객체
        except Exception:
            # 손상 이미지/권한 문제 등은 조용히 skip (UI 흐름 끊지 않기 위함)
            pass
    return out



# csv 읽어 올 함수
def load_matched():
    """matched_parts.csv 전체를 안전 로더로 읽어 반환"""
    return read_csv_safe(DATA_DIR / "matched_parts.csv")

def load_catalog():
    """
    part_master.csv + category 컬럼을 읽어 DataFrame 반환
    - site/part_type/category 등 카탈로그 메타
    """
    return read_csv_safe(DATA_DIR / "part_master.csv")

@st.cache_data
def load_code_schema(site: str = "IK") -> pd.DataFrame:
    """
    site = 'IK' -> codeSchema_IK.csv, site = 'OK' -> codeSchema_OK.csv
    기대 컬럼: part_type, attr_name, lookup_table (없으면 빈 문자열)
    - Streamlit 캐시 적용: 동일 인자(site) 재호출시 디스크 재읽기 없이 메모리 반환
    """
    fname = "codeSchema_IK.csv" if site.upper()=="IK" else "codeSchema_OK.csv"
    df = read_csv_safe(DATA_DIR / fname).fillna('')  # 안전 로더 사용(인코딩 이슈 방지)
    return df

@st.cache_data
def load_lookups() -> dict:
    """
    7종 lookup csv를 읽어 테이블명 -> {spec, common, value_col} 사전으로 반환
    (테이블명 예: material_lookup, surface_lookup ...)
    - spec: {(part_type, code): label}  # 전용값
    - common: {code: label}             # 공통값
    - value_col: 라벨 컬럼명(동적으로 감지)
    """
    files = [
        "material_lookup.csv", "surface_lookup.csv", "grade_lookup.csv",
        "seal_lookup.csv", "designation_lookup.csv",
        "screw_tolerance_lookup.csv", "type_assembly_lookup.csv",
    ]
    result = {}
    for f in files:
        p = LOOKUP_DIR / f
        if not p.exists():
            continue                         # 파일이 없으면 건너뛰기(유연성)
        df = pd.read_csv(p, dtype=str).fillna('')  # 문자열/결측치 정규화
        # part_type/code를 제외한 나머지 1개 열을 라벨 컬럼으로 간주(첫 번째 것)
        value_cols = [c for c in df.columns if c not in ("part_type","code")]
        value_col  = value_cols[0] if value_cols else "value"
        # 전용값/공통값 딕셔너리 구성
        spec   = df[df.part_type != "*"].set_index(["part_type","code"])[value_col].to_dict()
        common = df[df.part_type == "*"].set_index("code")[value_col].to_dict()
        key = f.replace(".csv","")  # "material_lookup" 등 파일명 → 테이블명 키
        result[key] = {"spec": spec, "common": common, "value_col": value_col}
    return result


def lookup_options(lookups: dict, table: str, part_type: str) -> dict:
    """
    특정 lookup_table과 part_type에 맞는 {코드: 라벨} 반환
    - 공백/대소문자/키 누락/중복에 안전
    - common(공통) + spec(전용) 병합 (spec이 공통을 덮어씀)
    """
    obj = lookups.get(table)
    if not obj:
        return {}

    # 안전하게 가져오기(키 없으면 디폴트 {})
    spec = obj.get("spec", {})      # {(pt, code): label}
    common = obj.get("common", {})  # {code: label}

    pt = str(part_type).strip()     # part_type 공백 정리

    # 해당 part_type에 매칭되는 spec만 추출: (ppt, code)에서 ppt가 현재 pt인 것만
    spec_map = {code: spec[(ppt, code)]
                for (ppt, code) in spec.keys()
                if str(ppt).strip() == pt}

    # 공통 + 전용 합치되, 전용이 우선(덮어쓰기)
    merged = {**common, **spec_map}

    # 코드 키/라벨 공백 정리 + 빈 키 제거
    cleaned = {str(k).strip(): str(v).strip() for k, v in merged.items() if str(k).strip()}

    return cleaned



def _detect_crossmap_cols(df: pd.DataFrame):
    """Cross_Map 컬럼명이 제각각일 수 있어 자동 추론(우선순위: 명시 후보 → 패턴)
    - IK 후보: ik_part_type/iksan_part_type/v_part_type/vcode/ik_pt 등
    - OK 후보: ok_part_type/okcheon_part_type/km_part_type/kmcode/ok_km_code/ok_pt 등
    - 후보가 없으면 패턴으로 보완:
        · IK: 값의 절반 이상이 ^V\\d{3}$ (예: V111) 인 컬럼
        · OK: 값의 절반 이상이 ^\\d{4,5}$ (4~5자리 숫자) 인 컬럼
    """
    cols = [c.lower() for c in df.columns]
    # 1) 자주 쓰는 명칭(케이스 무시) 우선 매칭
    ik_candidates = [c for c in df.columns if c.lower() in ("ik_part_type","iksan_part_type","v_part_type","vcode","ik_pt")]
    ok_candidates = [c for c in df.columns if c.lower() in ("ok_part_type","okcheon_part_type","km_part_type","kmcode","ok_km_code","ok_pt")]
    ik_col = ik_candidates[0] if ik_candidates else None
    ok_col = ok_candidates[0] if ok_candidates else None
    # 2) 패턴으로 보완(후보가 비었을 때만)
    if not ik_col:
        for c in df.columns:
            vals = df[c].astype(str)
            if (vals.str.match(r"^V\d{3}$", na=False)).mean() > 0.5:  # 절반 이상 V###
                ik_col = c; break
    if not ok_col:
        for c in df.columns:
            vals = df[c].astype(str)
            if (vals.str.match(r"^\d{4,5}$", na=False)).mean() > 0.5: # 절반 이상 4~5자리 숫자
                ok_col = c; break
    return ik_col, ok_col


@st.cache_data
def load_crossmap():
    """Cross_Map.csv에서 IK↔OK 매핑 dict 2개 반환
    - IK→OK (ik2ok): {ik_part_type: ok_part_type}
    - OK→IK (ok2ik): {ok_part_type: ik_part_type}
    - 컬럼명이 다를 수 있으므로 자동 감지(_detect_crossmap_cols) 사용
    """
    df = read_csv_safe(DATA_DIR / "Cross_Map.csv").fillna("")
    ik_col, ok_col = _detect_crossmap_cols(df)
    if not ik_col or not ok_col:
        # 필수 컬럼을 찾지 못하면 명확한 에러 메시지로 가이드
        raise ValueError("Cross_Map.csv에서 IK/OK 컬럼을 찾지 못했습니다. 컬럼명을 확인하세요.")
    # 두 컬럼 페어만 뽑아 NA 제거 후 dict 변환
    ik2ok = dict(df[[ik_col, ok_col]].dropna().values)
    ok2ik = dict(df[[ok_col, ik_col]].dropna().values)
    return ik2ok, ok2ik

@st.cache_data
def load_matched_full():
    """matched_parts.csv 전체를 안전 로더로 읽어 반환(캐시)"""
    return read_csv_safe("matched_parts.csv")

