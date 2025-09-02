# notebooks/vcode_codec.py
# -*- coding: utf-8 -*-

import re
import pandas as pd
from typing import Dict, List, Tuple

# ----------------------------
# 소도구
# ----------------------------
def _s(x) -> str:
    if x is None:
        return ""
    try:
        import pandas as _pd
        if _pd.isna(x):
            return ""
    except Exception:
        pass
    return str(x)

def _slot_to_range(slot: str) -> Tuple[int, int] | None:
    """
    '7–8', '7-8', '7-8'(NB hyphen) 등을 모두 허용.
    단일 '5'도 허용 -> (5,5)
    """
    if not slot:
        return None
    s = _s(slot).strip()
    if s == "" or s.lower() == "nan":
        return None
    # 하이픈 계열 통일
    s = s.replace("\u2013", "-").replace("\u2011", "-").replace("~", "-").replace(":", "-")
    if "-" in s:
        a, b = s.split("-", 1)
        return (int(a), int(b))
    else:
        i = int(s)
        return (i, i)

def _parse_int_codec(codec: str) -> Tuple[int, str]:
    """
    int 코덱 파싱: 'int:width=3,pad=0' -> (3,'0')
    없으면 (1,'')
    """
    width = 1
    pad = ""
    c = _s(codec)
    m = re.search(r"width\s*=\s*(\d+)", c)
    if m:
        width = int(m.group(1))
    m = re.search(r"pad\s*=\s*([0-9A-Za-z])", c)
    if m:
        pad = m.group(1)
    return width, pad

def _apply_codec(value, codec: str, width_hint: int | None = None) -> str:
    c = _s(codec).strip()
    if c.startswith("lookup:"):
        return _s(value)
    if c.startswith("int:"):
        width, pad = _parse_int_codec(c)
        s = str(int(value))  # 숫자 보장
        if pad:
            return s.rjust(width, pad)
        # pad 미지정이면 폭만 맞춤
        return s.rjust(width)
    # codec이 비었거나 규칙 외면 best-effort
    v = _s(value)
    if width_hint and len(v) < width_hint:
        return v.rjust(width_hint, "0")
    return v

def _pair_prefixes(union_df: pd.DataFrame, pair_id: str) -> Tuple[str, str]:
    rows = union_df[union_df["pair_id"] == pair_id]
    if rows.empty:
        raise ValueError(f"pair_id '{pair_id}' 를 union_schema에서 찾지 못했습니다.")
    ik_pt = rows["ik_part_type"].iloc[0]
    ok_pt = rows["ok_part_type"].iloc[0]
    return str(ik_pt), str(ok_pt)

# ----------------------------
# 공개 API
# ----------------------------
def required_keys(union_df: pd.DataFrame, pair_id: str, side: str) -> List[str]:
    side = side.upper()
    col = "required_ik" if side == "IK" else "required_ok"
    return union_df[(union_df["pair_id"] == pair_id) & (union_df[col] == True)]["key"].tolist()

def extra_keys_from_other_side(union_df: pd.DataFrame, pair_id: str, base_side: str) -> List[str]:
    """
    base_side=IK이면 OK에서만 필수인 키 목록(= IK 폼에서 '추가 입력'으로 보여줄 키)
    """
    base_side = base_side.upper()
    if base_side == "IK":
        need_other = required_keys(union_df, pair_id, "OK")
        need_base  = required_keys(union_df, pair_id, "IK")
    else:
        need_other = required_keys(union_df, pair_id, "IK")
        need_base  = required_keys(union_df, pair_id, "OK")
    return [k for k in need_other if k not in need_base]

def missing_required_keys(union_df: pd.DataFrame, pair_id: str, side: str, attrs: Dict) -> List[str]:
    needs = required_keys(union_df, pair_id, side)
    miss = []
    for k in needs:
        v = attrs.get(k, None)
        if v is None or _s(v).strip() == "":
            miss.append(k)
    return miss

def encode_code(side: str, union_df: pd.DataFrame, pair_id: str,
                attrs: Dict, base_prefix: str | None = None,
                fill_char: str = "?") -> str:
    """
    side: "IK" 또는 "OK"
    union_df: pd.read_csv(... "union_schema.csv")
    pair_id: 예) "V111_2655"
    attrs: {"material_code":"7", "surface_code":"6", "nominal":4, "length_mm":8, "thread_grade":"2", ...}
           - lookup 값은 '코드' 기준 (라벨→코드 변환이 필요하면 UI/상위 레이어에서 처리)
    base_prefix: 맨 앞 고정 prefix. 주지 않으면 union_df에서 pair의 part_type을 자동 사용
    fill_char: 비어있는 칸의 대체 문자 (기본 '?')
    """
    side = side.upper()
    if base_prefix is None:
        ik_pt, ok_pt = _pair_prefixes(union_df, pair_id)
        base_prefix = ik_pt if side == "IK" else ok_pt
    code = list(" " * 11)

    # prefix 삽입 (1부터 시작)
    for i, ch in enumerate(str(base_prefix), start=1):
        if i <= 11:
            code[i - 1] = ch

    # pair 행들
    S = union_df[union_df["pair_id"] == pair_id]

    slot_col  = "ik_slot"  if side == "IK" else "ok_slot"
    codec_col = "ik_codec" if side == "IK" else "ok_codec"

    for _, r in S.iterrows():
        key   = r["key"]
        slot  = r[slot_col]
        codec = r[codec_col]
        rng = _slot_to_range(slot)
        if rng is None:
            continue
        a, b = rng
        width = b - a + 1

        # 값이 없으면 건너뛴다(필요시 '?'로 채우고 싶으면 아래 else 분기에서 처리)
        if key not in attrs or _s(attrs[key]).strip() == "":
            # 미입력은 그대로 두되, 시각화가 필요하면 아래 주석 해제
            # for off in range(width):
            #     idx = a - 1 + off
            #     if 0 <= idx < 11:
            #         code[idx] = fill_char
            continue

        val = attrs[key]
        enc = _apply_codec(val, codec, width_hint=width)
        # 길이 보정
        if len(enc) < width:
            enc = enc.rjust(width, "0")
        elif len(enc) > width:
            
            enc = enc[-width:]  # 뒤에서 width만큼 사용

        for off, ch in enumerate(enc):
            idx = a - 1 + off
            if 0 <= idx < 11:
                
                code[idx] = ch

    # 남은 공백 표시용(옵션)
    code = [ch if ch != " " else fill_char for ch in code]
    return "".join(code)

def encode_both(union_df: pd.DataFrame, pair_id: str, attrs: Dict, fill_char: str = "?") -> Tuple[str, str]:
    ik_pt, ok_pt = _pair_prefixes(union_df, pair_id)
    ik = encode_code("IK", union_df, pair_id, attrs, base_prefix=ik_pt, fill_char=fill_char)
    ok = encode_code("OK", union_df, pair_id, attrs, base_prefix=ok_pt, fill_char=fill_char)
    return ik, ok
