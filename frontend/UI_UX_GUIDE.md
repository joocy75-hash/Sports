# UI/UX 개발 가이드

이 가이드는 Cursor에서 프론트엔드 UI/UX를 효율적으로 개발하는 방법을 안내합니다.

## 🎨 Cursor에서 UI/UX 작업하기

### 1. 실시간 미리보기

```bash
# 프론트엔드 개발 서버 실행
cd frontend
npm run dev

# 브라우저에서 http://localhost:5173 자동 열림
```

**Cursor 팁:**
- `Cmd + Click` (Mac) 또는 `Ctrl + Click` (Windows)로 URL 클릭
- 코드 수정 시 자동 새로고침 (Hot Module Replacement)

### 2. 컴포넌트 개발 워크플로우

#### 단계별 개발

1. **컴포넌트 생성**
   ```bash
   # Cursor AI에게 요청
   "src/components/common/NewComponent.tsx 파일 생성해줘"
   ```

2. **스타일 작성**
   ```bash
   # CSS 파일 자동 생성
   "NewComponent.css 파일도 만들어줘"
   ```

3. **실시간 확인**
   - 브라우저에서 즉시 확인
   - 개발자 도구로 스타일 디버깅

### 3. 디자인 시스템 활용

#### CSS 변수 사용

```css
/* variables.css에 정의된 변수 사용 */
.my-component {
  background: var(--bg-primary);
  color: var(--text-primary);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  box-shadow: var(--shadow-md);
}
```

#### 테마 전환

```typescript
// 다크/라이트 테마 자동 적용
<div data-theme="dark">
  {/* 다크 테마 스타일 자동 적용 */}
</div>
```

### 4. Cursor AI 활용 팁

#### 컴포넌트 생성 요청

```
"Dashboard 페이지에 통계 카드 3개 추가해줘
- 승률 통계
- 적중률 통계  
- 수익률 통계
각각 다른 색상으로 (primary, success, warning)"
```

#### 스타일 개선 요청

```
"MatchCard 컴포넌트 스타일을 더 모던하게 개선해줘
- glass morphism 효과 추가
- hover 시 glow 효과
- 애니메이션 추가"
```

#### 반응형 디자인 요청

```
"모든 페이지를 모바일 반응형으로 만들어줘
- 768px 이하에서 사이드바 숨기기
- 카드 레이아웃을 1열로 변경
- 폰트 크기 조정"
```

## 🛠️ 유용한 Cursor 기능

### 1. 코드 생성 (Cmd/Ctrl + K)

```
"새로운 차트 컴포넌트 만들어줘
- Recharts 사용
- 확률 분포를 파이 차트로 표시
- 애니메이션 추가"
```

### 2. 코드 수정 (Cmd/Ctrl + L)

컴포넌트 선택 후:
```
"이 컴포넌트에 다크 모드 지원 추가해줘"
"이 버튼에 로딩 상태 표시 추가해줘"
```

### 3. 파일 검색 (Cmd/Ctrl + P)

- `variables.css` - 색상/스타일 변수 확인
- `Button.tsx` - 컴포넌트 참고
- `globals.css` - 전역 스타일 확인

## 📐 디자인 시스템 구조

```
frontend/src/
├── styles/
│   ├── variables.css      # 디자인 토큰 (색상, 간격, 폰트)
│   ├── globals.css        # 전역 스타일
│   └── themes/
│       └── light.css      # 라이트 테마
├── components/
│   ├── common/            # 공통 컴포넌트
│   │   ├── Button.tsx
│   │   ├── Card.tsx
│   │   └── Badge.tsx
│   └── charts/            # 차트 컴포넌트
└── pages/                 # 페이지 컴포넌트
```

## 🎯 컴포넌트 개발 체크리스트

새 컴포넌트 생성 시:

- [ ] TypeScript 타입 정의
- [ ] CSS 변수 사용 (하드코딩 금지)
- [ ] 다크/라이트 테마 지원
- [ ] 반응형 디자인 (모바일 고려)
- [ ] 접근성 (aria-label, 키보드 네비게이션)
- [ ] 애니메이션 (Framer Motion 활용)
- [ ] 에러 상태 처리
- [ ] 로딩 상태 표시

## 🚀 빠른 시작 예시

### 1. 새 페이지 생성

```bash
# Cursor AI에게 요청
"ValueBets 페이지를 참고해서 새로운 Statistics 페이지 만들어줘
- 통계 데이터를 카드로 표시
- 차트로 시각화
- 필터 기능 추가"
```

### 2. 스타일 개선

```bash
# 기존 컴포넌트 선택 후
"이 컴포넌트를 glass morphism 스타일로 변경해줘
- 반투명 배경
- blur 효과
- 테두리 glow"
```

### 3. 애니메이션 추가

```bash
"MatchCard에 hover 애니메이션 추가해줘
- scale 효과
- shadow 증가
- 0.2초 transition"
```

## 💡 디자인 팁

### 색상 사용

```css
/* ✅ 좋은 예: CSS 변수 사용 */
.button {
  background: var(--primary-500);
  color: var(--text-primary);
}

/* ❌ 나쁜 예: 하드코딩 */
.button {
  background: #3B82F6;
  color: #FFFFFF;
}
```

### 간격 사용

```css
/* ✅ 좋은 예 */
.container {
  padding: var(--space-4);
  gap: var(--space-6);
}

/* ❌ 나쁜 예 */
.container {
  padding: 16px;
  gap: 24px;
}
```

### 애니메이션

```typescript
// Framer Motion 사용
import { motion } from 'framer-motion';

<motion.div
  initial={{ opacity: 0, y: 20 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.3 }}
>
  {/* 내용 */}
</motion.div>
```

## 🔍 디버깅 팁

### 브라우저 개발자 도구

1. **Elements 탭**: DOM 구조 확인
2. **Styles 탭**: CSS 스타일 디버깅
3. **Console 탭**: JavaScript 에러 확인
4. **Network 탭**: API 요청 확인

### Cursor 통합 터미널

```bash
# 프론트엔드 로그 확인
cd frontend && npm run dev

# 빌드 에러 확인
npm run build

# 린트 에러 확인
npm run lint
```

## 📚 참고 자료

- [React 공식 문서](https://react.dev)
- [Framer Motion 문서](https://www.framer.com/motion/)
- [Recharts 문서](https://recharts.org)
- [CSS 변수 가이드](https://developer.mozilla.org/en-US/docs/Web/CSS/Using_CSS_custom_properties)

---

**마지막 업데이트**: 2026-01-05
