import os
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

class RDSClient:
    def __init__(self):
        # 1. DB URL 생성 (mysql+mysqlconnector 드라이버 사용)
        db_user = os.getenv('DB_USER')
        db_password = os.getenv('DB_PASSWORD')
        db_host = os.getenv('DB_HOST')
        db_port = os.getenv('DB_PORT', 3306)
        db_name = os.getenv('DB_NAME')

        # 특수문자가 비밀번호에 있을 경우 URL 인코딩 필요할 수 있음
        self.db_url = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

        try:
            # 2. 엔진 생성
            self.engine = create_engine(
                self.db_url,
                pool_size=5,
                max_overflow=10,
                pool_recycle=3600,
                echo=False
            )
            print("✅ DB Engine (Pool) 생성 완료")
        except Exception as e:
            print(f"❌ Engine 생성 중 오류 발생: {e}")
            self.engine = None

    def execute(self, query, params=None):
        """
        단일 쿼리 실행 및 단일 커밋 (기존 함수)
        """
        if not self.engine:
            print("DB 엔진이 초기화되지 않았습니다.")
            return None

        result_data = None

        try:
            with self.engine.connect() as connection:
                stmt = text(query)
                result = connection.execute(stmt, params or {})

                if result.returns_rows:
                    result_data = [dict(row) for row in result.mappings()]
                else:
                    connection.commit()
                    result_data = result.rowcount

        except SQLAlchemyError as e:
            print(f"⚠️ 쿼리 실행 에러: {e}")
        
        return result_data
    
    # ⭐️ 추가된 배치 삽입 함수
    def execute_batch(self, query, params_list):
        """
        대량의 데이터를 효율적으로 삽입하기 위한 배치 삽입 함수.
        하나의 트랜잭션과 하나의 execute 호출로 여러 행을 처리합니다.

        Args:
            query (str): 삽입 쿼리 (예: INSERT INTO table (a, b) VALUES (:a, :b))
            params_list (list): 바인딩할 파라미터 딕셔너리들의 리스트.
                                (예: [{'a': 1, 'b': 10}, {'a': 2, 'b': 20}, ...])
        
        Returns:
            int: 영향을 받은 총 행의 개수 (성공 시) 또는 None (실패 시)
        """
        if not self.engine:
            print("DB 엔진이 초기화되지 않았습니다.")
            return None
        
        if not params_list:
            print("삽입할 데이터(params_list)가 비어 있습니다.")
            return 0

        total_rows = 0
        
        try:
            # 1. 연결 획득 및 트랜잭션 시작
            with self.engine.connect() as connection:
                stmt = text(query)
                
                # 2. execute 호출 시 파라미터 리스트를 전달하여 배치 실행
                result = connection.execute(stmt, params_list)
                
                # 3. 한 번의 커밋으로 모든 변경사항 확정
                connection.commit()
                
                total_rows = result.rowcount
                print(f"✅ 배치 삽입 성공! 총 {total_rows}개 행 삽입.")
                
        except SQLAlchemyError as e:
            print(f"❌ 배치 쿼리 실행 에러: {e}")
            # 배치 삽입 실패 시 자동으로 롤백됩니다.
            return None
            
        return total_rows

# (클래스 정의 끝)