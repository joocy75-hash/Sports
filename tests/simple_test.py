#!/usr/bin/env python3
"""
간단한 API 테스트 스크립트
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_endpoint(name, url, method="GET", data=None):
    """단일 엔드포인트 테스트"""
    try:
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=10)
        else:
            print(f"❌ {name}: 지원하지 않는 메서드")
            return False
        
        if response.status_code == 200:
            print(f"✅ {name}: 성공 (상태: {response.status_code})")
            return True
        else:
            print(f"❌ {name}: 실패 (상태: {response.status_code})")
            print(f"   응답: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ {name}: 예외 발생 - {str(e)}")
        return False

def main():
    print("🔍 간단한 API 테스트 시작")
    print("=" * 50)
    
    tests = [
        ("Health Check", f"{BASE_URL}/health", "GET"),
        ("Games List", f"{BASE_URL}/api/v1/games/list", "GET"),
        ("Today Matches", f"{BASE_URL}/api/v1/matches/today", "GET"),
        ("Game Rounds", f"{BASE_URL}/api/v1/games/rounds", "GET"),
    ]
    
    passed = 0
    failed = 0
    
    for name, url, method in tests:
        if test_endpoint(name, url, method):
            passed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 50)
    print("📊 테스트 결과 요약")
    print(f"총 테스트: {passed + failed}")
    print(f"통과: {passed}")
    print(f"실패: {failed}")
    
    if failed == 0:
        print("\n🎉 모든 테스트 통과!")
        return True
    else:
        print(f"\n⚠️  {failed}개의 테스트가 실패했습니다.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)