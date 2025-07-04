FROM python:3.11-slim

# 시스템 패키지 업데이트 및 필요한 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

EXPOSE 8501
WORKDIR /app

# Python 의존성 설치
COPY requirements.txt ./requirements.txt
RUN pip3 install --upgrade pip && pip3 install -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# Streamlit 설정
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# 헬스체크 추가
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Streamlit 애플리케이션 실행
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
