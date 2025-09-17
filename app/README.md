# Code-Bridge-System • UI 안내

Streamlit 기반 UI. 익산(IK, V-Code) ⇄ 옥천(OK, KM-Code) 품번과 속성을 쌍방향으로 조회하고 비교한다.

## 핵심 기능
- 품번 검색: IK 또는 OK 11자리 입력 → 대응 품번과 속성 즉시 표시
- 속성 비교: IK ⇄ OK 속성 테이블 동시 표시
- 양방향 선택: IK 기준 선택 또는 OK 기준 선택을 전환
- 이미지 뷰어: 품번당 1–5장 슬라이드
- 결과 다운로드: CSV 또는 Excel
- 통계 위젯: 검색 수, 매칭 성공/실패 수
- 매칭 실패 표시: `NO_MATCH` 배지

## 데이터 의존 파일
- `data/part_master.csv`
- `data/Cross_Map.csv`
- `data/parsed_parts.csv`  ← `parse_vcode.py` 산출
- `data/matched_parts.csv` ← `match_iksan_okc.py` 산출
- Lookup 7종: `material_*.csv`, `surface_*.csv`, `grade_*.csv`, `seal_*.csv`, `designation_*.csv`, `screw_tolerance_*.csv`, `type_assembly_*.csv`
- 스키마: `codeSchema_IK.csv`, `codeSchema_OK.csv`

## 이미지 배치 규칙

images/
IK/
V111_1.jpg, V111_2.jpg ...
V11_1.jpg, V11_2.jpg ... # V111, V112, V113 등 공통이미지는 접두 V11 사용
OK/
K12345678901_1.jpg ...

우선순위: 개별 품번 이미지 > 접두 공통 이미지. 최대 5장까지 순서대로 렌더링.

## 설치
```bash
python -V           # 3.10+ 권장
pip install -r requirements.txt
