#!/usr/bin/env python3
"""
API 연결 테스트 스크립트
"""

import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import get_settings


async def test_api_connections():
    """API 연결 테스트"""
    print("🔌 API 연결 테스트 시작...")
    
    try:
        # 설정 로드
        settings = get_settings()
        print(f"✅ 설정 로드 성공")
        print(f"   - Provider: {settings.provider}")
        print(f"   - API Football Key: {'설정됨' if settings.api_football_key else '설정 안됨'}")
        print(f"   - The Odds API Key: {'설정됨' if settings.the_odds_api_key else '설정 안됨'}")
        print(f"   - Telegram Bot Token: {'설정됨' if settings.telegram_bot_token else '설정 안됨'}")
        
        # API 클라이언트 테스트
        print("\n📡 API 클라이언트 테스트:")
        
        # 1. API-Football 클라이언트 테스트
        try:
            from src.clients.api_football import APIFootballClient
            client = APIFootballClient(settings.api_football_key)
            print("   ✅ API-Football 클라이언트 임포트 성공")
            
            # 간단한 API 호출 테스트 (실제 호출은 하지 않음)
            if settings.api_football_key:
                print("   ⚠️  실제 API 호출은 API 키 필요 (테스트 생략)")
            else:
                print("   ⚠️  API-Football 키가 설정되지 않음")
                
        except ImportError as e:
            print(f"   ❌ API-Football 클라이언트 임포트 실패: {e}")
        except Exception as e:
            print(f"   ⚠️  API-Football 클라이언트 오류: {e}")
        
        # 2. The Odds API 클라이언트 테스트
        try:
            from src.clients.the_odds_api import TheOddsAPIClient
            client = TheOddsAPIClient(settings.the_odds_api_key)
            print("   ✅ The Odds API 클라이언트 임포트 성공")
            
            if settings.the_odds_api_key:
                print("   ⚠️  실제 API 호출은 API 키 필요 (테스트 생략)")
            else:
                print("   ⚠️  The Odds API 키가 설정되지 않음")
                
        except ImportError as e:
            print(f"   ❌ The Odds API 클라이언트 임포트 실패: {e}")
        except Exception as e:
            print(f"   ⚠️  The Odds API 클라이언트 오류: {e}")
        
        # 3. Telegram Bot 테스트
        try:
            from telegram import Bot
            print("   ✅ Telegram 라이브러리 임포트 성공")
            
            if settings.telegram_bot_token:
                # 실제 연결 테스트
                bot = Bot(token=settings.telegram_bot_token)
                me = await bot.get_me()
                print(f"   ✅ Telegram Bot 연결 성공: @{me.username}")
            else:
                print("   ⚠️  Telegram Bot 토큰이 설정되지 않음")
                
        except ImportError as e:
            print(f"   ❌ Telegram 라이브러리 임포트 실패: {e}")
        except Exception as e:
            print(f"   ⚠️  Telegram Bot 연결 오류: {e}")
        
        # 4. 데이터베이스 연결 테스트
        try:
            from src.db.session import get_session
            print("   ✅ 데이터베이스 세션 임포트 성공")
            
            # 실제 연결 테스트
            async with get_session() as session:
                # 간단한 쿼리 실행
                from sqlalchemy import text
                result = await session.execute(text("SELECT 1"))
                test_result = result.scalar()
                if test_result == 1:
                    print("   ✅ 데이터베이스 연결 성공")
                else:
                    print("   ❌ 데이터베이스 연결 테스트 실패")
                    
        except ImportError as e:
            print(f"   ❌ 데이터베이스 모듈 임포트 실패: {e}")
        except Exception as e:
            print(f"   ⚠️  데이터베이스 연결 오류: {e}")
        
        print("\n📊 요약:")
        print("1. 필수 API 키 확인:")
        print(f"   - API-Football: {'✅ 설정됨' if settings.api_football_key else '❌ 설정 안됨'}")
        print(f"   - The Odds API: {'✅ 설정됨' if settings.the_odds_api_key else '❌ 설정 안됨'}")
        print(f"   - Telegram Bot: {'✅ 설정됨' if settings.telegram_bot_token else '❌ 설정 안됨'}")
        
        print("\n2. 다음 단계:")
        if not settings.api_football_key:
            print("   - API-Football 키를 .env 파일에 설정하세요")
        if not settings.the_odds_api_key:
            print("   - The Odds API 키를 .env 파일에 설정하세요")
        if not settings.telegram_bot_token:
            print("   - Telegram Bot 토큰을 .env 파일에 설정하세요")
        
        if settings.api_football_key and settings.the_odds_api_key:
            print("   ✅ 모든 필수 API 키가 설정되어 있습니다!")
            print("   다음으로 샘플 데이터를 생성하고 시스템을 테스트하세요.")
        
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """메인 함수"""
    print("🔍 API 연결 테스트 스크립트")
    print("=" * 50)
    
    await test_api_connections()
    
    print("\n" + "=" * 50)
    print("테스트 완료!")


if __name__ == "__main__":
    asyncio.run(main())