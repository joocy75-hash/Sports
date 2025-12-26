# Proto 14게임 AI 분석 시스템 Dockerfile
# 스포츠 분석 자동화 (축구 승무패 + 농구 승5패)

FROM python:3.11-slim

LABEL maintainer="mr.joo"
LABEL description="Proto 14게임 AI 분석 시스템 - 5개 AI 앙상블"
LABEL version="3.1.0"

# ============================================
# 환경 변수
# ============================================
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Seoul

WORKDIR /app

# ============================================
# 시스템 패키지 설치 (Playwright 의존성)
# ============================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Playwright Chromium 브라우저 의존성
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    # 기타 유틸리티
    curl \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# ============================================
# Python 패키지 설치 (캐시 최적화)
# ============================================
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright 브라우저 설치 (베트맨 크롤러용)
RUN playwright install chromium && \
    playwright install-deps chromium

# ============================================
# 애플리케이션 코드 복사
# ============================================
# 소스 코드
COPY src/ ./src/

# 메인 실행 파일들
COPY auto_sports_notifier.py .
COPY auto_telegram_bot.py .
COPY basketball_w5l_analyzer.py .
COPY basketball_w5l_notifier.py .
COPY collect_and_notify.py .

# 설정 파일
COPY alembic.ini ./
COPY alembic/ ./alembic/

# 상태 저장 디렉토리 생성
RUN mkdir -p .state logs

# ============================================
# 헬스체크
# ============================================
HEALTHCHECK --interval=60s --timeout=30s --start-period=30s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# ============================================
# 기본 실행 명령
# ============================================
# 스케줄러 모드: 6시간마다 자동 분석 및 텔레그램 알림
CMD ["python", "auto_sports_notifier.py", "--schedule", "--interval", "6"]
