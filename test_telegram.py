#!/usr/bin/env python3
"""텔레그램 테스트 알림"""

import asyncio
import os
from datetime import datetime

# 환경 변수 로드
from dotenv import load_dotenv
load_dotenv()

from src.services.telegram_bot import TelegramBot, TelegramNotifier


async def send_test_notification():
    """테스트 알림 전송"""

    bot = TelegramBot()
    notifier = TelegramNotifier(bot)

    print("=" * 60)
    print("📱 텔레그램 테스트 알림 전송")
    print("=" * 60)
    print()

    # 1. 기본 연결 테스트
    print("1️⃣ 기본 연결 테스트...")
    success = await bot.test_connection()
    if success:
        print("✅ 텔레그램 연결 성공!")
    else:
        print("❌ 텔레그램 연결 실패!")
        return

    print()
    await asyncio.sleep(2)

    # 2. 프로토 분석 결과 예시 (실제 알림 포맷)
    print("2️⃣ 프로토 분석 결과 예시 알림...")

    marking_text = """프로토 승무패 2024001회 AI 분석 결과
분석 시각: 2024-12-23 14:35:00

[01] 맨체스터 시티 vs 첼시
     → 1 (홈승) (65.2%)
     홈승 예상 (65.2%), AI 합의도 100%

[02] 레알 마드리드 vs 바르셀로나 [복수]
     → 1 (홈승), X (무)
     홈승 예상 (48.5%), 이변 신호: 확률 분포 애매함 (1위: 48.5%, 2위: 32.1%)

[03] 아스날 vs 리버풀
     → 1 (홈승) (55.2%)
     홈승 예상 (55.2%), AI 합의도 80%

[04] 바이에른 뮌헨 vs 도르트문트 [복수]
     → 1 (홈승), X (무)
     이변 신호: 모델 간 의견 불일치 (표준편차 22.3%)

[05] 유벤투스 vs 나폴리
     → 1 (홈승) (58.7%)
     홈승 예상 (58.7%), AI 합의도 85%

[06] PSG vs 마르세유
     → 1 (홈승) (72.4%)
     홈승 예상 (72.4%), AI 합의도 100%

[07] 토트넘 vs 웨스트햄 [복수]
     → 1 (홈승), 2 (원정승)
     이변 신호: 폼-예측 상충, 확률 분포 애매함

[08] 첼시 vs 뉴캐슬
     → 1 (홈승) (60.1%)
     홈승 예상 (60.1%), AI 합의도 90%

[09] 인터 밀란 vs AC 밀란 [복수]
     → X (무승부), 2 (원정승)
     이변 신호: 모델 불일치, 랭킹 불일치

[10] 아틀레티코 vs 세비야
     → 1 (홈승) (63.5%)
     홈승 예상 (63.5%), AI 합의도 95%

[11] 라이프치히 vs 레버쿠젠
     → 2 (원정승) (52.3%)
     원정승 예상 (52.3%), AI 합의도 75%

[12] 맨체스터 유나이티드 vs 에버튼
     → 1 (홈승) (68.9%)
     홈승 예상 (68.9%), AI 합의도 100%

[13] 로마 vs 라치오
     → 1 (홈승) (56.4%)
     홈승 예상 (56.4%), AI 합의도 80%

[14] 발렌시아 vs 빌바오
     → X (무승부) (45.2%)
     무승부 예상 (45.2%), AI 합의도 70%

────────────────────────────────────────
고신뢰 경기: 10개
복수 베팅 경기: 4개
평균 AI 합의도: 86.4%
추천 전략: 소량 복수
전략 근거: 4개 경기 복수 베팅으로 안정성 확보
============================================================"""

    success = await notifier.notify_proto_round_analyzed(
        round_id="2024001",
        game_type="승무패",
        marking_text=marking_text,
        high_confidence_count=10,
        upset_count=4,
        strategy="소량 복수"
    )

    if success:
        print("✅ 프로토 분석 결과 알림 전송 성공!")
    else:
        print("❌ 알림 전송 실패!")

    print()
    await asyncio.sleep(2)

    # 3. 에러 알림 예시
    print("3️⃣ 에러 알림 예시...")
    success = await notifier.notify_error(
        error_type="테스트 에러",
        error_message="이것은 테스트 에러 메시지입니다"
    )

    if success:
        print("✅ 에러 알림 전송 성공!")
    else:
        print("❌ 알림 전송 실패!")

    print()
    print("=" * 60)
    print("✅ 모든 테스트 알림 전송 완료!")
    print("=" * 60)
    print()
    print("📱 텔레그램 앱에서 다음 메시지들을 확인하세요:")
    print("   1. 연결 테스트 메시지")
    print("   2. 프로토 14경기 분석 결과 (실제 알림 포맷)")
    print("   3. 에러 알림 예시")
    print()


if __name__ == "__main__":
    asyncio.run(send_test_notification())
