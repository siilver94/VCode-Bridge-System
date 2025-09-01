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

# ── 0. 경로 정의 ──────────────────────────────────────────────

BASE_DIR = Path(r"C:\Users\Allen\Desktop\Project\TYM\V_CODE")

SCHEMA_IK = BASE_DIR / "data" / "codeSchema_IK.csv"
SCHEMA_OK = BASE_DIR / "data" / "codeSchema_OK.csv"


LOOKUP_FILES = {
    'material_lookup':     BASE_DIR / "data" / "material_lookup.csv",
    'surface_lookup':      BASE_DIR / "data" / "surface_lookup.csv",
    'grade_lookup':        BASE_DIR / "data" / "grade_lookup.csv",
    'seal_lookup':         BASE_DIR / "data" / "seal_lookup.csv",
    'designation_lookup':  BASE_DIR / "data" / "designation_lookup.csv",
    'screw_tolerance_lookup':     BASE_DIR / "data" / "screw_tolerance_lookup.csv",
    'type_assembly_lookup':BASE_DIR / "data" / "type_assembly_lookup.csv",
}

PART_CSV  = BASE_DIR / "data" / "part_master.csv"
OUT_CSV   = BASE_DIR / "data" / "parsed_parts.csv"

# ── 1. 스키마 로드 (시스템별) ─────────────────────────────────
schema_ik = pd.read_csv(SCHEMA_IK)
schema_ok = pd.read_csv(SCHEMA_OK)

# ── 2. 룩업 dict 로드 공통 함수 ──────────────────────────────
def build_lookup(csv: Path, value_col: str):
    df = pd.read_csv(csv, dtype=str).fillna('')
    spec = df[df.part_type != '*'].set_index(['part_type','code'])[value_col].to_dict()
    common = df[df.part_type == '*'].set_index('code')[value_col].to_dict()
    return spec, common

LOOKUP_MAP = {}           # {'material': (spec, common), ...}

for name, path in LOOKUP_FILES.items():
    col = [c for c in pd.read_csv(path, nrows=1).columns if c not in ('part_type','code')][0]
    LOOKUP_MAP[name] = build_lookup(path, col)

def lookup(table_name:str, ptype:str, token:str):
    spec, common = LOOKUP_MAP[table_name]
    return spec.get((ptype, token)) or common.get(token) or f'UNKNOWN({token})'

# ── 3. part_master 로드 ─────────────────────────────────────
pm = pd.read_csv(PART_CSV, dtype=str)
pm['system'] = pm['part_type'].str.startswith('V').map({True:'IK', False:'OK'})

# 데이터 불일치를 공백 제거와 모두 문자열로 변
pm['part_type'] = pm['part_type'].astype(str).str.strip()
schema_ok['part_type'] = schema_ok['part_type'].astype(str).str.strip()

# ── 4. 파싱 (part_type 수준 – 11자리 없음) ───────────────────
rows = []
for _, row in pm.iterrows():
    ptype   = row.part_type
    system  = row.system
    rules   = schema_ik if system=='IK' else schema_ok
    rules   = rules[rules.part_type == ptype]

    if rules.empty:
        rows.append({**row.to_dict(), '_parse_error': f'NO_SCHEMA({ptype})'})
        continue

    parsed = row.to_dict()
    for _, r in rules.iterrows():
        # 자리 토큰이 없으므로 '가능 코드 집합'만 표시
        table = r.lookup_table
        if table in LOOKUP_MAP:
            parsed[r.attr_name] = '|'.join(
                sorted({k[1] for k in LOOKUP_MAP[table][0].keys() if k[0]==ptype} |
                       set(LOOKUP_MAP[table][1].keys()))
            )
        else:
            parsed[r.attr_name] = '(free)'
    rows.append(parsed)

# csv 저장
out_df = pd.DataFrame(rows)
out_df.to_csv(OUT_CSV, index=False, encoding='cp949')
print(f"✅  part_type 수준 메타 출력 완료 → {OUT_CSV}")

# utils/parsers.py 내부 -----------------------
def split_vcode(code: str) -> dict:
    """
    11자리 V‑Code를 파싱해 dict로 반환
    """
    ptype = code[:4]     # V111
    material = code[4:6]
    surface  = code[6]
    grade    = code[7]
    size     = code[8:11]
    return {
        "part_type": ptype,
        "material_cd": material,
        "surface_cd": surface,
        "grade_cd": grade,
        "size_cd": size
    }
# --------------------------------------------
