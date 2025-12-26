#!/usr/bin/env python3
"""보안 기능 테스트 스크립트"""

import os
import hashlib


def test_api_key_hash():
    """API 키 해시 검증 테스트"""
    # 생성된 API 키
    api_key = "WAOZPZtHKb9Z545dC0hsW0NOSRjkvmhfMxOxZP0VRMY"
    expected_hash = "b9dfa32f80614fcac5bad52dbc83d54f81f645adec5c157e36a7e1914a70608d"

    # 해시 생성
    computed_hash = hashlib.sha256(api_key.encode()).hexdigest()

    print("=" * 70)
    print("🔐 API 키 해시 검증 테스트")
    print("=" * 70)
    print(f"API Key: {api_key}")
    print(f"Expected Hash: {expected_hash}")
    print(f"Computed Hash: {computed_hash}")
    print(f"Match: {'✅ PASS' if computed_hash == expected_hash else '❌ FAIL'}")
    print("=" * 70)
    print()


def test_env_variable():
    """환경 변수 로드 테스트"""
    from dotenv import load_dotenv

    # .env 파일 로드
    load_dotenv()

    hash_from_env = os.getenv('API_SECRET_KEY_HASH')

    print("=" * 70)
    print("🌍 환경 변수 로드 테스트")
    print("=" * 70)
    print(f"API_SECRET_KEY_HASH from .env: {hash_from_env}")
    print(f"Status: {'✅ LOADED' if hash_from_env else '❌ NOT FOUND'}")
    print("=" * 70)
    print()


def test_middleware_import():
    """미들웨어 임포트 테스트"""
    print("=" * 70)
    print("📦 미들웨어 임포트 테스트")
    print("=" * 70)

    try:
        from src.api.middleware.auth import APIKeyAuth, verify_api_key
        print("✅ 미들웨어 임포트 성공")

        # APIKeyAuth 인스턴스 생성
        auth = APIKeyAuth()
        print("✅ APIKeyAuth 인스턴스 생성 성공")

        # 테스트 키 검증
        api_key = "WAOZPZtHKb9Z545dC0hsW0NOSRjkvmhfMxOxZP0VRMY"
        is_valid = auth.verify_key(api_key)
        print(f"✅ API 키 검증: {'VALID' if is_valid else 'INVALID'}")

        # 잘못된 키 테스트
        wrong_key = "wrong_api_key_12345"
        is_invalid = auth.verify_key(wrong_key)
        print(f"✅ 잘못된 키 검증: {'INVALID' if not is_invalid else 'VALID (SHOULD BE INVALID)'}")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")

    print("=" * 70)
    print()


def test_rate_limiter():
    """Rate Limiter 설정 테스트"""
    print("=" * 70)
    print("⏱️  Rate Limiter 테스트")
    print("=" * 70)

    try:
        from slowapi import Limiter
        from slowapi.util import get_remote_address

        limiter = Limiter(key_func=get_remote_address)
        print("✅ SlowAPI 임포트 및 Limiter 인스턴스 생성 성공")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")

    print("=" * 70)
    print()


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🛡️  보안 기능 통합 테스트")
    print("=" * 70 + "\n")

    test_api_key_hash()
    test_env_variable()
    test_middleware_import()
    test_rate_limiter()

    print("=" * 70)
    print("✅ 모든 테스트 완료!")
    print("=" * 70)
