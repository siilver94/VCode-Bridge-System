# notebooks/build_union_schema.py
import pandas as pd
import re

IK_COL = dict(part_type="part_type", key="attr_name", dtype="dtype", lookup="lookup",
              required="required", slot="slot", codec="codec")
OK_COL = dict(part_type="part_type", key="attr_name", dtype="dtype", lookup="lookup",
              required="required", slot="slot", codec="codec")

def _slim(df, C):
    cols = [C["part_type"], C["key"], C["dtype"], C.get("lookup","lookup"),
            C["required"], C["slot"], C["codec"]]
    cols = [c for c in cols if c in df.columns]
    out = df[cols].rename(columns={
        C["part_type"]:"part_type", C["key"]:"key", C["dtype"]:"dtype",
        C.get("lookup","lookup"):"lookup", C["required"]:"required",
        C["slot"]:"slot", C["codec"]:"codec"
    })
    if "lookup" not in out.columns:
        out["lookup"] = ""
    return out

def _to_bool(x):
    if pd.isna(x): return False
    s = str(x).strip().lower()
    return s in {"1","true","t","y","yes","필수","required","✓","o"}

def _norm_pt(x):
    s = str(x).strip()
    # 2655.0 → 2655, 숫자 or V111 같은 건 그대로
    if re.fullmatch(r"\d+(\.0)?", s):
        return s.split(".")[0]
    return s

def build_union(ik_csv, ok_csv, cross_map_csv, out_csv):
    # 핵심: 모두 문자열로 읽기
    ik    = pd.read_csv(ik_csv, dtype=str)
    ok    = pd.read_csv(ok_csv, dtype=str)
    pairs = pd.read_csv(cross_map_csv, dtype=str)

    ik_slim = _slim(ik, IK_COL); ik_slim["side"]="IK"
    ok_slim = _slim(ok, OK_COL); ok_slim["side"]="OK"

    rows = []
    for _, p in pairs.iterrows():
        ik_pt, ok_pt = _norm_pt(p["ik_part_type"]), _norm_pt(p["ok_part_type"])
        A = ik_slim[ik_slim.part_type==ik_pt].set_index("key")
        B = ok_slim[ok_slim.part_type==ok_pt].set_index("key")
        keys = sorted(set(A.index) | set(B.index))
        for k in keys:
            a = A.loc[k] if k in A.index else None
            b = B.loc[k] if k in B.index else None

            def g(row, col, default=""):
                if row is None: return default
                return row[col] if col in row.index else default

            dtype  = g(a, "dtype",  g(b, "dtype",  ""))
            lookup = g(a, "lookup", g(b, "lookup", ""))

            rows.append(dict(
                pair_id      = f"{ik_pt}_{ok_pt}",
                ik_part_type = ik_pt,
                ok_part_type = ok_pt,
                key          = k,
                dtype        = dtype,
                lookup       = lookup,
                required_ik  = _to_bool(g(a, "required", False)),
                required_ok  = _to_bool(g(b, "required", False)),
                ik_slot      = g(a, "slot",  ""),
                ik_codec     = g(a, "codec", ""),
                ok_slot      = g(b, "slot",  ""),
                ok_codec     = g(b, "codec", ""),
            ))

    union = pd.DataFrame(rows, columns=[
        "pair_id","ik_part_type","ok_part_type","key","dtype","lookup",
        "required_ik","required_ok","ik_slot","ik_codec","ok_slot","ok_codec"
    ])
    union.to_csv(out_csv, index=False)
    return union
