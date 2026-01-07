# Hetzner Deep-Server Deployment Guide

이 디렉토리는 서비스를 3개의 그룹(Group A, B, C)으로 나누어 배포하기 위한 설정을 포함하고 있습니다.

## 그룹 구성

### Group A: Freqtrade Service (`service_a`)

- 4개의 독립적인 Freqtrade 봇 운영
- 포트: 8080, 8081, 8082, 8083
- 리소스: 각 봇당 1GB RAM, 0.5 CPU

### Group B: Personal Automation (`service_b`)

- 스포츠 분석 시스템 (Proto 14게임)
- 네이버 블로그 자동화
- 트레이딩뷰 전략 수집기
- 포트: 5001, 5002, 5003
- 리소스: 총 1.5GB RAM, 1 CPU

### Group C: AI Trading Platform (`service_c`)

- AI 기반 자동매매 플랫폼
- PostgreSQL DB + Redis + Celery Worker 포함
- 포트: 8090
- 리소스: 총 2GB RAM, 1 CPU

---

## 배포 방법

### 1. 서버 초기화 (최초 1회)

서버에 접속하여 초기화 스크립트를 실행합니다.

```bash
# 로컬에서 스크립트 전송
scp -r ./scripts root@<SERVER_IP>:/root/

# 서버에서 실행
ssh root@<SERVER_IP>
chmod +x /root/scripts/*.sh
/root/scripts/01-server-init.sh
/root/scripts/02-create-dirs.sh
```

### 2. 소스 코드 및 설정 업로드

각 그룹 디렉토리의 내용을 서버의 대응하는 디렉토리로 업로드합니다.

- `group_a_freqtrade/` -> `/root/service_a/`
- `group_b_automation/` -> `/root/service_b/`
- `group_c_ai_trading/` -> `/root/service_c/`
- `master-compose.yml` -> `/root/master-compose.yml`

### 3. 서비스 시작

```bash
/root/scripts/03-start-services.sh
```

또는 통합 관리를 위해 `master-compose.yml`을 사용할 수 있습니다:

```bash
docker compose -f /root/master-compose.yml up -d
```

---

## 주의 사항

- 각 그룹 폴더의 `.env.example`을 참고하여 `.env` 파일을 생성해야 합니다.
- Freqtrade 봇의 경우 `user_data/config.json` 파일이 각 봇 디렉토리에 존재해야 합니다.
- 스포츠 분석 시스템의 경우 `sports_analysis` 디렉토리에 소스 코드가 포함되어야 합니다.
