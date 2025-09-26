# -*- coding: utf-8 -*-
# apply_category_to_part_master.py
# Cross_Map의 category를 part_master.csv에 반영

import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")
PM_PATH  = DATA_DIR / "part_master.csv"
CM_PATH  = DATA_DIR / "Cross_Map.csv"
BACKUP   = DATA_DIR / "part_master.backup.csv"

def main():
    if not PM_PATH.exists():
        raise SystemExit(f"not found: {PM_PATH}")
    if not CM_PATH.exists():
        raise SystemExit(f"not found: {CM_PATH}")

    pm = pd.read_csv(PM_PATH, dtype=str).fillna("")
    cm = pd.read_csv(CM_PATH, dtype=str).fillna("")

    # --- 컬럼 존재성 체크 (유연하게 처리)
    if "category" not in cm.columns:
        raise SystemExit("Cross_Map.csv에 'category' 컬럼이 필요합니다.")
    if "ik_part_type" not in cm.columns and "ok_code" not in cm.columns:
        raise SystemExit("Cross_Map.csv에 'ik_part_type' 또는 'ok_code' 키가 있어야 합니다.")

    # priority 없으면 0
    if "priority" not in cm.columns:
        cm["priority"] = 0
    else:
        cm["priority"] = pd.to_numeric(cm["priority"], errors="coerce").fillna(0).astype(int)

    # part_master 필수 컬럼 보정
    for col in ("site", "part_code"):
        if col not in pm.columns:
            raise SystemExit(f"part_master.csv에 '{col}' 컬럼이 필요합니다.")
    if "part_type" not in pm.columns:
        # 혹시 part_type이 없으면 간단 파생(필요시 너의 derive 로직으로 교체)
        # 예: V111-xxx... 에서 앞 4자리
        pm["part_type"] = pm["part_code"].str.extract(r"^(V\d{3})", expand=False).fillna("")

    # -------- 1) IK: ik_part_type 기준 매핑
    cat_ik = pd.DataFrame(columns=["ik_part_type","category","priority"])
    if "ik_part_type" in cm.columns:
        cat_ik = cm[["ik_part_type","category","priority"]].copy()
        # 같은 ik_part_type에 규칙 여러 개면 priority 높은 것만 남김
        cat_ik = (cat_ik.sort_values(["ik_part_type","priority"], ascending=[True,False])
                        .drop_duplicates(subset=["ik_part_type"], keep="first"))

    pm_ik = pm.query("site.str.upper() == 'IK'", engine="python").copy()
    if not pm_ik.empty and not cat_ik.empty:
        pm_ik = pm_ik.merge(cat_ik, how="left",
                            left_on="part_type", right_on="ik_part_type")
        pm_ik.drop(columns=["ik_part_type"], inplace=True, errors="ignore")
    else:
        pm_ik["category"] = pm_ik.get("category", "")

    # -------- 2) OK: ok_code 기준 매핑(선택)
    pm_ok = pm.query("site.str.upper() == 'OK'", engine="python").copy()
    if "ok_code" in cm.columns and not pm_ok.empty:
        cat_ok = cm[["ok_code","category","priority"]].copy()
        cat_ok = (cat_ok.sort_values(["ok_code","priority"], ascending=[True,False])
                        .drop_duplicates(subset=["ok_code"], keep="first"))
        # OK의 part_code가 Cross_Map의 ok_code와 직접 같다고 가정
        pm_ok = pm_ok.merge(cat_ok, how="left",
                            left_on="part_code", right_on="ok_code")
        pm_ok.drop(columns=["ok_code"], inplace=True, errors="ignore")
    else:
        pm_ok["category"] = pm_ok.get("category", "")

    # -------- 3) 그 외 사이트(있다면)는 일단 category 비워둠
    pm_else = pm[~pm.index.isin(pm_ik.index.union(pm_ok.index))].copy()
    pm_else["category"] = pm_else.get("category", "")

    # -------- 4) 합치기 + 우선 기존 category가 있었으면 덮어쓰기
    cols = list(pm.columns)
    if "category" not in cols:
        cols.append("category")

    merged = pd.concat([pm_ik, pm_ok, pm_else], ignore_index=True)[cols]

    # -------- 5) 백업 후 저장
    pm.to_csv(BACKUP, index=False)
    merged.to_csv(PM_PATH, index=False)
    print(f"[OK] category 반영 완료\n - backup: {BACKUP}\n - write : {PM_PATH}\n - rows  : {len(merged)}")

if __name__ == "__main__":
    main()
