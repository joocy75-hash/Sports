#!/usr/bin/env python3
"""
텔레그램 분석 알림 테스트 스크립트
"""

import asyncio
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from src.services.telegram_notifier import TelegramNotifier


async def test_basic_connection():
    """기본 연결 테스트"""
    print("\n" + "="*60)
    print("1️⃣ 텔레그램 연결 테스트")
    print("="*60)

    notifier = TelegramNotifier()

    if not notifier.enabled:
        print("❌ 텔레그램이 비활성화되어 있습니다.")
        print("💡 .env 파일에 다음을 설정하세요:")
        print("   TELEGRAM_BOT_TOKEN=your_token")
        print("   TELEGRAM_CHAT_ID=your_chat_id")
        return False

    test_msg = f"""
🧪 **텔레그램 연결 테스트**

✅ 봇이 정상적으로 작동하고 있습니다!
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

━━━━━━━━━━━━━━━━━━━━━
_베트맨 스포츠토토 AI 분석 시스템_
    """

    success = await notifier.send_message(test_msg)

    if success:
        print("✅ 연결 성공! 텔레그램 앱에서 메시지를 확인하세요.")
    else:
        print("❌ 메시지 전송 실패")

    return success


async def test_sample_analysis():
    """샘플 분석 결과 전송 테스트"""
    print("\n" + "="*60)
    print("2️⃣ 샘플 분석 결과 전송 테스트")
    print("="*60)

    notifier = TelegramNotifier()

    sample_msg = """
💎 **Top 3 Value Picks**
📅 2025-12-23

**1. 맨체스터 시티 vs 첼시**
🏆 Premier League | ⏰ 20:00
💎 **홈 승리**
🔢 신뢰도: 72.5%
📈 Edge: 12.3%
💰 추천 베팅: 4.2%
📊 배당: 홈 1.85 | 무 3.60 | 원정 4.50

**2. 레알 마드리드 vs 바르셀로나**
🏆 La Liga | ⏰ 21:00
💎 **홈 승리**
🔢 신뢰도: 68.5%
📈 Edge: 10.8%
💰 추천 베팅: 3.5%
📊 배당: 홈 2.10 | 무 3.40 | 원정 3.80

**3. 바이에른 뮌헨 vs 도르트문트**
🏆 Bundesliga | ⏰ 18:30
✅ **홈 승리**
🔢 신뢰도: 65.2%
📈 Edge: 8.5%
💰 추천 베팅: 2.8%
📊 배당: 홈 1.70 | 무 4.00 | 원정 5.50

━━━━━━━━━━━━━━━━━━━━━
_베트맨 스포츠토토 AI 분석 시스템_
    """

    success = await notifier.send_message(sample_msg)

    if success:
        print("✅ 샘플 분석 전송 성공!")
    else:
        print("❌ 전송 실패")

    await asyncio.sleep(2)

    return success


async def test_match_detail():
    """경기 상세 분석 샘플 전송"""
    print("\n" + "="*60)
    print("3️⃣ 경기 상세 분석 샘플 전송")
    print("="*60)

    notifier = TelegramNotifier()

    detail_msg = """
⚽ **경기 상세 분석**

**맨체스터 시티 vs 첼시**
🏆 Premier League
⏰ 2025-12-23 20:00

━━━━━━━━━━━━━━━━━━━━━

🤖 **AI 모델 예측**
🏠 홈 승리: 72.5%
🤝 무승부: 18.2%
✈️ 원정 승리: 9.3%

📊 **배당 (Pinnacle)**
홈: 1.85 | 무: 3.60 | 원정: 4.50

💡 **AI Fair Odds**
홈: 1.38 | 무: 5.49 | 원정: 10.75

💎 **추천: 홈 승리**
🔢 신뢰도: 72.5%
📈 Edge: 12.3%
💰 추천 베팅: 4.2%

📈 **최근 5경기 폼**
🏠 맨체스터 시티: W-W-W-D-W (13pts)
✈️ 첼시: W-L-W-D-L (7pts)

━━━━━━━━━━━━━━━━━━━━━
_베트맨 스포츠토토 AI 분석 시스템_
    """

    success = await notifier.send_message(detail_msg)

    if success:
        print("✅ 상세 분석 전송 성공!")
    else:
        print("❌ 전송 실패")

    return success


async def test_high_confidence_alert():
    """고신뢰도 알림 샘플"""
    print("\n" + "="*60)
    print("4️⃣ 고신뢰도 알림 샘플 전송")
    print("="*60)

    notifier = TelegramNotifier()

    alert_msg = """
🔒 **고신뢰도 픽 (70%+)**
📅 2025-12-23

⚽ **맨체스터 시티 vs 첼시**
📍 홈 승리 (72.5%)

⚽ **바이에른 뮌헨 vs 도르트문트**
📍 홈 승리 (71.2%)

⚽ **PSG vs 마르세유**
📍 홈 승리 (70.8%)

━━━━━━━━━━━━━━━━━━━━━
_베트맨 스포츠토토 AI 분석 시스템_
    """

    success = await notifier.send_message(alert_msg)

    if success:
        print("✅ 고신뢰도 알림 전송 성공!")
    else:
        print("❌ 전송 실패")

    return success


async def main():
    """전체 테스트 실행"""
    print("\n" + "="*60)
    print("📱 텔레그램 분석 알림 테스트")
    print("="*60)
    print()
    print("이 스크립트는 다음을 테스트합니다:")
    print("1. 텔레그램 봇 연결")
    print("2. 샘플 분석 결과 전송")
    print("3. 경기 상세 분석 전송")
    print("4. 고신뢰도 알림 전송")
    print()
    print("각 테스트 사이에 2초의 간격이 있습니다.")
    print()

    # 1. 연결 테스트
    connection_ok = await test_basic_connection()

    if not connection_ok:
        print("\n❌ 텔레그램 연결 실패. 테스트를 중단합니다.")
        return

    await asyncio.sleep(2)

    # 2. 샘플 분석
    await test_sample_analysis()
    await asyncio.sleep(2)

    # 3. 경기 상세
    await test_match_detail()
    await asyncio.sleep(2)

    # 4. 고신뢰도 알림
    await test_high_confidence_alert()

    print("\n" + "="*60)
    print("✅ 모든 테스트 완료!")
    print("="*60)
    print()
    print("📱 텔레그램 앱에서 다음 메시지들을 확인하세요:")
    print("   1. 연결 테스트 메시지")
    print("   2. Top 3 Value Picks")
    print("   3. 경기 상세 분석")
    print("   4. 고신뢰도 픽 알림")
    print()
    print("💡 실제 분석 결과를 전송하려면:")
    print("   python send_analysis_results.py --today")
    print()


if __name__ == "__main__":
    asyncio.run(main())
