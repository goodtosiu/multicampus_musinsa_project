import redis
import json
import numpy as np
import os
from dotenv import load_dotenv

load_dotenv()

class RedisClient:
    def __init__(self):
        self.host = os.getenv('REDIS_HOST', 'localhost')
        self.port = int(os.getenv('REDIS_PORT', 6379))
        self.db = int(os.getenv('REDIS_DB', 0))
        
        try:
            self.client = redis.Redis(
                host=self.host, 
                port=self.port, 
                db=self.db, 
                decode_responses=True # 문자열로 자동 디코딩
            )
            self.client.ping()
            print("✅ Redis 연결 성공")
        except redis.ConnectionError:
            print("❌ Redis 연결 실패")
            self.client = None

    def get_product_vectors(self, product_id):
        """
        Redis에서 특정 상품의 5가지 임베딩 벡터를 모두 가져옵니다.
        Key 구조 예시: product:{product_id}:vectors -> Hash Field에 각 벡터 저장
        """
        if not self.client:
            return None
        
        key = f"product:{product_id}:vectors"
        # 5가지 벡터 필드명 (임의 지정)
        fields = ['image_emb', 'brand_info_emb', 'lower_cat_emb', 'brand_cat_emb', 'name_emb']
        
        try:
            # HMGET으로 한 번에 조회
            data = self.client.hmget(key, fields)
            
            # 데이터가 없으면 None 반환
            if not any(data):
                return None
            
            # JSON 문자열을 Numpy array로 변환
            vectors = {}
            for i, field in enumerate(fields):
                if data[i]:
                    vectors[field] = np.array(json.loads(data[i]))
                else:
                    # 벡터가 누락된 경우 영벡터 처리 (에러 방지)
                    vectors[field] = np.zeros(768) 
            
            return vectors
            
        except Exception as e:
            print(f"⚠️ Redis 조회 오류 (ID: {product_id}): {e}")
            return None