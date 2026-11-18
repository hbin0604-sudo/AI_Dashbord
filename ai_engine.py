import base64
import json
from datetime import datetime
import requests

# 🌐 무료 Google Gemini 클라우드 API 설정
# 💡큰따옴표("") 사이에 AI Studio에서 받으신 본인의 API 키를 넣어주세요!
GEMINI_API_KEY = "방금_복사한_실제_API키_입력"

# 🚀 404 에러를 완벽하게 해결하는 구글 공식 v1beta 최신 정식 엔드포인트
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

# 🦊 GitLab 연동 설정
GITLAB_PROJECT_ID = "hbin0604-sudo%2FAI_Dashbord"
GITLAB_TOKEN = "glpat-T3gHK_Vziu5qRtPgRXHd62M6MQpvOjEKdTpxajM4bw8.01.171lz2q2c"

def ask_ai_bot(user_prompt):
    """ 클라우드 기반 초고속 Gemini API 질의응답 함수 (v1beta 엔드포인트 적용) """
    if not GEMINI_API_KEY or GEMINI_API_KEY == "방금_복사한_실제_API키_입력":
        return "⚠️ Gemini API 키가 입력되지 않았습니다. ai_engine.py 파일의 GEMINI_API_KEY 변수에 키를 넣어주세요."
    
    headers = {
        "Content-Type": "application/json"
    }
    
    # 구글 클라우드 v1beta 표준 페이로드 (시스템 지침 포함)
    payload = {
        "system_instruction": {
            "parts": [{"text": "너는 관세청 오프라인/온프레미스 인프라 AI 수석 참모야. 간결하고 전문적으로 답변해줘."}]
        },
        "contents": [
            {
                "parts": [{"text": user_prompt}]
            }
        ]
    }
    
    try:
        response = requests.post(GEMINI_URL, json=payload, headers=headers, timeout=20)
        res_data = response.json()
        
        # API 거부 에러 체크
        if "error" in res_data:
            err_msg = res_data["error"].get("message", "알 수 없는 API 에러")
            return f"⚠️ Gemini 클라우드 거부됨: {err_msg}"
            
        # 응답 텍스트 추출
        candidate = res_data.get("candidates", [])[0]
        answer_text = candidate.get("content", {}).get("parts", [])[0].get("text", "응답을 생성하지 못했습니다.")
        return answer_text
        
    except Exception as e:
        return f"⚠️ 클라우드 AI 통신 오류: {e}"

def push_log_to_gitlab(event_name, ai_diagnosis_text):
    """ AI가 탐지한 침해사고 로그를 GitLab Repository에 자동 커밋하는 함수 """
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = f"logs/ai_detect_{timestamp_str}.json"
    
    log_data = {
        "event": event_name,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": "gemini-1.5-flash",
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
