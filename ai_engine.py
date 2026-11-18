import requests
import base64
import json
from datetime import datetime

# 🌐 클라우드 AI (OpenAI GPT-4o-mini) 설정
CLOUD_AI_URL = "https://api.openai.com/v1/chat/completions"
CLOUD_AI_KEY = "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"
MODEL_NAME = "gpt-4o-mini"

# 🦊 GitLab 연동 설정
GITLAB_PROJECT_ID = "hbin0604-sudo%2FAI_Dashbord"  # URL 인코딩된 프로젝트 경로
GITLAB_TOKEN = "glpat-T3gHK_Vziu5qRtPgRXHd62M6MQpvOjEKdTpxajM4bw8.01.171lz2q2c"

def ask_ai_bot(user_prompt):
    """ 인터넷망을 통한 초고속 클라우드 AI 질의응답 """
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

def push_log_to_gitlab(event_name, ai_diagnosis_text):
    """ AI가 탐지한 침해사고 로그를 GitLab Repository에 자동으로 커밋/기록하는 함수 """
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

    # GitLab Repository Files API 규격
    url = f"https://gitlab.com/api/v4/projects/{GITLAB_PROJECT_ID}/repository/files/{file_path}"
    headers = {
        "PRIVATE-TOKEN": GITLAB_TOKEN,
        "Content-Type": "application/json"
    }
    payload = {
        "branch": "main",
        "content": base64_content,
        "encoding": "base64",
        "commit_message": f"AIOps-Guard: 자동 AI 탐지 로그 기록 ({timestamp_str})"
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=15)
        if res.status_code in [200, 201]:
            return f"✅ GitLab 연동 성공! 레포지토리에 로그가 기록되었습니다. (경로: {file_path})"
        else:
            err_msg = res.json().get("message", "알 수 없는 오류")
            return f"⚠️ GitLab 업로드 실패: {err_msg} (상태코드: {res.status_code})"
    except Exception as e:
        return f"⚠️ GitLab API 통신 오류: {e}"
