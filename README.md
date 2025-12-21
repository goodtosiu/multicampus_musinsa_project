# 👕 무신사 토탈아웃핏 추천 시스템 (Musinsa Total Outfit Recommendation)

무신사의 방대한 상품 데이터를 분석하여 사용자의 패션 성향(16가지 페르소나)을 진단하고, 텍스트와 이미지 임베딩을 결합한 하이브리드 추천 엔진을 통해 최적의 토탈 아웃핏을 제안하는 프로젝트입니다.

# 🚀 주요 기능 (Key Features)

Fashion Persona Test: 간단한 설문을 통해 사용자를 16가지 패션 유형 중 하나로 분류합니다.

Hybrid Embedding Engine:

S-BERT: 상품명, 카테고리, 브랜드 정보를 768차원의 밀집 벡터로 변환하여 문맥적 의미를 파악합니다.

CLIP: 상품 이미지를 분석하여 시각적 특징(색상, 패턴, 실루엣 등)을 벡터화합니다.

Outfit Expansion: 배정된 페르소나의 대표 아웃핏 5종을 기준으로, 전체 상품군(약 5만 개) 중 가장 유사도가 높은 아이템들을 실시간으로 매칭합니다.

High-Performance DB: 제3정규화(3NF)가 적용된 스키마와 Redis 캐싱을 통해 대량의 벡터 연산을 지연 없이 처리합니다.

# 🛠 기술 스택 (Tech Stack)

Language: Python 3.9+

Database: MySQL 8.0+ (Normalized 3NF)

Cache: Redis (Vector & Session Caching)

AI/ML: Sentence-Transformers (S-BERT), OpenAI CLIP, NumPy, Scikit-learn

Tools: DBML, Docker

# 📊 데이터베이스 설계 (Database Design)

데이터 중복을 최소화하고 무결성을 유지하기 위해 **제3정규화(3NF)**를 적용했습니다.

### ERD 구조 (DBML)
https://dbdiagram.io/d/musinsa-693cfc52e877c63074ad5427

categories: 상/하위 카테고리 간의 이행적 함수 종속 제거

brands: 브랜드 메타데이터(설명, URL 등) 중복 저장 방지

products: 핵심 수치 데이터 및 임베딩 벡터 저장 (Covering Index 최적화)

product_styles: 다중 스타일 태그를 별도 행으로 분리 (1NF 준수)

persona_items: 페르소나별 대표 아이템 매핑 정보 관리

# 🧠 추천 알고리즘 원리 (Recommendation Logic)

1. 하이브리드 임베딩 (Hybrid Embedding)

각 상품은 다음 두 가지 모델을 통해 벡터화됩니다.

Natural Language (S-BERT): 상품의 텍스트 메타데이터를 기반으로 의미론적 유사성을 계산합니다.

Visual Features (CLIP): 이미지 데이터를 기반으로 시각적 스타일의 유사성을 계산합니다.

2. 코사인 유사도 연산 (Cosine Similarity)

선정된 대표 아웃핏 벡터 $A$와 후보 상품 벡터 $B$ 사이의 유사도는 다음과 같이 계산됩니다.

$$\text{Similarity}(A, B) = \cos(\theta) = \frac{A \cdot B}{\|A\| \|B\|}$$

3. 데이터 파이프라인

사용자 페르소나 결정 및 대표 아웃핏 로드.

MySQL에서 카테고리 및 필터링 조건을 만족하는 후보군(5만 행) 추출.

Redis에서 해당 상품들의 임베딩 벡터를 고속 로드.

NumPy를 이용한 벡터 연산을 통해 유사도 상위 50개 상품 선정 및 추천.

⚡ 성능 최적화 (Performance Tuning)

Covering Index: (category_id, rating, wish_count) 복합 인덱스를 구성하여 테이블 접근 없이 인덱스 스캔만으로 5만 건의 데이터를 즉시 인출합니다.

Lateral Join: 각 카테고리별로 대표 상품 N개를 추출할 때 전체 정렬 대신 인덱스 기반의 효율적인 조회를 수행합니다.

In-Memory Caching: 빈번하게 조회되는 임베딩 벡터를 Redis에 적재하여 MySQL I/O 부하를 80% 이상 감소시켰습니다.

Data Pre-processing: cumulative_sales 등 문자열 데이터를 INT 타입으로 정규화하여 정렬 연산 속도를 개선했습니다.

# 📂 프로젝트 구조 (Project Structure)


이 프로젝트는 무신사 크롤링 데이터를 기반으로 한 교육 및 포트폴리오 목적으로 제작되었습니다.
