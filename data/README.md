# 📂 Data Directory 설명 (Code-Bridge-System)

본 디렉토리는 **익산(V-Code) ↔ 옥천(KM-Code) 부품 코드 통합 시스템**을 위한 원본 데이터, 룩업 테이블, 파싱 및 매칭 결과 파일을 포함합니다.  
아래는 각 파일의 역할, 생성 경로, 데이터 흐름에서의 위치를 정리한 내용입니다.

---

## 🗂 원본 스키마 정의
| 파일명 | 설명 | 생성/사용 경로 |
|--------|------|----------------|
| **codeSchema_IK** | 익산(V-Code) 11자리 코드의 자리수별 속성과 정의를 정리한 스키마 | 수동 관리 (기준 정의) |
| **codeSchema_OK** | 옥천(KM-Code) 11자리 코드의 자리수별 속성과 정의를 정리한 스키마 | 수동 관리 (기준 정의) |
| **union_schema** | IK/OK 스키마를 통합한 참조표. 자리수별 속성 비교, 공통/상이 속성 확인에 활용 | codeSchema_IK, codeSchema_OK를 기반으로 수동 생성 |

---

## 🗂 Lookup 테이블 (속성별 코드표)
부품군 코드 해석에 필요한 세부 속성 정의 파일들입니다.  
각 테이블은 **공통 코드(common)** + **part_type별 전용 코드(spec)** 로 구성됩니다.

| 파일명 | 설명 | 생성/사용 경로 |
|--------|------|----------------|
| **material_lookup** | 재질(Material) 코드 → 라벨 매핑 | 수동 관리 |
| **material_lookup_ori** | material_lookup의 원본 버전 (이후 가공/정제 전 단계) | 수동 관리 |
| **surface_lookup** | 표면 처리(Surface) 코드표 | 수동 관리 |
| **grade_lookup** | 강도·등급(Grade) 코드표 | 수동 관리 |
| **seal_lookup** | 실(Seal) 코드표 | 수동 관리 |
| **designation_lookup** | 규격/명칭(Designation) 코드표 | 수동 관리 |
| **screw_tolerance_lookup** | 나사 공차(Screw tolerance) 코드표 | 수동 관리 |
| **type_assembly_lookup** | 조립 유형(Type of assembly) 코드표 | 수동 관리 |

---

## 🗂 매핑 규칙 및 마스터 데이터
| 파일명 | 설명 | 생성/사용 경로 |
|--------|------|----------------|
| **Cross_Map** | 익산 part_type(+조건) ↔ 옥천 KM-Code를 1:1 매칭한 규칙표 | 수동 관리, 매칭 로직의 핵심 |
| **part_master** | site(익산/옥천), part_type별 기본 카탈로그. 11자리 품번이 없는 항목도 포함 | 수동 관리 |

---

## 🗂 파싱 및 매칭 결과
| 파일명 | 설명 | 생성/사용 경로 |
|--------|------|----------------|
| **parsed_parts** | `parse_vcode.py` 실행 결과. part_master의 품번을 파싱해 부품군과 가능한 코드 목록을 생성 | part_master → parse_vcode.py |
| **matched_parts** | `match_iksan_okc.py` 실행 결과. parsed_parts + Cross_Map을 Join하여 최종 매칭 결과를 생성. `match_flag`(`OK` / `NO_MATCH`) 포함 | parsed_parts + Cross_Map → match_iksan_okc.py |

---

## 🔄 데이터 처리 흐름
```mermaid
flowchart TD
    A[part_master.csv] -->|parse_vcode.py| B[parsed_parts.csv]
    B --> D[matched_parts.csv]
    C[Cross_Map.csv] --> D

    subgraph Lookup_Tables
        L1[material_lookup]
        L2[surface_lookup]
        L3[grade_lookup]
        L4[seal_lookup]
        L5[designation_lookup]
        L6[screw_tolerance_lookup]
        L7[type_assembly_lookup]
    end

    D --> E[Streamlit UI]
    L1 & L2 & L3 & L4 & L5 & L6 & L7 --> E
