import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma"  # 또는 gemma2:9b

def get_gemma_diagnosis():
    # 기존 단발성 진단 리포트용 함수 유지
    payload = {
        "model": MODEL_NAME,
        "prompt": "너는 관세청 IT 인프라 수석 참모야. 현재 수입신고 시스템 로그에서 간헐적인 지연이 포착되었어. 1) 예상 원인, 2) 긴급 조치 가이드를 3줄 이내로 요약해줘.",
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=15)
        return response.json().get("response", "AI 응답을 받아오지 못했습니다.")
    except Exception as e:
        return None

def ask_ai_bot(user_prompt):
    """ 우측 하단 AI Bot 챗봇용 실시간 질의응답 함수 """
    payload = {
        "model": MODEL_NAME,
        "prompt": f"너는 관세청 오프라인 폐쇄망 인프라 AI 어시스턴트야. 사용자의 질문에 친절하고 전문적으로 답변해줘.\n\n질문: {user_prompt}",
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=20)
        return response.json().get("response", "로컬 AI 응답 생성 실패")
    except Exception as e:
        return f"⚠️ Ollama 연결 오류: {e}"
