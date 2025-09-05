# codeSchema_IK.csv/data/codeSchema_OK.csv -> union_schema.csv 로 합치기

from notebooks.build_union_schema import build_union, validate_union

u = build_union("data/codeSchema_IK.csv","data/codeSchema_OK.csv","data/Cross_Map.csv","data/union_schema.csv")
validate_union(u)

import pandas as pd

ik = pd.read_csv("data/codeSchema_IK.csv", dtype=str)
ok = pd.read_csv("data/codeSchema_OK.csv", dtype=str)

def dup_check(df, name):
    g = df.groupby(["part_type","attr_name"]).size().reset_index(name="n")
    dups = g[g["n"]>1]
    print(f"[{name}] dup count:", len(dups))
    return dups

dup_ik = dup_check(ik, "IK")
dup_ok = dup_check(ok, "OK")
dup_ik.head(), dup_ok.head()

import pandas as pd
from notebooks.vcode_codec import (
    encode_code, encode_both,
    required_keys, extra_keys_from_other_side, missing_required_keys
)

u = pd.read_csv("data/union_schema.csv")   # utf-8-sig로 저장되어 있다면 encoding 생략OK

pair = "V111_2655"

# 1) 기준 측(IK) 필수와 상대측(OK) 추가 입력 키 보기
print("IK 필수:", required_keys(u, pair, "IK"))
print("OK 필수:", required_keys(u, pair, "OK"))
print("IK 기준일 때 추가로 받아야 할 OK 전용 키:", extra_keys_from_other_side(u, pair, "IK"))

# 2) 값 입력(예시) → 보유 룩업은 '코드' 값으로
attrs = {
    "material_code":"7",
    "surface_code":"6",
    "nominal":4,
    "length_mm":8,
    "thread_grade":"2"  # OK 전용(예시)
}

# 3) 미입력 필수 키 체크(UX에서 경고에 사용)
print("IK 부족:", missing_required_keys(u, pair, "IK", attrs))
print("OK 부족:", missing_required_keys(u, pair, "OK", attrs))

# 4) 11자리 생성
ik_code = encode_code("IK", u, pair, attrs)            # prefix 자동
ok_code = encode_code("OK", u, pair, attrs)            # prefix 자동
print("IK:", ik_code)
print("OK:", ok_code)

# 또는 동시에
ik2, ok2 = encode_both(u, pair, attrs)
print(ik2, ok2)
