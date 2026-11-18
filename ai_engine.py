import base64
import json
from datetime import datetime
from google import genai
import requests

# 🌐 Google Gemini API 설정 (최신 google-genai SDK 방식)
# 발급받으신 본인의 Gemini API 키를 큰따옴표 사이에 넣어주세요.
GEMINI_API_KEY = "방금_복사한_실제_API키_입력"

# 최신 SDK 클라이언트 초기화
client = genai.Client(api_key=GEMINI_API_KEY)

# 💡 구글 서버가 요구하는 최신 지원 모델명으로 변경
MODEL_NAME = "gemini-2.0-flash"

# 🦊 GitLab 연동 설정
GITLAB_PROJECT_ID = "hbin0604-sudo%2FAI_Dashbord"
GITLAB_TOKEN = "glpat-T3gHK_Vziu5qRtPgRXHd62M6MQpvOjEKdTpxajM4bw8.01.171lz2q2c"

def ask_ai_bot(user_prompt):
    """ 최신 google-genai SDK를 사용한 인프라 참모 질의응답 함수 """
    if not GEMINI_API_KEY or GEMINI_API_KEY == "방금_복사한_실제_API키_입력":
        return "⚠️ Gemini API 키가 입력되지 않았습니다. ai_engine.py 파일의 GEMINI_API_KEY 변수에 키를 넣어주세요."
    
    try:
        # 시스템 지침(System Instruction)과 함께 콘텐츠 생성 요청
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=user_prompt,
            config={
                "system_instruction": "너는 관세청 오프라인/온프레미스 인프라 AI 수석 참모야. 간결하고 전문적으로 답변해줘.",
                "temperature": 0.3,
            }
        )
        return response.text
    except Exception as e:
        return f"⚠️ Gemini API 통신 오류: {e}"

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
