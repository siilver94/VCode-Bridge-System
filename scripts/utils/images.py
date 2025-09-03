# utils/images.py
from pathlib import Path
import re
from typing import List, Union
import streamlit as st

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}

def _natural_key(p: Union[str, Path]):
    s = Path(p).stem
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]

@st.cache_data(show_spinner=False)
def find_images(
    part_code: str,
    site: str,
    base_dir: Union[str, Path] = "images",
    max_n: int = 5,
) -> List[Path]:
    part_code = (part_code or "").strip()  # 공백 제거
    site = (site or "").strip()
    base = Path(base_dir)
    candidates: List[Path] = []

    # 1) 폴더형(있으면 우선)
    folder = base / site / part_code
    if folder.exists() and folder.is_dir():
        for p in sorted(folder.iterdir(), key=_natural_key):
            if p.suffix.lower() in IMAGE_EXTS:
                candidates.append(p)

    # 2) 파일형: images/<SITE>/<PART_CODE>_*.{ext}
    if len(candidates) < max_n:
        pattern_dir = base / site
        if pattern_dir.exists():
            # 확장자별로 글롭
            for ext in IMAGE_EXTS:
                for p in sorted(pattern_dir.glob(f"{part_code}_*{ext}"), key=_natural_key):
                    candidates.append(p)

    # 중복 제거 & 상한
    uniq, seen = [], set()
    for p in candidates:
        if p not in seen and p.exists():
            uniq.append(p)
            seen.add(p)
        if len(uniq) >= max_n:
            break

    return uniq
