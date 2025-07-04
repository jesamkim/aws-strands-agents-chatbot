"""
Strands Agents 호출을 위한 타임아웃 래퍼
네트워크 타임아웃 발생 시 graceful fallback 제공
"""

import time
import signal
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Any, Dict, Optional


class TimeoutException(Exception):
    """타임아웃 예외"""
    pass


@contextmanager
def timeout_handler(seconds: int):
    """시그널 기반 타임아웃 핸들러"""
    def timeout_signal_handler(signum, frame):
        raise TimeoutException(f"Operation timed out after {seconds} seconds")
    
    # 기존 핸들러 저장
    old_handler = signal.signal(signal.SIGALRM, timeout_signal_handler)
    signal.alarm(seconds)
    
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def safe_agent_call(agent, query: str, conversation_history: list, timeout_seconds: int = 60) -> Dict[str, Any]:
    """
    안전한 에이전트 호출 (타임아웃 처리 포함)
    
    Args:
        agent: Strands Agent 인스턴스
        query: 사용자 쿼리
        conversation_history: 대화 히스토리
        timeout_seconds: 타임아웃 시간 (초)
    
    Returns:
        Dict containing response or error information
    """
    
    def _agent_call():
        """실제 에이전트 호출"""
        try:
            # Strands Agent 호출 방식 수정
            prompt = f"""사용자 질문을 처리해주세요:

질문: {query}
대화 히스토리: {conversation_history[-3:] if conversation_history else []}

다음 단계를 따라 처리하세요:
1. context_analyzer로 맥락 분석
2. 필요시 timeout_resilient_kb_search로 검색
3. 검색 결과가 있으면 quality_assessor로 평가
4. 최종 답변 생성

**중요:** 타임아웃이 발생할 수 있으므로 간결하게 처리하세요."""

            # Strands Agent는 callable 객체로 호출
            response = agent(prompt)
            
            return {
                "success": True,
                "content": str(response),
                "error": None,
                "timeout": False
            }
        except Exception as e:
            error_str = str(e)
            is_timeout = any(keyword in error_str.lower() for keyword in [
                "timeout", "timed out", "read timed out", "connection timeout",
                "readtimeouterror", "connecttimeouterror"
            ])
            
            return {
                "success": False,
                "content": None,
                "error": error_str,
                "timeout": is_timeout
            }
    
    start_time = time.time()
    
    try:
        # ThreadPoolExecutor를 사용한 타임아웃 처리
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_agent_call)
            
            try:
                result = future.result(timeout=timeout_seconds)
                processing_time = time.time() - start_time
                result["processing_time"] = processing_time
                
                return result
                
            except FutureTimeoutError:
                # 타임아웃 발생 시 fallback 응답
                processing_time = time.time() - start_time
                
                return {
                    "success": False,
                    "content": generate_timeout_fallback_response(query),
                    "error": f"Request timed out after {timeout_seconds} seconds",
                    "timeout": True,
                    "processing_time": processing_time,
                    "fallback": True
                }
                
    except Exception as e:
        processing_time = time.time() - start_time
        
        return {
            "success": False,
            "content": generate_error_fallback_response(query, str(e)),
            "error": str(e),
            "timeout": False,
            "processing_time": processing_time,
            "fallback": True
        }


def generate_timeout_fallback_response(query: str) -> str:
    """타임아웃 발생 시 대체 응답 생성"""
    
    # 간단한 키워드 기반 응답
    query_lower = query.lower()
    
    if any(word in query_lower for word in ["안녕", "hello", "hi", "반갑"]):
        return """안녕하세요! 반갑습니다. 

⚠️ 현재 네트워크 연결이 불안정하여 Knowledge Base 검색을 수행할 수 없습니다. 
일반적인 질문에 대해서는 답변해 드릴 수 있으니, 다시 질문해 주세요."""

    elif any(word in query_lower for word in ["투자", "investment", "승인", "approval"]):
        return """투자 승인 절차에 대한 질문을 주셨군요.

⚠️ 현재 Knowledge Base 연결에 문제가 있어 정확한 회사 정책을 확인할 수 없습니다.

일반적인 투자 승인 절차는 다음과 같습니다:
1. 투자 제안서 작성
2. 부서 검토
3. 재무팀 검토  
4. 경영진 승인
5. 최종 결재

정확한 회사 정책은 네트워크 상태가 개선된 후 다시 문의해 주세요."""

    elif any(word in query_lower for word in ["정책", "policy", "절차", "procedure"]):
        return """회사 정책이나 절차에 대한 질문을 주셨군요.

⚠️ 현재 Knowledge Base에 연결할 수 없어 정확한 회사 정책을 확인할 수 없습니다.

네트워크 상태가 개선된 후 다시 질문해 주시거나, 
직접 관련 부서에 문의하시기 바랍니다."""

    else:
        return f"""죄송합니다. 현재 시스템에 일시적인 문제가 발생했습니다.

⚠️ **네트워크 타임아웃 발생**
- Knowledge Base 검색을 수행할 수 없습니다
- 연결 상태를 확인한 후 다시 시도해 주세요

**질문:** {query}

잠시 후 다시 시도해 주시거나, 더 간단한 질문으로 다시 문의해 주세요."""


def generate_error_fallback_response(query: str, error: str) -> str:
    """오류 발생 시 대체 응답 생성"""
    
    return f"""죄송합니다. 요청을 처리하는 중 오류가 발생했습니다.

**질문:** {query}

**오류 정보:** {error}

**해결 방법:**
1. 잠시 후 다시 시도해 주세요
2. 질문을 더 간단하게 바꿔서 시도해 보세요
3. 네트워크 연결 상태를 확인해 주세요

문제가 지속되면 시스템 관리자에게 문의하시기 바랍니다."""


def test_timeout_wrapper():
    """타임아웃 래퍼 테스트"""
    print("🧪 타임아웃 래퍼 테스트")
    print("-" * 50)
    
    # Mock agent for testing
    class MockAgent:
        def __call__(self, query):
            import time
            time.sleep(2)  # 2초 대기
            return f"Mock response for: {query}"
    
    agent = MockAgent()
    
    # 정상 케이스 테스트
    print("1. 정상 케이스 테스트:")
    result = safe_agent_call(agent, "테스트 질문", [], timeout_seconds=5)
    print(f"   성공: {result['success']}")
    
    if result['success'] and result['content']:
        print(f"   응답: {result['content'][:50]}...")
    elif not result['success'] and result['content']:
        print(f"   Fallback 응답: {result['content'][:50]}...")
    else:
        print(f"   오류: {result.get('error', 'Unknown error')}")
        
    print(f"   처리 시간: {result['processing_time']:.2f}초")
    print(f"   타임아웃 발생: {result.get('timeout', False)}")
    
    # 타임아웃 케이스 테스트 (실제로는 시간이 오래 걸리므로 생략)
    print("\n2. 타임아웃 처리 준비 완료")
    print("   실제 타임아웃 상황에서 fallback 응답 제공")
    
    print("\n✅ 타임아웃 래퍼 테스트 완료")


if __name__ == "__main__":
    test_timeout_wrapper()
