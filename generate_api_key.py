#!/usr/bin/env python3
"""
API Key Generator for Sports Analysis System

보안을 위한 안전한 API 키 생성 도구
"""

import secrets
import hashlib
import sys


def generate_api_key(length: int = 32) -> str:
    """
    안전한 랜덤 API 키 생성

    Args:
        length: 키 길이 (기본 32)

    Returns:
        URL-safe base64 인코딩된 랜덤 문자열
    """
    return secrets.token_urlsafe(length)


def hash_api_key(api_key: str) -> str:
    """
    API 키의 SHA-256 해시 생성

    Args:
        api_key: 원본 API 키

    Returns:
        SHA-256 해시 (hex)
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def main():
    """메인 실행 함수"""
    print("=" * 70)
    print("🔐 Sports Analysis System - API Key Generator")
    print("=" * 70)
    print()

    # 키 생성
    api_key = generate_api_key()
    api_key_hash = hash_api_key(api_key)

    # 출력
    print("✅ API Key Generated Successfully!")
    print()
    print("📋 Step 1: Save this API key securely (you won't see it again):")
    print("-" * 70)
    print(f"   {api_key}")
    print("-" * 70)
    print()
    print("📝 Step 2: Add this hash to your .env file:")
    print("-" * 70)
    print(f"   API_SECRET_KEY_HASH={api_key_hash}")
    print("-" * 70)
    print()
    print("🔑 Step 3: Use the API key (from Step 1) in requests:")
    print("-" * 70)
    print(f'   Authorization: Bearer {api_key}')
    print("-" * 70)
    print()
    print("⚠️  IMPORTANT:")
    print("   - Do NOT commit the API key to Git")
    print("   - Only commit the hash (API_SECRET_KEY_HASH)")
    print("   - Share the key securely with authorized users only")
    print()
    print("=" * 70)

    # .env 파일 업데이트 제안
    print()
    update = input("Do you want to automatically update .env file? (y/N): ")
    if update.lower() == 'y':
        try:
            with open('.env', 'r') as f:
                env_content = f.read()

            # 기존 API_SECRET_KEY_HASH 체크
            if 'API_SECRET_KEY_HASH=' in env_content:
                confirm = input("⚠️  API_SECRET_KEY_HASH already exists. Replace? (y/N): ")
                if confirm.lower() != 'y':
                    print("Cancelled.")
                    return

                # 기존 값 교체
                import re
                env_content = re.sub(
                    r'API_SECRET_KEY_HASH=.*',
                    f'API_SECRET_KEY_HASH={api_key_hash}',
                    env_content
                )
            else:
                # 새로 추가
                env_content += f'\n# API 보안\nAPI_SECRET_KEY_HASH={api_key_hash}\n'

            # 파일 저장
            with open('.env', 'w') as f:
                f.write(env_content)

            print("✅ .env file updated successfully!")
            print()
            print("🔄 Next steps:")
            print("   1. Restart your server")
            print("   2. Test authentication with the new API key")
            print(f"   3. Update frontend/mobile apps with new key: {api_key}")

        except FileNotFoundError:
            print("❌ .env file not found. Please create it first.")
        except Exception as e:
            print(f"❌ Error updating .env: {e}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Cancelled by user.")
        sys.exit(0)
