Cursor AI를 활용하여 개발하시기에 최적화된 구조로 안내해 드립니다.

**핵심 과제 해결:**
Streamlit Cloud는 **앱이 재부팅되면 로컬에 저장된 파일이 초기화**되는 특성이 있습니다. 따라서 `json` 파일을 로컬에 저장하면 데이터가 날아갑니다. 이를 해결하기 위해 **GitHub API(`PyGithub`)를 사용하여 GitHub 리포지토리에 있는 JSON 파일을 직접 읽고 수정(Commit)하는 방식**으로 "DB 없는 영구 저장소"를 구현하겠습니다.

이 코드를 복사해서 Cursor AI에 파일별로 붙여넣으면 바로 작동합니다.

---

### 📂 프로젝트 파일 구조

```text
my-newsroom/
├── .streamlit/
│   └── secrets.toml      # (로컬 테스트용) API 키 저장
├── requirements.txt      # 라이브러리 목록
├── github_db.py          # GitHub를 DB처럼 쓰는 모듈
├── ai_analyst.py         # RSS 수집 및 Gemini 분석 모듈
└── app.py                # 메인 UI (Streamlit)
```

---

### 1. `requirements.txt`
필요한 라이브러리를 정의합니다.

```text
streamlit>=1.28.0
feedparser>=6.0.10
google-generativeai>=0.3.0
PyGithub>=1.59.0
python-dateutil>=2.8.2
beautifulsoup4>=4.12.0
```

---

### 2. `github_db.py` (핵심: 깃헙을 DB로 사용)
이 모듈은 GitHub 리포지토리의 파일을 읽고 쓰는 역할을 합니다.

```python
import json
from github import Github
import streamlit as st

class GithubDB:
    def __init__(self, token, repo_name):
        self.g = Github(token)
        self.repo = self.g.get_user().get_repo(repo_name)
    
    def load_data(self, filename, default_data):
        """GitHub에서 JSON 파일을 읽어옵니다. 파일이 없으면 기본값을 반환합니다."""
        try:
            contents = self.repo.get_contents(filename)
            return json.loads(contents.decoded_content.decode())
        except Exception as e:
            # 파일이 없는 경우는 정상적인 상황일 수 있음
            error_str = str(e)
            if "404" in error_str or "Not Found" in error_str:
                return default_data
            else:
                st.warning(f"데이터 로드 중 오류 발생: {e}")
                return default_data

    def save_data(self, filename, data, commit_message):
        """데이터를 JSON으로 변환하여 GitHub에 커밋합니다."""
        try:
            # 파일이 이미 존재하는지 확인
            try:
                contents = self.repo.get_contents(filename)
                self.repo.update_file(
                    contents.path,
                    commit_message,
                    json.dumps(data, indent=4, ensure_ascii=False),
                    contents.sha
                )
            except Exception as e:
                # 파일이 없으면 생성
                error_str = str(e)
                if "404" in error_str or "Not Found" in error_str:
                    self.repo.create_file(
                        filename,
                        commit_message,
                        json.dumps(data, indent=4, ensure_ascii=False)
                    )
                else:
                    raise e
            return True
        except Exception as e:
            st.error(f"GitHub 저장 실패: {e}")
            return False
```

---

### 3. `ai_analyst.py` (RSS 수집 및 Gemini 분석)
뉴스 수집 로직과 AI 분석 프롬프트를 담당합니다.

```python
import feedparser
import google.generativeai as genai
from bs4 import BeautifulSoup
import time

# HTML 태그 제거 함수
def clean_html(text):
    return BeautifulSoup(text, "html.parser").get_text()

# RSS 수집 함수
def fetch_rss_feeds(feed_urls, show_errors=True):
    """RSS 피드에서 기사를 수집합니다."""
    articles = []
    errors = []
    for url in feed_urls:
        try:
            feed = feedparser.parse(url)
            # RSS 파싱 에러 체크
            if feed.bozo and feed.bozo_exception:
                errors.append(f"{url}: 파싱 오류 - {feed.bozo_exception}")
                continue
            # 각 피드당 최신 3개만 가져오기 (토큰 절약 및 속도)
            for entry in feed.entries[:3]:
                articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "summary": clean_html(entry.get('summary', entry.get('description', '')))
                })
        except Exception as e:
            errors.append(f"{url}: {str(e)}")
    
    # 에러가 있고 Streamlit 환경이면 경고 표시
    if errors and show_errors:
        try:
            import streamlit as st
            for error in errors:
                st.warning(f"⚠️ RSS 피드 오류: {error}")
        except:
            # Streamlit이 아닌 환경에서는 print 사용
            for error in errors:
                print(f"Error: {error}")
    
    return articles

# Gemini 분석 함수
def analyze_news(api_key, articles, date_str):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash') # 빠르고 저렴한 모델 사용

    # 프롬프트 구성
    news_text = ""
    for idx, art in enumerate(articles):
        news_text += f"{idx+1}. {art['title']} : {art['summary']}\n"

    prompt = f"""
    아래는 {date_str}의 주요 IT 뉴스 목록입니다. 
    이 뉴스들을 바탕으로 '나만의 IT 뉴스 브리핑'을 작성해주세요.
    
    형식:
    1. 📢 **오늘의 핵심 이슈** (가장 중요한 트렌드 1~2개 요약)
    2. 🏢 **기업/기술 동향** (주요 기업이나 기술 변화)
    3. 🚀 **주목할 만한 소식** (짧은 리스트 형태)
    
    뉴스 데이터:
    {news_text}
    """

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI 분석 중 오류 발생: {e}"
```

---

### 4. `app.py` (메인 UI)
사용자 인터페이스 및 로직 연결을 담당합니다.

```python
import streamlit as st
import datetime
import time
from github_db import GithubDB
from ai_analyst import fetch_rss_feeds, analyze_news

# --- 페이지 설정 ---
st.set_page_config(page_title="나만의 IT 뉴스룸", layout="wide", page_icon="🗞️")

# --- Secrets에서 설정 가져오기 ---
# Streamlit Cloud 배포 시 Secrets에 저장된 키를 사용
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"] # 예: "my-username/my-repo"
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets 설정이 필요합니다 (.streamlit/secrets.toml)")
    st.stop()

# --- DB 연결 (GitHub) ---
db = GithubDB(GITHUB_TOKEN, REPO_NAME)

# --- 데이터 로드 (캐싱으로 GitHub API 호출 최소화) ---
# 캐시가 5분 이내면 재사용 (Rate Limit 방지)
cache_duration = 300  # 5분

if 'config_cache' not in st.session_state or 'cache_timestamp' not in st.session_state:
    st.session_state.cache_timestamp = time.time()
    st.session_state.config_cache = db.load_data("config.json", {"rss_feeds": [
        "https://news.google.com/rss/search?q=IT+tech+korea&hl=ko&gl=KR&ceid=KR:ko", # 기본값
    ]})
    st.session_state.news_cache = db.load_data("news_data.json", {})
    st.session_state.stats_cache = db.load_data("stats.json", {"visits": 0})

# 캐시가 만료되었거나 강제 새로고침이 필요한 경우
if time.time() - st.session_state.cache_timestamp > cache_duration:
    st.session_state.config_cache = db.load_data("config.json", {"rss_feeds": [
        "https://news.google.com/rss/search?q=IT+tech+korea&hl=ko&gl=KR&ceid=KR:ko",
    ]})
    st.session_state.news_cache = db.load_data("news_data.json", {})
    st.session_state.stats_cache = db.load_data("stats.json", {"visits": 0})
    st.session_state.cache_timestamp = time.time()

# 캐시된 데이터 사용
config_data = st.session_state.config_cache
news_archive = st.session_state.news_cache
stats_data = st.session_state.stats_cache

# --- 방문자 수 카운트 (세션당 1회) ---
if 'visited' not in st.session_state:
    stats_data['visits'] += 1
    if db.save_data("stats.json", stats_data, "Update visitor count"):
        st.session_state.stats_cache = stats_data  # 캐시 업데이트
    st.session_state['visited'] = True

# --- UI 구성 ---
st.title("🗞️ 나만의 AI IT 뉴스룸")

# 탭 구성
tab1, tab2 = st.tabs(["📅 일일 브리핑 (Main)", "⚙️ 대시보드 (Dashboard)"])

# === [TAB 1] 메인 화면: 뉴스 브리핑 ===
with tab1:
    st.header("오늘의 IT 브리핑")
    
    # 날짜 선택
    selected_date = st.date_input("날짜 선택", datetime.date.today())
    date_key = str(selected_date)

    if date_key in news_archive:
        st.markdown(news_archive[date_key])
    else:
        st.info("해당 날짜의 분석 리포트가 없습니다. 대시보드에서 분석을 실행해주세요.")

# === [TAB 2] 대시보드: 관리 및 분석 ===
with tab2:
    st.header("관리자 대시보드")
    
    # 1. 통계 섹션
    st.subheader("📊 접속자 통계")
    st.metric("총 누적 방문자 수", f"{stats_data['visits']}명")
    
    st.divider()

    # 2. RSS 관리 섹션
    st.subheader("📡 RSS 피드 관리")
    
    # 현재 등록된 피드 보여주기
    for i, url in enumerate(config_data['rss_feeds']):
        col1, col2 = st.columns([4, 1])
        col1.text(url)
        if col2.button("삭제", key=f"del_{i}"):
            config_data['rss_feeds'].pop(i)
            with st.spinner("설정 저장 중..."):
                if db.save_data("config.json", config_data, "Remove RSS Feed"):
                    st.session_state.config_cache = config_data  # 캐시 업데이트
            st.rerun()
            
    # 피드 추가
    new_feed = st.text_input("새로운 RSS URL 추가", placeholder="https://example.com/rss")
    if st.button("추가"):
        if new_feed:
            # 간단한 URL 검증
            if new_feed.startswith(("http://", "https://")):
                if new_feed not in config_data['rss_feeds']:
                    config_data['rss_feeds'].append(new_feed)
                    with st.spinner("설정 저장 중..."):
                        if db.save_data("config.json", config_data, "Add RSS Feed"):
                            st.session_state.config_cache = config_data  # 캐시 업데이트
                    st.rerun()
                else:
                    st.warning("이미 등록된 RSS 피드입니다.")
            else:
                st.error("올바른 URL 형식이 아닙니다. (http:// 또는 https://로 시작해야 합니다)")
            
    st.divider()

    # 3. AI 분석 실행 섹션
    st.subheader("🤖 뉴스 수집 및 AI 분석")
    
    # 날짜 선택 옵션 추가
    analysis_date = st.date_input("분석할 날짜 선택", datetime.date.today(), key="analysis_date")
    date_key = str(analysis_date)
    
    st.caption(f"등록된 RSS 피드에서 최신 뉴스를 가져와 {date_key} 날짜로 분석 리포트를 생성합니다.")
    
    if st.button("지금 분석 실행 (Update Now)", type="primary"):
        if not config_data.get('rss_feeds'):
            st.error("⚠️ RSS 피드가 등록되지 않았습니다. 먼저 RSS 피드를 추가해주세요.")
        else:
            with st.status("AI 뉴스 분석 진행 중...", expanded=True) as status:
                st.write("1. RSS 피드 수집 중...")
                articles = fetch_rss_feeds(config_data['rss_feeds'], show_errors=True)
                
                if not articles:
                    st.error("수집된 기사가 없습니다. RSS 피드 URL을 확인해주세요.")
                    status.update(label="수집 실패", state="error", expanded=False)
                else:
                    st.write(f" -> 총 {len(articles)}개의 기사 수집 완료")
                    
                    st.write("2. Gemini AI 분석 중...")
                    analysis_result = analyze_news(GEMINI_API_KEY, articles, date_key)
                    
                    if "오류 발생" in analysis_result or "❌" in analysis_result:
                        st.error(f"AI 분석 실패: {analysis_result}")
                        status.update(label="분석 실패", state="error", expanded=False)
                    else:
                        st.write("3. GitHub 저장소에 결과 저장 중...")
                        # 결과 저장
                        news_archive[date_key] = analysis_result
                        if db.save_data("news_data.json", news_archive, f"Add news report for {date_key}"):
                            st.session_state.news_cache = news_archive  # 캐시 업데이트
                            status.update(label="분석 및 저장 완료!", state="complete", expanded=False)
                            st.success(f"{date_key}의 뉴스룸이 업데이트되었습니다! 메인 탭에서 확인하세요.")
                            time.sleep(2)
                            st.rerun()
                        else:
                            status.update(label="저장 실패", state="error", expanded=False)
                            st.error("GitHub 저장에 실패했습니다. 나중에 다시 시도해주세요.")
```

---

### 🚀 배포 및 설정 방법 (매우 중요)

Cursor로 개발을 마치신 후, GitHub에 코드를 푸시하고 **Streamlit Cloud**에서 배포할 때 다음 단계를 거쳐야 합니다.

1.  **GitHub 리포지토리 생성 및 코드 푸시**: 위 파일들을 모두 올립니다.
2.  **Streamlit Cloud 접속 및 앱 생성**: 해당 리포지토리를 연결합니다.
3.  **Advanced Settings (Secrets) 설정**:
    Streamlit Cloud 설정 화면에서 `Secrets` 영역에 아래 내용을 입력해야 합니다.

```toml
# Streamlit Cloud의 Secrets 입력란에 복사 붙여넣기
GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxx"  # 본인의 GitHub Personal Access Token
REPO_NAME = "본인아이디/리포지토리이름"      # 예: "honggildong/ai-newsroom"
GEMINI_API_KEY = "AIzaSyxxxxxxxxxxxxxxxxx" # Google Gemini API Key
```

**[참고] GitHub Token 발급 방법:**
1. GitHub Settings -> Developer settings -> Personal access tokens (Tokens (classic)) -> Generate new token.
2. 권한(Scopes) 체크: **`repo`** (전체 체크) - 이 권한이 있어야 Streamlit이 GitHub 파일에 쓰기(Write)를 할 수 있습니다.
   - **보안 권장**: 가능하면 Fine-grained token을 사용하여 특정 리포지토리만 접근 가능하도록 설정하세요.

### ✨ 이 앱의 특징
1.  **DB 프리(DB-Free)**: 별도의 데이터베이스 서버 없이 GitHub 리포지토리 자체를 DB로 씁니다.
2.  **영구 저장**: `github_db.py` 덕분에 앱이 재시작되어도 뉴스 데이터와 방문자 수가 유지됩니다.
3.  **관리자 기능**: 대시보드에서 RSS를 맘대로 바꾸고 버튼 하나로 오늘의 뉴스를 생성할 수 있습니다.

이제 이 구조대로 Cursor AI에게 구현을 요청하거나 직접 붙여넣으시면 됩니다!