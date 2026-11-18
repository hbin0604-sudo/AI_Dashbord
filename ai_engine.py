import base64
import json
from datetime import datetime
import requests

# 🌐 Groq 무료 클라우드 API 설정 (REST 직통 방식)
GROQ_API_KEY = "Gsk_v9aQPjsahM76RVf0xku6WGdyb3FYRrga2xMv1IsLpnALtPypcm3V"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# 💡 확실하게 권한이 열려 있는 Groq 표준 정식 모델명으로 교체
MODEL_NAME = "llama3-70b-8192"

# 🦊 GitLab 연동 설정
GITLAB_PROJECT_ID = "hbin0604-sudo%2FAI_Dashbord"
GITLAB_TOKEN = "glpat-T3gHK_Vziu5qRtPgRXHd62M6MQpvOjEKdTpxajM4bw8.01.171lz2q2c"

def ask_ai_bot(user_prompt):
    """ Groq REST API를 직접 호출하여 인증 오류와 라이브러리 충돌을 원천 차단하는 참모 함수 """
    if not GROQ_API_KEY:
        return "⚠️ Groq API 키가 입력되지 않았습니다."
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": "너는 관세청 오프라인/온프레미스 인프라 AI 수석 참모야. 간결하고 전문적으로 답변해줘."
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        "temperature": 0.3
    }
    
    try:
        response = requests.post(GROQ_URL, json=payload, headers=headers, timeout=20)
        res_data = response.json()
        
        # API 거부 에러 체크
        if "error" in res_data:
            err_msg = res_data["error"].get("message", "알 수 없는 API 에러")
            return f"⚠️ Groq 인증/요청 거부됨: {err_msg}"
            
        # 응답 텍스트 추출
        answer_text = res_data["choices"][0]["message"]["content"]
        return answer_text
        
    except Exception as e:
        return f"⚠️ Groq API 통신 오류: {e}"

def push_log_to_gitlab(event_name, ai_diagnosis_text):
    """ AI가 탐지한 침해사고 로그를 GitLab Repository에 자동 커밋하는 함수 """
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

# 하위 호환을 위한 별칭
push_log_to_github = push_log_to_gitlab
