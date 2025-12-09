import feedparser
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from bs4 import BeautifulSoup
import time
import ssl
import urllib.request
import certifi

# HTML 태그 제거 함수
def clean_html(text):
    return BeautifulSoup(text, "html.parser").get_text()

# RSS 수집 함수
def fetch_rss_feeds(feed_urls, show_errors=True):
    """RSS 피드에서 기사를 수집합니다."""
    articles = []
    errors = []

    # 인증서 검증 문제 해결: certifi 기반 SSL 컨텍스트 사용
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    https_handler = urllib.request.HTTPSHandler(context=ssl_context)

    for url in feed_urls:
        try:
            feed = feedparser.parse(url, handlers=[https_handler])
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

# Gemini 분석 함수 (모델 자동 폴백)
# Gemini 2.0 Flash 모델 우선 사용
MODEL_CANDIDATES = [
    "gemini-2.0-flash",
    "models/gemini-2.0-flash",
    # 필요 시 하위 버전으로 확장 가능
    # "gemini-1.5-flash-001",
    # "models/gemini-1.5-flash-001",
    # "gemini-1.5-flash",
    # "models/gemini-1.5-flash",
]

def analyze_news(api_key, articles, date_str):
    genai.configure(api_key=api_key)

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

    last_error = None
    for model_name in MODEL_CANDIDATES:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text
        except google_exceptions.NotFound as e:
            # 모델이 없으면 다음 후보로 폴백
            last_error = e
            continue
        except Exception as e:
            last_error = e
            break

    return f"AI 분석 중 오류 발생: {last_error}"


