# Plan.md 검토 결과

## ✅ 잘 구성된 부분

1. **명확한 문제 정의**: Streamlit Cloud의 파일 초기화 문제를 GitHub API로 해결하는 접근이 적절합니다.
2. **구조적 설계**: 모듈 분리(github_db.py, ai_analyst.py, app.py)가 잘 되어 있습니다.
3. **실용적인 기능**: RSS 관리, AI 분석, 통계 추적 등 핵심 기능이 포함되어 있습니다.

---

## ⚠️ 발견된 문제점 및 개선 사항

### 1. **코드 오류 (Critical)**

#### `app.py` 265번째 줄
```python
time.sleep(2)  # ❌ import time이 없음
```
**문제**: `time` 모듈을 import하지 않았는데 사용하고 있습니다.

**해결책**: `app.py` 상단에 추가
```python
import time
```

---

### 2. **에러 처리 개선 필요**

#### `github_db.py`의 예외 처리
- 현재 `except:`로 모든 예외를 무시하고 있습니다.
- 구체적인 예외 타입을 명시하고 사용자에게 더 명확한 메시지를 제공해야 합니다.

**개선 제안**:
```python
def load_data(self, filename, default_data):
    try:
        contents = self.repo.get_contents(filename)
        return json.loads(contents.decoded_content.decode())
    except Exception as e:
        # 파일이 없는 경우는 정상적인 상황일 수 있음
        if "404" in str(e) or "Not Found" in str(e):
            return default_data
        else:
            st.warning(f"데이터 로드 중 오류: {e}")
            return default_data
```

---

### 3. **GitHub API Rate Limit 고려**

GitHub API는 시간당 요청 제한이 있습니다 (인증된 사용자: 5,000 requests/hour).
- 여러 사용자가 동시에 접속하면 rate limit에 걸릴 수 있습니다.
- 캐싱 메커니즘 추가를 고려해야 합니다.

**개선 제안**:
```python
# app.py에 세션 상태 캐싱 추가
if 'news_archive_cache' not in st.session_state:
    st.session_state.news_archive_cache = db.load_data("news_data.json", {})
    st.session_state.cache_timestamp = time.time()

# 캐시가 5분 이내면 재사용
if time.time() - st.session_state.cache_timestamp < 300:
    news_archive = st.session_state.news_archive_cache
else:
    news_archive = db.load_data("news_data.json", {})
    st.session_state.news_archive_cache = news_archive
    st.session_state.cache_timestamp = time.time()
```

---

### 4. **RSS 피드 수집 에러 처리 개선**

#### `ai_analyst.py`의 `fetch_rss_feeds` 함수
- 현재 개별 피드 오류 시 `print`만 사용하고 있습니다.
- Streamlit에서는 `st.warning()`을 사용하는 것이 더 적절합니다.

**개선 제안**:
```python
def fetch_rss_feeds(feed_urls, show_errors=True):
    articles = []
    errors = []
    for url in feed_urls:
        try:
            feed = feedparser.parse(url)
            if feed.bozo and feed.bozo_exception:
                errors.append(f"{url}: 파싱 오류")
                continue
            for entry in feed.entries[:3]:
                articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "summary": clean_html(entry.get('summary', entry.get('description', '')))
                })
        except Exception as e:
            errors.append(f"{url}: {str(e)}")
    
    if errors and show_errors:
        # Streamlit에서 사용할 경우
        import streamlit as st
        for error in errors:
            st.warning(error)
    
    return articles
```

---

### 5. **날짜 선택 기능 개선**

현재는 날짜를 선택할 수 있지만, 과거 날짜에 대한 분석을 실행할 수 없습니다.
- 대시보드에서 특정 날짜를 선택하여 분석할 수 있는 기능 추가를 고려하세요.

---

### 6. **보안 개선 사항**

#### GitHub Token 권한
- `repo` 전체 권한은 너무 광범위합니다.
- 최소 권한 원칙에 따라 필요한 권한만 부여하는 것이 좋습니다.
- **권장**: `public_repo` 또는 특정 리포지토리만 접근 가능한 Fine-grained token 사용

---

### 7. **사용자 경험 개선**

#### 로딩 상태 표시
- `github_db.py`의 `save_data` 함수에서 저장 중임을 사용자에게 알려주는 것이 좋습니다.
- 이미 `app.py`에서 `st.spinner`를 사용하고 있으므로 일관성이 좋습니다.

#### 데이터 검증
- RSS URL 형식 검증 추가
- JSON 데이터 구조 검증

---

### 8. **requirements.txt 누락**

`plan.md`의 `requirements.txt`에 다음이 누락되어 있습니다:
- `beautifulsoup4` (ai_analyst.py에서 사용)
- `python-dateutil` (날짜 처리용, 현재는 사용하지 않지만 언급됨)

**완전한 requirements.txt**:
```text
streamlit>=1.28.0
feedparser>=6.0.10
google-generativeai>=0.3.0
PyGithub>=1.59.0
beautifulsoup4>=4.12.0
python-dateutil>=2.8.2
```

---

### 9. **코드 일관성**

#### `ai_analyst.py`의 `clean_html` 함수
- `BeautifulSoup`을 사용하는데, `plan.md`에서는 `beautifulsoup4`를 requirements에 포함시켰지만 실제 사용 예시가 명확하지 않습니다.
- 현재 코드는 올바르게 구현되어 있습니다.

---

## 📋 우선순위별 수정 권장사항

### 🔴 높은 우선순위 (즉시 수정 필요)
1. ✅ `app.py`에 `import time` 추가
2. ✅ `requirements.txt`에 누락된 패키지 추가
3. ✅ `github_db.py`의 예외 처리 개선

### 🟡 중간 우선순위 (개선 권장)
4. ✅ GitHub API rate limit 대응 (캐싱)
5. ✅ RSS 피드 에러 처리 개선
6. ✅ 날짜 선택 기능 확장

### 🟢 낮은 우선순위 (선택적)
7. ✅ 보안 권한 최소화
8. ✅ 데이터 검증 추가
9. ✅ 사용자 경험 개선

---

## 💡 추가 제안사항

1. **로깅 시스템**: GitHub 저장 실패 등의 중요한 이벤트를 로깅
2. **백업 기능**: 주기적으로 데이터 백업
3. **분석 결과 포맷팅**: Markdown 렌더링 개선
4. **반응형 디자인**: 모바일 지원 고려

---

## ✅ 최종 평가

전반적으로 **잘 설계된 계획**입니다. 핵심 문제를 정확히 파악하고 실용적인 해결책을 제시했습니다. 위의 수정사항들을 반영하면 더욱 견고한 애플리케이션이 될 것입니다.

**점수**: 8.5/10
- 구조: 9/10
- 완성도: 8/10
- 에러 처리: 7/10
- 보안: 8/10


