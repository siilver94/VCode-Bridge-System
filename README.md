# SPF(Standard Parts Finder)

## 📌 프로젝트 개요
익산(V-Code)과 옥천(KM-Code) 두 체계로 운용되어 온 부품 코드 관리 방식을 **하나의 통합 조회 시스템**으로 구현한 프로젝트입니다.  
부품군마다 상이한 11자리 코드 체계와 속성(재질, 표면, 등급, 실 등)을 자동 매칭하고, 검색과 동시에 속성 및 이미지를 확인할 수 있습니다.

---

## 🚩 문제 정의
- 동일 11자리 코드지만, **부품군별 의미와 코드표가 모두 상이**함  
- 익산에는 있고 옥천에는 없는 속성(예: 실 코드) 또는 그 반대 속성이 존재  
- 매번 Excel/PDF로 수작업 검색 → 시간 소요 및 오류 발생  

---

## 🎯 목표
- 익산 ↔ 옥천 **품번 상호 매칭**
- 속성(재질, 실, 길이 등) 및 이미지 동시 확인
- 매칭 실패 시 **NO_MATCH** 알림
- 데이터 품질 관리(UNKNOWN, NO_SCHEMA, NO_MATCH 로그 생성)

---

## 🗂 데이터 구성
### 스키마 정의
- **codeSchema_IK.csv** : 익산(V-Code) 자리수·속성 정의  
- **codeSchema_OK.csv** : 옥천(KM-Code) 자리수·속성 정의  
- **union_schema.csv** : IK/OK 통합 참조표  

### Lookup CSV (7종)
- **material_lookup.csv** : 재질(Material) 코드표  
- **surface_lookup.csv** : 표면(Surface) 코드표  
- **grade_lookup.csv** : 강도·등급(Grade) 코드표  
- **seal_lookup.csv** : 실(Seal) 코드표  
- **designation_lookup.csv** : 규격/명칭(Designation) 코드표  
- **screw_tolerance_lookup.csv** : 나사 공차(Screw tolerance) 코드표  
- **type_assembly_lookup.csv** : 조립 유형(Type of assembly) 코드표  

### 매핑 규칙 및 마스터 데이터
- **Cross_Map.csv** : 익산 part_type ↔ 옥천 KM-Code 1:1 규칙  
- **part_master.csv** : 사이트별 part_type 카탈로그  

### 파싱 및 매칭 결과
- **parsed_parts.csv** : `parse_vcode.py` 실행 결과. part_master를 파싱한 코드 목록  
- **matched_parts.csv** : `match_iksan_okc.py` 실행 결과. Cross_Map과 Join하여 최종 매칭 결과. `match_flag`(`OK` / `NO_MATCH`) 포함  

### 이미지
- **images/IK/** : 익산 품번별 이미지 (개별 또는 접두 공통)  
- **images/OK/** : 옥천 품번별 이미지 (개별 또는 접두 공통)  

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
