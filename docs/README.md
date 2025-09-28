# 📖 프로젝트 문서 (VCode-Bridge-System)

본 문서는 **익산(V-Code) ↔ 옥천(KM-Code) 통합 조회 시스템**의 전체 구조를 한눈에 볼 수 있도록 정리한 자료입니다.  
데이터 스키마, 처리 흐름, UI 구조, 배포 방식까지 포함합니다.

---

## 🏗 전체 아키텍처
```mermaid
flowchart TD
    subgraph Data
        A1[codeSchema_IK.csv]
        A2[codeSchema_OK.csv]
        A3[union_schema.csv]
        A4[Lookup CSVs 7종]
        A5[Cross_Map.csv]
        A6[part_master.csv]
    end

    subgraph Processing
        P1[parse_vcode.py]
        P2[parsed_parts.csv]
        P3[match_iksan_okc.py]
        P4[matched_parts.csv]
    end

    subgraph App
        U1[Streamlit UI]
        U2[검색 패널]
        U3[속성 비교 테이블]
        U4[이미지 뷰어]
        U5[다운로드 & 통계 위젯]
    end

    A6 --> P1 --> P2 --> P3 --> P4
    A5 --> P3
    A1 & A2 & A3 & A4 --> U1
    P4 --> U1
    U1 --> U2
    U1 --> U3
    U1 --> U4
    U1 --> U5
