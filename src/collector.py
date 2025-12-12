import os
import csv
import json
import time
import random
import re
from curl_cffi import requests
from bs4 import BeautifulSoup

# SQLAlchemy
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# 사용자의 DB Client 모듈 (같은 폴더에 db_client.py가 있어야 함)
from db_client import RDSClient

# ==========================================
# 1. 환경 설정 및 DB 초기화
# ==========================================
rds = RDSClient()

# 테이블 컬럼 정보 가져오기 (동적 쿼리 생성용)
cols_result = rds.execute("SHOW COLUMNS FROM product_bottom")
if not cols_result:
    print("❌ 테이블 정보를 가져오지 못했습니다. DB 연결을 확인하세요.")
    exit()

db_cols = [row['Field'] for row in cols_result]
placeholders = ", ".join([f":{col}" for col in db_cols])
# INSERT 구문 미리 생성
insert_sql = f"INSERT IGNORE INTO product_bottom ({', '.join(db_cols)}) VALUES ({placeholders})"

# ==========================================
# 2. CSV 파일 로드
# ==========================================
goods_ids = []
csv_filename = "musinsa_bottom_ids.csv"

try:
    with open(csv_filename, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader) # 헤더 건너뛰기
        for row in reader:
            if row:
                goods_ids.append(row[0])
except FileNotFoundError:
    print(f"❌ '{csv_filename}' 파일이 없습니다.")
    exit()

# ==========================================
# 3. 시작 위치 계산 (이어하기)
# ==========================================
cnt_result = rds.execute("SELECT COUNT(*) as cnt FROM product_top")
saved_count = cnt_result[0]['cnt'] if cnt_result else 0

start_index = 0 # 이미 저장된 개수만큼 건너뛰고 시작
total_count = cnt_result # 목표 수집 개수 (필요시 수정)

# 범위 보정
if total_count > len(goods_ids):
    total_count = len(goods_ids)

print(f"📊 전체 ID: {len(goods_ids)}개 / 이미 저장됨: {saved_count}개")
print(f"🚀 금일 작업 구간: {start_index}번부터 {total_count}번까지 (총 {total_count - start_index}개)")

# ==========================================
# 4. 헬퍼 함수 정의
# ==========================================

def create_session():
    """새로운 세션을 생성하고 헤더를 설정합니다."""
    s = requests.Session(impersonate="chrome")
    s.headers.update({
        "Referer": "https://www.musinsa.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    })
    return s

def smart_sleep():
    """
    [터보 모드] 빠르지만 기계적인 패턴은 피하는 대기 로직
    """
    prob = random.random() # 0.0 ~ 1.0 난수

    if prob < 0.90:  
        # [90%] 고속 주행: 0.6초 ~ 1.3초
        delay = random.uniform(0.2, 0.6)
        mode = "⚡빠름"
    elif prob < 0.99: 
        # [9%] 잠깐 숨고르기: 2초 ~ 3초
        delay = random.uniform(1.0, 1.6)
        mode = "🧘숨고르기"
    else: 
        # [1%] 아주 가끔 멍때리기: 4초 ~ 6초 (패턴 끊기용)
        delay = random.uniform(4.0, 5.0)
        mode = "☕잠깐휴식"
    
    print(f"   💤 [{mode}] {delay:.2f}초...", end="", flush=True)
    time.sleep(delay)

# ==========================================
# 5. 메인 크롤링 루프
# ==========================================
session = create_session()

for idx in range(start_index, total_count):
    gid = goods_ids[idx]

    # [대기] 스마트 슬립 적용
    smart_sleep()
    print() # 줄바꿈

    # [세션 관리] 40~60회마다 세션 물갈이 (추적 회피)
    if idx > start_index and idx % random.randint(40, 60) == 0:
        print("\n🔄 [System] 브라우저 세션 새로고침...")
        time.sleep(random.uniform(3, 5))
        session = create_session()

    print(f"[{idx+1}/{len(goods_ids)}] ID:{gid} 요청 중...", end=" ")

    try:
        url = f"https://www.musinsa.com/products/{gid}"
        
        # -------------------------------------------------------
        # STEP 1: 메인 페이지 요청 (Next.js 데이터 확보)
        # -------------------------------------------------------
        response = session.get(url, timeout=10)
        
        # HTTP 에러 핸들링
        if response.status_code != 200:
            print(f"⚠️ HTTP {response.status_code}", end=" ")
            if response.status_code in [429, 403]:
                print("\n🚨 [Warning] 차단 의심! 3분간 대기합니다.")
                time.sleep(180)
                session = create_session()
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        
        # 봇 차단 페이지 감지
        page_title = soup.title.get_text(strip=True) if soup.title else ""
        if any(k in page_title for k in ["Access Denied", "Just a moment", "Security Check"]):
            print(f"\n🚨 [CRITICAL] 봇 차단 화면 감지됨! 2분 대기 후 스킵합니다.")
            time.sleep(120)
            continue

        # __NEXT_DATA__ 추출
        next_data_tag = soup.find("script", {"id": "__NEXT_DATA__"})
        if not next_data_tag:
            print(f"⚠️ JSON 태그 없음", end=" ")
            continue
            
        try:
            raw_json = json.loads(next_data_tag.string)
        except json.JSONDecodeError:
            print(f"⚠️ JSON 디코딩 실패", end=" ")
            continue

        # -------------------------------------------------------
        # STEP 2: 상품 상세 데이터 위치 탐색
        # -------------------------------------------------------
        product_info = None
        page_props = raw_json.get("props", {}).get("pageProps", {})

        # 탐색 경로 1: props -> meta -> data (가장 최신 구조)
        if "meta" in page_props and "data" in page_props["meta"]:
            candidate = page_props["meta"]["data"]
            if str(candidate.get("goodsNo", "")) == str(gid):
                product_info = candidate

        # 탐색 경로 2: dehydratedState (구 구조)
        if not product_info:
            queries = page_props.get("dehydratedState", {}).get("queries", [])
            for query in queries:
                data_node = query.get("state", {}).get("data", {})
                if isinstance(data_node, dict):
                    # 여러 키 패턴 확인
                    if str(data_node.get("goodsNo", "")) == str(gid) or str(data_node.get("productNo", "")) == str(gid):
                        product_info = data_node; break
                    elif "product" in data_node and (str(data_node["product"].get("goodsNo", "")) == str(gid)):
                        product_info = data_node["product"]; break
                    elif "goods" in data_node and (str(data_node["goods"].get("goodsNo", "")) == str(gid)):
                        product_info = data_node["goods"]; break

        if not product_info:
            print(f"⚠️ 정보 매칭 실패", end=" ")
            continue

        # -------------------------------------------------------
        # STEP 3: 데이터 매핑
        # -------------------------------------------------------
        # 1) 상품명
        product_name = (product_info.get("goodsNm") or product_info.get("goodsName") or product_info.get("productName") or "")
        
        # 2) 브랜드
        brand_info = product_info.get("brandInfo", {})
        if isinstance(brand_info, dict) and "brandName" in brand_info:
            brand = brand_info["brandName"]
        else:
            brand = product_info.get("brandName", "") or product_info.get("brand", "")
        
        # 3) 가격
        price_info = product_info.get("goodsPrice") or product_info.get("price") or {}
        normal_price = price_info.get("normalPrice") or price_info.get("originPrice") or 0
        sale_price = price_info.get("salePrice") or price_info.get("price") or 0
        discount = price_info.get("discountRate", 0)

        # 4) 카테고리
        upper_category, lower_category = "", ""
        cat_obj = product_info.get("category")
        if isinstance(cat_obj, dict):
            upper_category = cat_obj.get("categoryDepth1Title", "")
            lower_category = cat_obj.get("categoryDepth2Title", "")
        if not upper_category:
            cats = product_info.get("categories", [])
            if cats:
                upper_category = cats[0].get("depth1Title", "")
                lower_category = cats[0].get("depth2Title", "")

        # 5) 성별
        sex_data = product_info.get("sex")
        gender = 0
        if isinstance(sex_data, list):
            if "남성" in sex_data and "여성" in sex_data: gender = 0
            elif "남성" in sex_data: gender = 1
            elif "여성" in sex_data: gender = 2
        else:
            if sex_data in ["M", "MALE", "남성"]: gender = 1
            elif sex_data in ["F", "FEMALE", "여성"]: gender = 2

        # 6) 통계 (리뷰, 평점, 좋아요)
        stat_info = (product_info.get("goodsReview") or product_info.get("goodsCount") or product_info.get("stat") or {})
        review_cnt = stat_info.get("totalCount") or stat_info.get("reviewCount") or 0
        rating = float(stat_info.get("satisfactionScore") or stat_info.get("reviewAverage") or 0.0)
        like_cnt = (product_info.get("goodsCount", {}).get("likeCount") or product_info.get("stat", {}).get("likeCount") or 0)
        cumulative = (product_info.get("cumulativeSales") or str(stat_info.get("purchaseCount", "")) or "")

        # -------------------------------------------------------
        # STEP 4: 스타일 태그 (API 요청 방식)
        # -------------------------------------------------------
        tags_list = []
        try:
            # API 요청 전 아주 짧은 딜레이 (기계적 연속성 방지)
            time.sleep(random.uniform(0.1, 0.3))
            
            tag_api_url = f"https://goods-detail.musinsa.com/api2/goods/{gid}/tags"
            tag_response = session.get(tag_api_url, timeout=5)
            
            if tag_response.status_code == 200:
                tag_json = tag_response.json()
                if "data" in tag_json and "tags" in tag_json["data"]:
                    tags_list = tag_json["data"]["tags"]
            else:
                # 404 등은 태그가 없는 상품일 수 있으므로 조용히 처리
                pass

        except Exception as e:
            print(f"(태그Skip)", end=" ")

        final_tags_str = ','.join(tags_list)

        # 수집 상태 출력
        if final_tags_str:
            print(f"✅ 태그({len(tags_list)})", end=" ")
        else:
            print(f"⚠️ 태그없음", end=" ")

        # -------------------------------------------------------
        # STEP 5: DB 저장
        # -------------------------------------------------------
        size_json = "[]"
        fit_season_dict = {"핏": [], "계절감": []} 
        fit_json = json.dumps(fit_season_dict, ensure_ascii=False)

        # 파라미터 매핑
        params = {
            "product_id": gid,
            "product_name": product_name,
            "brand": brand,
            "original_price": normal_price,
            "sale_price": sale_price,
            "upper_category": upper_category,
            "lower_category": lower_category,
            "gender": gender,
            "rating": rating,
            "wish_count": like_cnt,
            "review_count": review_cnt,
            "size_info": size_json,
            "discount_rate": discount,
            "fit_season": fit_json,
            "cumulative_sales": cumulative,
            "style": final_tags_str 
        }

        # 쿼리 실행
        rds.execute(insert_sql, params)
        print(f"-> 저장완료")

    except Exception as e:
        print(f"\n❌ 에러 발생: {e}")
        time.sleep(5) # 에러 시 잠시 대기

print("\n🎉 모든 작업이 완료되었습니다!")