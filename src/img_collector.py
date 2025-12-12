from curl_cffi import requests
import time
import random
import pandas as pd
from tqdm import tqdm  # 진행률 바 라이브러리 추가

def crawl_musinsa_goods(category_code="001", max_pages=1000):
    """
    무신사 API를 통해 상품 ID와 썸네일 URL을 수집합니다.
    :param category_code: 수집할 카테고리 코드 (예: 001)
    :param max_pages: 수집할 최대 페이지 수
    :return: 수집된 데이터 리스트
    """
    
    collected_data = []
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.musinsa.com/",
        "Accept": "application/json"
    }

    print(f"🚀 크롤링 시작: 카테고리 {category_code}, 최대 {max_pages} 페이지")

    # tqdm을 사용하여 진행률 바 생성
    pbar = tqdm(range(1, max_pages + 1), unit="page")
    
    for page in pbar:
        # 진행 상황 텍스트 업데이트
        pbar.set_description(f"수집 중... Page {page}")

        params = {
            "gf": "M",
            "sortCode": "POPULAR",
            "category": category_code,
            "size": 60,
            "testGroup": "",
            "caller": "CATEGORY",
            "page": page,
            "seen": 0,
            "seenAds": ""
        }
        
        url = "https://api.musinsa.com/api2/dp/v1/plp/goods"

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                json_data = response.json()
                goods_list = json_data.get('data', {}).get('list', [])
                
                if not goods_list:
                    pbar.write(f"🛑 [Page {page}] 더 이상 상품이 없습니다. 수집을 종료합니다.")
                    break

                current_items = 0
                for item in goods_list:
                    item_info = {
                        "goodsNo": item.get("goodsNo"),
                        "thumbnail": item.get("thumbnail"),
                        "goodsName": item.get("goodsName")
                    }
                    collected_data.append(item_info)
                    current_items += 1
                
                # 우측에 수집된 총 개수 표시 업데이트
                pbar.set_postfix(total_collected=len(collected_data), last_count=current_items)

            else:
                pbar.write(f"⚠️ [Page {page}] 에러 발생: Status {response.status_code}")
                break

        except Exception as e:
            pbar.write(f"❌ [Page {page}] 요청 실패: {e}")
            break

        # 랜덤 딜레이
        time.sleep(random.uniform(0.2, 0.5))

    return collected_data



# --- 실행부 ---
if __name__ == "__main__":
    # 테스트를 위해 페이지 수 설정 (예: 10페이지)
    target_category = "001"
    target_pages = 1000
    
    result_list = crawl_musinsa_goods(category_code=target_category, max_pages=target_pages)

    print("\n" + "="*40)
    print(f"✅ 수집 완료 요약")
    print(f"- 대상 카테고리: {target_category}")
    print(f"- 총 수집 상품 수: {len(result_list)}개")
    print("="*40 + "\n")

    # 결과 샘플 확인
    if result_list:
        print("🔍 수집 데이터 샘플 (상위 3개):")
        for data in result_list[:3]:
            print(data)



            