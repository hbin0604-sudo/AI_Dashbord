import requests
import base64
import json
from datetime import datetime

# 💡 초고속 클라우드 AI API 설정 (예: OpenAI API / 인터넷망 연동)
CLOUD_AI_URL = "https://api.openai.com/v1/chat/completions"
# 본인의 클라우드 AI API 키를 입력하세요 (예: "sk-...")
CLOUD_AI_KEY = "YOUR_CLOUD_AI_API_KEY"
MODEL_NAME = "gpt-4o-mini"  # 매우 빠르고 정확한 고속 모델

# GitHub 연동 설정
GITHUB_REPO = "hbin0604-sudo/AI_Dashbord"
GITHUB_TOKEN = "YOUR_GITHUB_PERSONAL_ACCESS_TOKEN" # 본인 GitHub 토큰 입력

def ask_ai_bot(user_prompt):
    """ 인터넷망을 통한 고속 클라우드 AI 질의응답 (수초 내 즉답) """
    if not CLOUD_AI_KEY or CLOUD_AI_KEY == "YOUR_CLOUD_AI_API_KEY":
        return "⚠️ 클라우드 AI API 키(CLOUD_AI_KEY)가 설정되지 않았습니다. ai_engine.py에 키를 입력해주세요."

    headers = {
        "Authorization": f"Bearer {CLOUD_AI_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "너는 관세청 오프라인/온프레미스 인프라 AI 수석 참모야. 간결하고 전문적으로 답변해줘."},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.3
    }
    try:
        response = requests.post(CLOUD_AI_URL, json=payload, headers=headers, timeout=15)
        res_data = response.json()
        return res_data["choices"]["message"]["content"]
    except Exception as e:
        return f"⚠️ 클라우드 AI API 통신 오류: {e}"

def push_log_to_github(event_name, ai_diagnosis_text):
    """ AI가 탐지한 이벤트 로그를 GitHub 레포지토리에 자동으로 커밋/기록하는 함수 """
    if not GITHUB_TOKEN or GITHUB_TOKEN == "YOUR_GITHUB_PERSONAL_ACCESS_TOKEN":
        return "❌ GitHub 토큰(GITHUB_TOKEN)이 설정되지 않았습니다."

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = f"logs/ai_detect_{timestamp_str}.json"
    
    log_data = {
        "event": event_name,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": MODEL_NAME,
        "ai_report": ai_diagnosis_text
    }
    
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
            return f"⚠️ GitHub 업로드 실패: {err_msg}"
    except Exception as e:
        return f"⚠️ GitHub API 통신 오류: {e}"
