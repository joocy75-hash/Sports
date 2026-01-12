# Cursor 앱 업데이트 오류 해결 방법

**오류**: "Cannot update while running on a read-only volume"

## 문제 원인
macOS Sierra 이후로 Downloads 폴더에서 직접 실행된 앱은 읽기 전용 볼륨로 간주되어 업데이트가 불가능합니다.

## 해결 방법

### 방법 1: Applications 폴더로 이동 (권장)

1. **Cursor 앱 종료**
   - 완전히 종료 (Cmd + Q 또는 Dock에서 우클릭 → Quit)

2. **Applications 폴더로 이동**
   ```bash
   # 터미널에서 실행
   sudo mv ~/Downloads/Cursor.app /Applications/
   ```
   
   또는 수동으로:
   - Finder에서 `~/Downloads/Cursor.app` 찾기
   - 드래그하여 `/Applications` 폴더로 이동

3. **검역 속성 제거 (필요한 경우)**
   ```bash
   sudo xattr -rd com.apple.quarantine /Applications/Cursor.app
   ```

4. **Cursor 재실행**
   - Applications 폴더에서 Cursor 실행

### 방법 2: 터미널에서 직접 실행

```bash
# 1. Cursor 앱 위치 확인
ls -la ~/Downloads/Cursor.app 2>/dev/null

# 2. Applications로 이동 (Cursor 종료 후)
sudo mv ~/Downloads/Cursor.app /Applications/Cursor.app

# 3. 권한 확인
chmod +x /Applications/Cursor.app/Contents/MacOS/Cursor

# 4. 검역 속성 제거 (필요시)
sudo xattr -rd com.apple.quarantine /Applications/Cursor.app
```

### 방법 3: 완전히 삭제 후 재설치

1. Cursor 완전히 종료
2. Downloads 폴더의 Cursor.app 삭제
3. [Cursor 공식 웹사이트](https://cursor.sh)에서 최신 버전 다운로드
4. 다운로드 후 **즉시 Applications 폴더로 이동**
5. Applications 폴더에서 실행

## 확인 방법

```bash
# Cursor가 Applications 폴더에 있는지 확인
ls -la /Applications/ | grep -i cursor

# 실행 경로 확인
which cursor
```

## 주의사항

- **Cursor 실행 중에는 이동하지 마세요** (먼저 완전히 종료)
- Applications 폴더로 이동 후에는 Downloads 폴더의 앱은 삭제해도 됩니다
- 이동 후 Dock의 아이콘을 Applications 폴더의 새 위치로 업데이트해야 할 수 있습니다

## 추가 팁

- Applications 폴더에 앱을 두면 자동 업데이트가 정상 작동합니다
- 시스템 설정에서 자동 업데이트를 활성화할 수 있습니다


