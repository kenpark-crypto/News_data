import json
from github import Github
import streamlit as st

class GithubDB:
    def __init__(self, token, repo_name):
        self.g = Github(token)
        # repo_name이 "username/repo" 형식이면 get_repo()를 직접 사용
        if "/" in repo_name:
            self.repo = self.g.get_repo(repo_name)
        else:
            # 단순 리포지토리 이름만 있으면 현재 사용자의 리포지토리로 가져오기
            self.repo = self.g.get_user().get_repo(repo_name)
    
    def load_data(self, filename, default_data):
        """GitHub에서 JSON 파일을 읽어옵니다. 파일이 없으면 기본값을 반환합니다."""
        try:
            contents = self.repo.get_contents(filename)
            return json.loads(contents.decoded_content.decode())
        except Exception as e:
            # 파일이 없는 경우는 정상적인 상황일 수 있음
            error_str = str(e)
            # PyGithub의 UnknownObjectException도 처리
            from github import UnknownObjectException
            if isinstance(e, UnknownObjectException) or "404" in error_str or "Not Found" in error_str:
                return default_data
            else:
                # 리포지토리 접근 오류는 경고만 표시하고 기본값 반환
                try:
                    st.warning(f"데이터 로드 중 오류 발생: {e}")
                except:
                    # Streamlit이 없는 환경에서는 print 사용
                    print(f"Warning: 데이터 로드 중 오류 발생: {e}")
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
                from github import UnknownObjectException
                error_str = str(e)
                if isinstance(e, UnknownObjectException) or "404" in error_str or "Not Found" in error_str:
                    self.repo.create_file(
                        filename,
                        commit_message,
                        json.dumps(data, indent=4, ensure_ascii=False)
                    )
                else:
                    raise e
            return True
        except Exception as e:
            try:
                st.error(f"GitHub 저장 실패: {e}")
            except:
                print(f"Error: GitHub 저장 실패: {e}")
            return False


