#!/usr/bin/env python
# coding: utf-8
"""
parse_vcode.py  (두 시스템 & part_type 전용 master 대응)

1. codeSchema_IK.csv / codeSchema_OK.csv  : 자리수 규칙
2. material_lookup.csv · surface_lookup.csv · … : 룩업
3. part_master.csv  : site + part_type  (11자리 품번 없음)

출력:
    parsed_parts.csv  –  규칙 메타 + 스키마 있음/없음 플래그
"""

import pandas as pd
from pathlib import Path
import os
import re

# IK: V + 두 자리(그룹) / V + 세 자리(정확)
V3_RE = re.compile(r"^(V)(\d{2})(\d)$", re.IGNORECASE)  # V111, V802 ...
V2_RE = re.compile(r"^(V)(\d{2})$",     re.IGNORECASE)  # V11, V80 ...

def ik_group_key(ptype: str) -> str:
    """V111 -> V11 (이미 V11이면 그대로)"""
    s = (ptype or "").strip().upper()
    m3 = V3_RE.match(s)
    if m3:
        return f"{m3.group(1)}{m3.group(2)}"
    return s

def candidate_keys(system: str, ptype_raw: str) -> list[str]:
    """
    조회용 파트타입 키 우선순위:
    - IK: [정확키(V111 등), 그룹키(V11)]  (서로 다를 때만 2개)
    - OK: [정확키]
    """
    s = (ptype_raw or "").strip().upper()
    if system == "IK":
        g = ik_group_key(s)
        return [s] if s == g else [s, g]
    return [s]
    

# ── 0. 경로 정의 ──────────────────────────────────────────────
BASE_DIR = Path(r"C:\Users\Allen\Desktop\Project\TYM\V_CODE")  # 프로젝트 최상단 경로(윈도우 고정경로 예시)

# 스키마 파일: 각 시스템(IK/OK)별 part_type의 속성/룩업 규칙 테이블
SCHEMA_IK = BASE_DIR / "data" / "codeSchema_IK.csv"
SCHEMA_OK = BASE_DIR / "data" / "codeSchema_OK.csv"

# 룩업 파일들: 각 속성별 코드표(코드→라벨), part_type 전용(spec)과 전체 공통(common) 공존
LOOKUP_FILES = {
    'material_lookup':     BASE_DIR / "data" / "lookup" / "material_lookup.csv",
    'surface_lookup':      BASE_DIR / "data" / "lookup" / "surface_lookup.csv",
    'grade_lookup':        BASE_DIR / "data" / "lookup" / "grade_lookup.csv",
    'seal_lookup':         BASE_DIR / "data" / "lookup" / "seal_lookup.csv",
    'designation_lookup':  BASE_DIR / "data" / "lookup" / "designation_lookup.csv",
    'screw_tolerance_lookup':     BASE_DIR / "data" / "lookup" / "screw_tolerance_lookup.csv",
    'type_assembly_lookup':BASE_DIR / "data" / "lookup" / "type_assembly_lookup.csv",
}

# 마스터(입력) / 결과(출력) 경로
PART_CSV  = BASE_DIR / "data" / "part_master.csv"     # site + part_type 목록(완성 11자리 코드 없음)
OUT_CSV   = BASE_DIR / "data" / "parsed_parts.csv"    # 품명군 단위 "가능 코드 집합" 메타 결과

# ── 1. 스키마 로드 (시스템별) ─────────────────────────────────
schema_ik = pd.read_csv(SCHEMA_IK)  # 익산 시스템 스키마
schema_ok = pd.read_csv(SCHEMA_OK)  # 옥천 시스템 스키마

# ↓↓↓ 추가
schema_ik['part_type'] = schema_ik['part_type'].astype(str).str.strip().str.upper()
schema_ok['part_type'] = schema_ok['part_type'].astype(str).str.strip().str.upper()

# ── 2. 룩업 dict 로드 공통 함수 ──────────────────────────────
def build_lookup(csv: Path, value_col: str):
    """
    하나의 룩업 CSV를 읽어,
    - spec: (part_type, code) → 라벨
    - common: code → 라벨
    두 딕셔너리로 분리해 반환
    """
    df = pd.read_csv(csv, dtype=str).fillna('')  # 문자열로 통일 + 결측치 공백 처리
    # part_type가 '*'가 아니면 '특정 part_type 전용' 값

    if 'part_type' not in df.columns or 'code' not in df.columns:
        raise ValueError(f"{csv.name}에는 'part_type'와 'code' 컬럼이 필요합니다.")
    df['part_type'] = df['part_type'].astype(str).str.strip().str.upper()

    spec = df[df.part_type != '*'].set_index(['part_type','code'])[value_col].to_dict()
    # part_type가 '*'면 '전체 공통' 값
    common = df[df.part_type == '*'].set_index('code')[value_col].to_dict()
    return spec, common

LOOKUP_MAP = {}           # {'material_lookup': (spec_dict, common_dict), ...}

# 각 룩업 파일을 읽어서 LOOKUP_MAP에 적재
for name, path in LOOKUP_FILES.items():
    # CSV의 컬럼 중 ('part_type','code')를 제외한 '라벨 컬럼'을 자동 탐지(첫 번째 것을 사용)
    col = [c for c in pd.read_csv(path, nrows=1).columns if c not in ('part_type','code')][0]
    LOOKUP_MAP[name] = build_lookup(path, col)

def lookup(table_name:str, ptype:str, token:str):
    """
    주어진 룩업 테이블에서 (part_type 전용 → 공통) 순으로 라벨을 찾고,
    없으면 UNKNOWN(코드) 문자열 반환
    """
    """값 1개 조회: 정확(part_type) → (IK)그룹(Vxx) → 공통*"""
    spec, common = LOOKUP_MAP[table_name]
    for key in candidate_keys(system, ptype_raw):
        v = spec.get((key, token))
        if v is not None:
            return v
    return common.get(token) or f'UNKNOWN({token})'


# ── 3. part_master 로드 ─────────────────────────────────────
pm = pd.read_csv(PART_CSV, dtype=str)  # 마스터 읽기(모두 문자열)
# part_type이 'V'로 시작하면 IKSAN, 아니면 OKCHEON으로 시스템 분류
pm['system'] = pm['part_type'].str.startswith('V').map({True:'IK', False:'OK'})

# 데이터 불일치를 공백 제거와 모두 문자열로 변
pm['part_type'] = pm['part_type'].astype(str).str.strip()  # part_type 공백 제거/문자열화
schema_ok['part_type'] = schema_ok['part_type'].astype(str).str.strip()  # OK 스키마도 동일 정리
# (참고) schema_ik도 동일 정리가 필요할 수 있으나, 현 코드에선 OK만 처리

# ── 4. 파싱 (part_type 수준 – 11자리 없음) ───────────────────
rows = []  # 결과 행들을 담을 리스트(나중에 DataFrame으로 변환)
for _, row in pm.iterrows():
    ptype   = row.part_type          # 현재 행의 품명군(ex. V111)
    system  = row.system             # IK/OK
    # 시스템에 따라 해당 스키마에서, 현재 ptype에 해당하는 규칙들만 필터링
    rules_src = schema_ik if system == 'IK' else schema_ok
    
    # 1) 스키마: 정확 → (IK)그룹 순으로 찾기
    rules = pd.DataFrame()
    for key in candidate_keys(system, ptype):
        rules = rules_src[rules_src.part_type == key]
        if not rules.empty:
            break
    
    if rules.empty:
        rows.append({**row.to_dict(), '_parse_error': f'NO_SCHEMA({"/".join(candidate_keys(system, ptype))})'})
        continue
    
    # 2) 속성 메타 생성: (정확 + 그룹 + 공통)의 합집합을 옵션으로
    parsed = row.to_dict()
    for _, r in rules.iterrows():
        table = r.lookup_table
        if table in LOOKUP_MAP:
            spec, common = LOOKUP_MAP[table]
            cand = set(candidate_keys(system, ptype))
            spec_codes = {code for (pt, code) in spec.keys() if pt in cand}
            parsed[r.attr_name] = '|'.join(sorted(spec_codes | set(common.keys())))
        else:
            parsed[r.attr_name] = '(free)'
    rows.append(parsed)


# utils/parsers.py 내부 -----------------------
def split_vcode(code: str) -> dict:
    """
    11자리 V-Code를 파싱해 dict로 반환
    자리 구성: [0:4]=part_type(4), [4:6]=material(2), [6]=surface(1), [7]=grade(1), [8:11]=size(3)
    """
    ptype = code[:4]     # V111 (4자리)
    material = code[4:6] # 재질 코드(2자리)
    surface  = code[6]   # 표면 코드(1자리)
    grade    = code[7]   # 호칭/등급(1자리)
    size     = code[8:11]# 길이/사이즈(3자리)
    return {
        "part_type": ptype,
        "material_cd": material,
        "surface_cd": surface,
        "grade_cd": grade,
        "size_cd": size
    }
# --------------------------------------------

# csv 저장
out_df = pd.DataFrame(rows)  # rows를 DataFrame으로 변환
out_df.to_csv(OUT_CSV, index=False, encoding='cp949')  # 최종 메타 결과를 CP949로 저장(윈도우/한글 환경)
print(f"✅  part_type 수준 메타 출력 완료 → {OUT_CSV}")  # 완료 로그

#split_vcode("V11101234567")  # 예시 호출(주석 처리)
