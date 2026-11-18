import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma"  # 또는 gemma2:9b

def get_gemma_diagnosis():
    payload = {
        "model": MODEL_NAME,
        "prompt": "너는 관세청 IT 인프라 수석 참모야. 현재 수입신고 시스템 로그에서 간헐적인 지연이 포착되었어. 1) 예상 원인, 2) 긴급 조치 가이드를 3줄 이내로 요약해줘.",
        "stream": False
    }
    
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=15)
        return response.json().get("response", "AI 응답을 받아오지 못했습니다.")
    except Exception as e:
        return None  # 에러 발생 시 외부에서 처리
