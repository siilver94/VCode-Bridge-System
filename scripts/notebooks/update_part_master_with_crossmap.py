# -*- coding: utf-8 -*-
# update_part_master_with_crossmap.py
# Cross_Map.csv의 category/ok_code 등을 part_master.csv에 반영

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

    # CSV 읽기
    pm = pd.read_csv(PM_PATH, dtype=str).fillna("")
    cm = pd.read_csv(CM_PATH, dtype=str).fillna("")

    # part_master에 필수 컬럼 확인
    for col in ("site", "part_code", "part_type"):
        if col not in pm.columns:
            raise SystemExit(f"part_master.csv에 '{col}' 컬럼이 필요합니다.")

    # Cross_Map에 필요한 컬럼 확인
    if "ik_part_type" not in cm.columns or "category" not in cm.columns:
        raise SystemExit("Cross_Map.csv에는 'ik_part_type'와 'category' 컬럼이 필요합니다.")

    # priority 없으면 0
    if "priority" not in cm.columns:
        cm["priority"] = 0
    else:
        cm["priority"] = pd.to_numeric(cm["priority"], errors="coerce").fillna(0).astype(int)

    # 같은 ik_part_type이 여러 행이면 priority 높은 것만 남김
    cm_best = (cm.sort_values(["ik_part_type", "priority"], ascending=[True, False])
                  .drop_duplicates(subset=["ik_part_type"], keep="first"))

    # IK 사이트 기준으로 category 매핑
    pm_ik = pm.query("site.str.upper() == 'IK'", engine="python").copy()
    pm_ok = pm.query("site.str.upper() == 'OK'", engine="python").copy()
    pm_else = pm[~pm.index.isin(pm_ik.index.union(pm_ok.index))].copy()

    if not pm_ik.empty:
        pm_ik = pm_ik.merge(cm_best[["ik_part_type","category"]], 
                            how="left", left_on="part_type", right_on="ik_part_type")
        pm_ik.drop(columns=["ik_part_type"], inplace=True, errors="ignore")
    else:
        pm_ik["category"] = pm_ik.get("category", "")

    # OK 쪽은 일단 category 공백으로 두고 필요시 Cross_Map ok_code로 매핑 로직 추가 가능
    pm_ok["category"] = pm_ok.get("category", "")

    pm_else["category"] = pm_else.get("category", "")

    # 합치기
    merged = pd.concat([pm_ik, pm_ok, pm_else], ignore_index=True)

    # 기존 파일 백업 후 저장
    pm.to_csv(BACKUP, index=False)
    merged.to_csv(PM_PATH, index=False)
    print(f"[OK] part_master 업데이트 완료")
    print(f"- 백업: {BACKUP}")
    print(f"- 반영: {PM_PATH}")
    print(f"- 총 {len(merged)} 행")

if __name__ == "__main__":
    main()
