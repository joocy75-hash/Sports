# 스포츠 분석 시스템 배포 가이드 (Group B)

## 1. 개요

이 문서는 **Group B (스포츠 분석 시스템)**의 배포 및 운영에 대한 가이드입니다.
현재 서울 서버(`141.164.55.245`)에서 운영 중이며, GitHub Actions를 통해 자동 배포됩니다.

## 2. 서버 정보

- **IP**: `141.164.55.245`
- **User**: `root`
- **Path**: `/root/service_b`
- **Services**:
  - `sports_frontend` (Port 5000)
  - `sports_analysis` (Port 5001)
  - `sports_db` (PostgreSQL)
  - `sports_redis` (Redis)

## 3. GitHub Actions 자동 배포

`main` 브랜치에 코드가 푸시되면 자동으로 배포가 시작됩니다.

### 3.1 워크플로우 파일

- `.github/workflows/deploy-group-b.yml`

### 3.2 필요한 Secrets

GitHub 저장소 Settings > Secrets and variables > Actions에 다음 항목이 등록되어 있어야 합니다.

| Secret Name | 설명 |
|-------------|------|
| `HETZNER_SSH_KEY` | 서버 접속용 SSH Private Key |
| `TELEGRAM_BOT_TOKEN` | 배포 알림용 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 배포 알림용 채팅 ID |

### 3.3 배포 과정

1. **코드 체크아웃**: 최신 코드를 가져옵니다.
2. **파일 전송**:
   - `docker-compose.yml` → `/root/service_b/`
   - Backend Code (`src/`, `*.py`) → `/root/service_b/sports_analysis/`
   - Frontend Code (`frontend/`) → `/root/service_b/frontend/`
3. **서비스 재배포**:
   - 서버에서 `docker compose up -d --build` 실행
   - Frontend 및 Backend 이미지가 새로 빌드되고 컨테이너가 교체됩니다.
4. **알림 전송**: 성공/실패 여부를 텔레그램으로 전송합니다.

## 4. 수동 배포 (비상시)

자동 배포가 실패하거나 긴급 수정이 필요한 경우 수동으로 배포할 수 있습니다.

```bash
# 1. 로컬에서 스크립트 실행 (전체 동기화 및 재시작)
./deployment/hetzner/scripts/manual_deploy_group_b.sh
```

*(참고: `manual_deploy_group_b.sh` 스크립트는 별도로 생성해야 함)*

또는 직접 서버에 접속하여:

```bash
ssh root@141.164.55.245
cd /root/service_b
git pull origin main  # (Git을 사용하는 경우)
docker compose up -d --build
```

## 5. 주요 명령어

```bash
# 로그 확인
docker logs -f sports_analysis
docker logs -f sports_frontend

# 컨테이너 상태 확인
docker compose ps

# 서비스 재시작
docker compose restart sports_analysis
```
