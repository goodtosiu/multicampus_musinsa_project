import sys
import os
import numpy as np
from flask import Flask, render_template

# 상위 폴더(src)를 모듈 경로에 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.db_client import RDSClient
from src.redis_client import RedisClient

app = Flask(__name__)

# DB 및 Redis 클라이언트 초기화
db = RDSClient()
redis_conn = RedisClient()

def cosine_similarity(v1, v2):
    """코사인 유사도 계산 함수"""
    if v1 is None or v2 is None:
        return 0.0
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    
    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0
        
    return np.dot(v1, v2) / (norm_v1 * norm_v2)

def get_weighted_similarity(target_vecs, candidate_vecs):
    """
    5가지 요소에 대해 각각 코사인 유사도를 구하고 0.2씩 가중 평균
    """
    weights = 0.2
    total_score = 0.0
    
    # 5가지 키: image_emb, brand_info_emb, lower_cat_emb, brand_cat_emb, name_emb
    keys = target_vecs.keys()
    
    for key in keys:
        sim = cosine_similarity(target_vecs[key], candidate_vecs[key])
        total_score += (sim * weights)
        
    return total_score

@app.route('/')
def index():
    # 1. '올드머니' 페르소나의 카테고리별 대표 아이템 선정
    # 3NF 스키마 활용: products + categories + brands + persona_items 조인
    persona_query = """
        SELECT 
            p.product_id, p.product_name, p.img_url, 
            c.upper_category, c.lower_category, c.category_id,
            b.korea_name as brand_name
        FROM persona_items pi
        JOIN products p ON pi.product_id = p.product_id
        JOIN categories c ON p.category_id = c.category_id
        JOIN brands b ON p.brand_id = b.brand_id
        WHERE pi.persona = '올드머니'
        AND c.upper_category IN ('상의', '하의', '신발', '아우터')
        GROUP BY c.upper_category
    """
    
    rep_items = db.execute(persona_query)
    
    final_recommendations = {} # 카테고리별 결과 저장용

    # 2. 각 대표 아이템에 대해 유사 상품 추천 로직 수행
    for rep_item in rep_items:
        category = rep_item['upper_category']
        rep_id = rep_item['product_id']
        target_vectors = redis_conn.get_product_vectors(rep_id)
        
        if not target_vectors:
            print(f"대표 아이템({rep_id})의 벡터가 Redis에 없습니다.")
            continue

        # 2-1. 같은 카테고리(upper_category)의 후보군 상품 조회 (자기 자신 제외)
        candidate_query = """
            SELECT 
                p.product_id, p.product_name, p.img_url, 
                p.sale_price, b.korea_name as brand_name
            FROM products p
            JOIN categories c ON p.category_id = c.category_id
            JOIN brands b ON p.brand_id = b.brand_id
            WHERE c.upper_category = :category
            AND p.product_id != :rep_id
            LIMIT 1000 
        """ 
        # 성능상 1000개만 가져온다고 가정 (실제로는 배치 처리 필요)
        candidates = db.execute(candidate_query, {'category': category, 'rep_id': rep_id})
        
        scored_candidates = []

        # 2-2. 후보군과의 유사도 계산
        for cand in candidates:
            cand_id = cand['product_id']
            cand_vectors = redis_conn.get_product_vectors(cand_id)
            
            if cand_vectors:
                # 5가지 요소 가중 평균 유사도 계산
                score = get_weighted_similarity(target_vectors, cand_vectors)
                cand['similarity_score'] = round(score * 100, 2) # 퍼센트로 변환
                scored_candidates.append(cand)
        
        # 2-3. 점수 높은 순 정렬 및 Top 5 추출
        scored_candidates.sort(key=lambda x: x['similarity_score'], reverse=True)
        top_5 = scored_candidates[:5]
        
        # 결과 저장
        final_recommendations[category] = {
            'representative': rep_item,
            'recommendations': top_5
        }

    return render_template('index.html', data=final_recommendations)

if __name__ == '__main__':
    app.run(debug=True, port=5000)