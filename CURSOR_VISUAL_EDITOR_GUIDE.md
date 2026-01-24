# Cursor 2.2 비주얼 에디터 사용 가이드

> **Cursor 2.2**에서 새로 추가된 Visual Editor 기능을 활용하여 UI/UX를 시각적으로 편집하는 방법을 안내합니다.

---

## 🎨 Visual Editor란?

Visual Editor는 **코드 에디터, 디자인 도구, 브라우저 렌더링**이 하나의 창에서 통합된 개발 환경입니다.

**주요 특징:**
- ✅ DOM 트리 내 요소 드래그 앤 드롭으로 배치 수정
- ✅ React 컴포넌트 props/상태 제어
- ✅ 슬라이더, 색상 선택기로 스타일 조정
- ✅ 자연어 명령으로 코드 변경 적용
- ✅ 실시간 미리보기 및 코드 자동 반영

---

## 📋 사용 준비

### 1. 버전 확인

```bash
# Cursor 버전 확인
Cursor → About Cursor (Mac: Cmd + ,)
# 또는
Help → About

# 버전이 2.2 이상이어야 합니다
```

### 2. 프로젝트 준비

```bash
# 프론트엔드 개발 서버 실행
cd frontend
npm run dev

# 서버가 http://localhost:5173 에서 실행됨
```

### 3. Browser 탭 열기

1. Cursor 왼쪽 사이드바에서 **Browser** 탭 클릭
2. 또는 `Cmd/Ctrl + Shift + B` 단축키
3. Browser 창이 열리면 로컬 서버 URL 입력: `http://localhost:5173`

---

## 🚀 Visual Editor 활성화

### 방법 1: Browser 내에서 활성화

1. Browser 탭에서 페이지가 로드되면
2. 상단 툴바에서 **"Design"** 또는 **"Visual Editor"** 버튼 클릭
3. 또는 `Cmd/Ctrl + Shift + D` 단축키

### 방법 2: Inspector 패널 열기

1. Browser에서 페이지 요소를 **클릭**
2. 우측 또는 하단에 **Inspector 패널** 자동 표시
3. Inspector 패널에서 Visual Editor 모드 활성화

---

## 💡 주요 기능 사용법

### 1. 드래그 앤 드롭으로 요소 이동

**사용법:**
1. Browser에서 요소를 **선택**
2. DOM 트리에서 요소를 **드래그**하여 위치 변경
3. 레이아웃이 실시간으로 변경됨

**예시:**
```
Dashboard 페이지에서:
- 통계 카드 순서 변경
- 사이드바 위치 조정
- 그리드 레이아웃 재배치
```

### 2. 컴포넌트 Props/상태 제어

**React 컴포넌트의 경우:**

1. 컴포넌트를 **클릭**하여 선택
2. Inspector 패널에서 **Props** 섹션 확인
3. Props 값을 **토글**하거나 **수정**

**예시:**
```typescript
// Button 컴포넌트 선택 시
Props:
  - variant: primary | secondary | danger
  - size: sm | md | lg
  - disabled: true | false
  - loading: true | false

// Inspector에서 직접 변경하면 즉시 반영됨
```

### 3. 스타일 시각적 조정

**사용 가능한 컨트롤:**

| 컨트롤 | 기능 | 사용법 |
|--------|------|--------|
| **색상 선택기** | 배경색, 텍스트 색상 변경 | 색상 팔레트에서 선택 |
| **슬라이더** | padding, margin, font-size 조정 | 슬라이더로 값 변경 |
| **디자인 토큰** | CSS 변수 값 선택 | 드롭다운에서 토큰 선택 |
| **그림자** | box-shadow 조정 | 그림자 설정 패널 사용 |
| **투명도** | opacity 조정 | 슬라이더로 0-1 사이 값 |

**예시:**
```
1. MatchCard 컴포넌트 선택
2. Inspector에서 "Background Color" 클릭
3. 색상 선택기에서 --primary-500 선택
4. "Padding" 슬라이더를 16px로 조정
5. "Border Radius"를 12px로 설정
6. 변경사항 즉시 미리보기 확인
```

### 4. 자연어 명령으로 변경

**Point & Prompt 방식:**

1. **요소를 클릭**하여 선택
2. Inspector 패널 하단의 **프롬프트 입력창**에 명령 입력
3. Cursor AI가 명령을 해석하여 코드 변경

**명령 예시:**
```
"이 버튼을 빨간색 배경으로 바꿔줘"
"이 섹션의 간격을 줄여줘"
"이 카드에 그림자 효과 추가해줘"
"이 텍스트를 더 크게 만들어줘"
"이 컴포넌트를 모바일 반응형으로 만들어줘"
```

### 5. 변경사항 코드에 적용

**Apply 버튼:**

1. Visual Editor에서 스타일/레이아웃 조정 완료
2. Inspector 패널 하단의 **"Apply"** 또는 **"Apply Changes"** 버튼 클릭
3. 변경사항이 실제 코드 파일에 반영됨
4. Hot-reload로 브라우저에 즉시 반영

**주의사항:**
- 변경 전에 **Git 커밋** 권장 (변경사항 되돌리기 위해)
- 큰 변경은 **단계별로** 적용하는 것이 안전

---

## 🎯 실전 사용 예시

### 예시 1: Dashboard 스타일 개선

```
1. Browser에서 http://localhost:5173 접속
2. Visual Editor 모드 활성화
3. Dashboard 페이지의 통계 카드 선택
4. Inspector에서:
   - Background: glass morphism 효과 적용
   - Border: 1px solid rgba(255,255,255,0.1)
   - Shadow: var(--shadow-lg)
   - Hover 효과 추가
5. "Apply" 클릭하여 코드 반영
```

### 예시 2: 버튼 컴포넌트 개선

```
1. Button 컴포넌트 선택
2. Props 섹션에서:
   - variant: "primary" → "secondary" 변경
   - size: "md" → "lg" 변경
3. 스타일 섹션에서:
   - Border Radius: 8px → 12px
   - Padding: 12px → 16px
4. 자연어 명령: "hover 시 scale(1.05) 효과 추가"
5. "Apply" 클릭
```

### 예시 3: 반응형 레이아웃 조정

```
1. 전체 레이아웃 선택
2. 자연어 명령: "모바일 화면에서 사이드바를 숨기고 햄버거 메뉴로 변경해줘"
3. Cursor AI가 코드 수정
4. 변경사항 확인 후 "Apply"
```

---

## ⚙️ 단축키

| 기능 | Mac | Windows/Linux |
|------|-----|---------------|
| Browser 탭 열기 | `Cmd + Shift + B` | `Ctrl + Shift + B` |
| Visual Editor 활성화 | `Cmd + Shift + D` | `Ctrl + Shift + D` |
| Inspector 패널 토글 | `Cmd + I` | `Ctrl + I` |
| 요소 선택 모드 | `Cmd + Click` | `Ctrl + Click` |
| 변경사항 적용 | `Cmd + Enter` | `Ctrl + Enter` |

---

## 🐛 알려진 이슈 및 해결방법

### 1. 메뉴 패널 겹침 문제

**증상:** Visual Editor 모드 전환 시 툴바가 겹침

**해결:**
- Cursor 재시작
- Browser 탭 닫고 다시 열기
- Cursor 최신 버전으로 업데이트

### 2. 요소 클릭 시 새 채팅 생성

**증상:** 요소 클릭할 때마다 새 채팅이 열림

**해결:**
- Inspector 패널의 프롬프트 입력창 사용
- 기존 채팅에서 계속 작업

### 3. 성능 저하

**증상:** 큰 UI에서 느린 반응

**해결:**
- 작은 컴포넌트 단위로 작업
- 불필요한 요소 숨기기
- 개발 서버 최적화

### 4. 변경사항이 코드에 반영 안됨

**해결:**
- "Apply" 버튼 명시적으로 클릭
- 파일 저장 확인
- 개발 서버 재시작

---

## 💡 워크플로우 팁

### 1. 단계별 작업

```
✅ 좋은 예:
1. 색상 변경 → Apply
2. 간격 조정 → Apply
3. 애니메이션 추가 → Apply

❌ 나쁜 예:
1. 색상 + 간격 + 애니메이션 모두 변경 → Apply
(예상치 못한 변경 가능)
```

### 2. Git 커밋 전략

```bash
# Visual Editor 작업 전
git add .
git commit -m "작업 전 상태 저장"

# Visual Editor로 변경
# ...

# 변경 후
git diff  # 변경사항 확인
git add .
git commit -m "Visual Editor: Dashboard 스타일 개선"
```

### 3. 디자인 시스템 활용

```
✅ CSS 변수 사용:
- 색상: var(--primary-500)
- 간격: var(--space-4)
- 폰트: var(--text-lg)

❌ 하드코딩 피하기:
- 색상: #3B82F6
- 간격: 16px
```

### 4. 반응형 테스트

```
1. Browser에서 화면 크기 조정
2. 모바일 뷰 (375px) 확인
3. 태블릿 뷰 (768px) 확인
4. 데스크톱 뷰 (1920px) 확인
5. 각 뷰포트에서 스타일 조정
```

---

## 📚 추가 리소스

### 공식 문서
- [Cursor Visual Editor 공식 블로그](https://cursor.com/blog/browser-visual-editor)
- [Cursor 2.2 릴리즈 노트](https://cursor.com/en/changelog)

### 커뮤니티
- [Cursor 포럼](https://forum.cursor.com)
- [Reddit r/cursor](https://www.reddit.com/r/cursor)

---

## 🎓 실습 예제

### 프로젝트에 적용하기

```bash
# 1. 프론트엔드 서버 실행
cd frontend
npm run dev

# 2. Cursor에서 Browser 탭 열기
# 3. http://localhost:5173 접속
# 4. Visual Editor 활성화
# 5. Dashboard 페이지 개선 시작!
```

### 추천 작업 순서

1. **작은 컴포넌트부터** (Button, Card)
2. **레이아웃 조정** (Grid, Flexbox)
3. **전체 페이지 스타일** (Dashboard, Settings)
4. **반응형 디자인** (모바일 최적화)

---

**마지막 업데이트**: 2026-01-05  
**Cursor 버전**: 2.2 이상 필요
