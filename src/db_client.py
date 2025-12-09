import os
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

class RDSClient:
    def __init__(self):
        # 1. DB URL 생성 (mysql+mysqlconnector 드라이버 사용)
        # 형식: mysql+driver://user:password@host:port/dbname
        db_user = os.getenv('DB_USER')
        db_password = os.getenv('DB_PASSWORD')
        db_host = os.getenv('DB_HOST')
        db_port = os.getenv('DB_PORT', 3306)
        db_name = os.getenv('DB_NAME')
        
        print("DB HOST:", db_host)
        print("DB USER:", db_user)
        print("DB PASSWORD:", db_password)
        print("DB NAME:", db_name)
        print("DB PORT:", db_port)


        # 특수문자가 비밀번호에 있을 경우 URL 인코딩 필요할 수 있음
        self.db_url = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

        try:
            # 2. 엔진 생성 (이때 풀이 자동으로 설정됨)
            self.engine = create_engine(
                self.db_url,
                pool_size=5,        # 풀 크기 설정
                max_overflow=10,    # 풀이 꽉 찼을 때 추가로 허용할 연결 수
                pool_recycle=3600,  # 연결 재사용 주기(초)
                echo=False          # 쿼리 로그 출력 여부
            )
            print("✅ DB Engine (Pool) 생성 완료")
        except Exception as e:
            print(f"❌ Engine 생성 중 오류 발생: {e}")
            self.engine = None

    def execute(self, query, params=None):
        """
        SQLAlchemy Engine을 사용하여 쿼리 실행.
        Context Manager(with)를 통해 연결의 획득/반납을 자동 처리.
        """
        if not self.engine:
            print("DB 엔진이 초기화되지 않았습니다.")
            return None

        result_data = None

        try:
            # 3. 연결 획득 (Pool에서 가져옴) 및 트랜잭션 시작
            with self.engine.connect() as connection:
                # 텍스트 쿼리를 실행 가능한 객체로 변환
                stmt = text(query)
                
                # 4. 쿼리 실행
                # params가 튜플/리스트라면 그대로, 딕셔너리라면 바인딩
                result = connection.execute(stmt, params or {})

                # 5. 결과 처리
                if result.returns_rows: # SELECT 문인 경우
                    # 딕셔너리 형태로 변환하여 리스트로 반환
                    result_data = [dict(row) for row in result.mappings()]
                else: # INSERT, UPDATE, DELETE 인 경우
                    connection.commit() # 변경사항 확정
                    result_data = result.rowcount

        except SQLAlchemyError as e:
            print(f"⚠️ 쿼리 실행 에러: {e}")
        
        # with 블록을 빠져나가면 connection.close()가 자동 호출되어 Pool로 반납됨

        return result_data
    
