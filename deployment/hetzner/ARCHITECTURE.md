# Hetzner Deep-Server 아키텍처 설계서

## 서버 정보
| 항목 | 값 |
|------|-----|
| IP | 5.161.112.248 |
| 이름 | deep-server |
| 위치 | Ashburn, VA (USA) |
| OS | Ubuntu 24.04 LTS |
| 사양 | CPX31 (4 vCPU / 8 GB RAM / 160 GB SSD) |

---

## 디렉토리 구조 (서버)

```
/root/
├── service_a/              # Group A: Freqtrade Service
│   ├── docker-compose.yml
│   ├── user_data/
│   │   ├── bot1/           # 사용자 1 봇
│   │   ├── bot2/           # 사용자 2 봇
│   │   ├── bot3/           # 사용자 3 봇
│   │   └── bot4/           # 사용자 4 봇 (선택)
│   └── .env
│
├── service_b/              # Group B: Personal Automation
│   ├── docker-compose.yml
│   ├── sports_analysis/    # 스포츠 분석 시스템
│   ├── naver_blog/         # 네이버 블로그 자동화
│   ├── tradingview/        # 트레이딩뷰 전략 수집기
│   └── .env
│
├── service_c/              # Group C: AI Trading Platform
│   ├── docker-compose.yml
│   ├── ai_platform/        # AI 자동매매 플랫폼
│   └── .env
│
├── shared/                 # 공유 리소스
│   ├── nginx/              # 리버스 프록시
│   └── monitoring/         # Prometheus + Grafana (선택)
│
└── master-compose.yml      # 전체 오케스트레이션
```

---

## 리소스 배분 전략

### 총 가용 리소스
- **RAM**: 8 GB (+ 2 GB Swap)
- **CPU**: 4 vCPU
- **Disk**: 160 GB SSD

### 그룹별 할당

| 그룹 | 서비스 | RAM 할당 | CPU 할당 | 우선순위 |
|------|--------|----------|----------|----------|
| **A** | Freqtrade (4봇) | 4 GB (1GB×4) | 2 vCPU | 높음 |
| **B** | Personal Automation | 1.5 GB | 1 vCPU | 중간 |
| **C** | AI Trading Platform | 2 GB | 1 vCPU | 높음 |
| **시스템** | OS + Docker | 0.5 GB | - | - |
| **합계** | - | **8 GB** | **4 vCPU** | - |

### Swap 설정
```
Swap Size: 2 GB
Swappiness: 10 (메모리 우선 사용)
```

---

## 네트워크 아키텍처

```
                    ┌─────────────────────────────────┐
                    │         외부 인터넷              │
                    └─────────────┬───────────────────┘
                                  │
                    ┌─────────────▼───────────────────┐
                    │      UFW Firewall               │
                    │  22(SSH), 80, 443, 8080-8089    │
                    └─────────────┬───────────────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  freqtrade_net  │    │  automation_net │    │  ai_trading_net │
│   (bridge)      │    │    (bridge)     │    │    (bridge)     │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ • ft_bot1:8080  │    │ • sports:5001   │    │ • ai_platform   │
│ • ft_bot2:8081  │    │ • naver:5002    │    │   :8090         │
│ • ft_bot3:8082  │    │ • tv_collect    │    │ • ai_db         │
│ • ft_bot4:8083  │    │   :5003         │    │   (internal)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
     완전 격리              완전 격리              완전 격리
```

---

## 포트 할당표

| 포트 | 서비스 | 그룹 | 용도 |
|------|--------|------|------|
| 22 | SSH | 시스템 | 원격 접속 |
| 80 | Nginx | 공유 | HTTP 리다이렉트 |
| 443 | Nginx | 공유 | HTTPS (선택) |
| **8080** | Freqtrade Bot 1 | A | FreqUI 웹 |
| **8081** | Freqtrade Bot 2 | A | FreqUI 웹 |
| **8082** | Freqtrade Bot 3 | A | FreqUI 웹 |
| **8083** | Freqtrade Bot 4 | A | FreqUI 웹 |
| **5001** | Sports Analysis | B | 스포츠 분석 API |
| **5002** | Naver Blog | B | 블로그 자동화 |
| **5003** | TradingView | B | 전략 수집기 |
| **8090** | AI Platform | C | AI 자동매매 |

---

## 보안 설정

### UFW 규칙
```bash
# 기본 정책
ufw default deny incoming
ufw default allow outgoing

# 필수 포트
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'

# Freqtrade (Group A)
ufw allow 8080:8083/tcp comment 'Freqtrade WebUI'

# Personal Automation (Group B)
ufw allow 5001:5003/tcp comment 'Automation Services'

# AI Platform (Group C)
ufw allow 8090/tcp comment 'AI Trading Platform'
```

### Fail2Ban 설정
- SSH 브루트포스 방지
- 5회 실패 시 10분 차단
- 반복 시 24시간 차단

---

## GitHub Actions 연동

### 워크플로우 구조
```
.github/workflows/
├── deploy-freqtrade.yml    # Group A 배포
├── deploy-automation.yml   # Group B 배포
├── deploy-ai-platform.yml  # Group C 배포
└── deploy-all.yml          # 전체 배포
```

### 필요한 Secrets
| Secret Name | 설명 |
|-------------|------|
| `HETZNER_SSH_KEY` | 서버 SSH 개인키 |
| `HETZNER_HOST` | 5.161.112.248 |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 알림용 |
| `TELEGRAM_CHAT_ID` | 텔레그램 채팅방 ID |

---

## 배포 순서

1. **서버 초기 설정** (`scripts/01-server-init.sh`)
   - 패키지 업데이트
   - Docker 설치
   - Swap 설정
   - 방화벽 설정

2. **디렉토리 생성** (`scripts/02-create-dirs.sh`)
   - 서비스 디렉토리 구조 생성
   - 권한 설정

3. **소스 업로드** (로컬에서 실행)
   - rsync로 각 그룹 폴더에 업로드

4. **서비스 시작** (`scripts/03-start-services.sh`)
   - Docker Compose로 전체 서비스 실행

---

## 모니터링 (선택)

### 헬스체크 엔드포인트
- `/health` - 각 서비스 상태
- `/metrics` - Prometheus 메트릭

### 알림 채널
- Telegram 봇으로 장애 알림
- 일일 상태 리포트 전송

---

## 롤백 전략

```bash
# 특정 그룹 롤백
cd ~/service_a && docker-compose down
git checkout HEAD~1
docker-compose up -d

# 전체 롤백
cd ~ && docker-compose -f master-compose.yml down
# 이전 버전으로 복원 후
docker-compose -f master-compose.yml up -d
```

---

**작성일**: 2025-12-27
**버전**: 1.0.0
