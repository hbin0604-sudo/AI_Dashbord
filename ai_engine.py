import requests
import base64
import json
from datetime import datetime

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:3b"

# GitHub 연동 설정 (저장소 및 토큰 정보)
GITHUB_REPO = "hbin0604-sudo/AI_Dashbord"
# 💡 본인의 GitHub Personal Access Token(PAT)을 아래 빈 따옴표 안에 입력해주세요!
GITHUB_TOKEN = "YOUR_GITHUB_PERSONAL_ACCESS_TOKEN" 

def ask_ai_bot(user_prompt):
    """ 로컬 Ollama 질의응답 (타임아웃을 60초로 넉넉하게 연장) """
    payload = {
        "model": MODEL_NAME,
        "prompt": f"너는 관세청 오프라인 폐쇄망 인프라 AI 어시스턴트야. 사용자의 질문에 친절하고 전문적으로 답변해줘.\n\n질문: {user_prompt}",
        "stream": False
    }
    try:
        # 타임아웃을 60초로 연장하여 응답 지연 방지
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)
        return response.json().get("response", "로컬 AI 응답 생성 실패")
    except Exception as e:
        return f"⚠️ Ollama 연결 오류 (타임아웃 또는 서버 중지): {e}"

def push_log_to_github(event_name, ai_diagnosis_text):
    """ AI가 탐지한 이벤트 로그를 GitHub 레포지토리에 자동으로 커밋/기록하는 함수 """
    if not GITHUB_TOKEN or GITHUB_TOKEN == "YOUR_GITHUB_PERSONAL_ACCESS_TOKEN":
        return "❌ GitHub 토큰(GITHUB_TOKEN)이 설정되지 않았습니다. ai_engine.py 파일에 토큰을 입력해주세요."

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = f"logs/ai_detect_{timestamp_str}.json"
    
    # 기록할 로그 데이터 구조
    log_data = {
        "event": event_name,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": MODEL_NAME,
        "ai_report": ai_diagnosis_text
    }
    
    # JSON 데이터를 Base64로 인코딩 (GitHub API 규격)
    json_bytes = json.dumps(log_data, ensure_ascii=False, indent=4).encode("utf-8")
    base64_content = base64.b64encode(json_bytes).decode("utf-8")

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    payload = {
        "message": f"AIOps-Guard: 자동 AI 탐지 로그 기록 ({timestamp_str})",
        "content": base64_content,
        "branch": "main"
    }

    try:
        res = requests.put(url, json=payload, headers=headers, timeout=15)
        if res.status_code in [200, 201]:
            return f"✅ GitHub 연동 성공! 레포지토리에 로그가 기록되었습니다. (경로: {file_path})"
        else:
            err_msg = res.json().get("message", "알 수 없는 오류")
            return f"⚠️ GitHub 업로드 실패: {err_msg} (상태코드: {res.status_code})"
    except Exception as e:
        return f"⚠️ GitHub API 통신 오류: {e}"
