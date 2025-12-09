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
try:
    db = GithubDB(GITHUB_TOKEN, REPO_NAME)
except Exception as e:
    st.error(f"GitHub 리포지토리 연결 실패: {e}")
    st.info(f"리포지토리 '{REPO_NAME}'이 존재하는지 확인해주세요.")
    st.stop()

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
