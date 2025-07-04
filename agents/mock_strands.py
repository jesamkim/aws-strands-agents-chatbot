"""
Mock Strands Agents for testing without actual library
실제 Strands Agents 라이브러리 없이 테스트하기 위한 Mock 구현
"""

from typing import List, Dict, Any, Callable
import json
import time


class MockAgent:
    """Mock Strands Agent"""
    
    def __init__(self, system_prompt: str = "", tools: List[Callable] = None):
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.call_count = 0
    
    def __call__(self, query: str) -> str:
        """에이전트 호출 시뮬레이션"""
        self.call_count += 1
        
        # 간단한 응답 생성 로직
        if "안녕" in query or "hello" in query.lower():
            return "안녕하세요! 무엇을 도와드릴까요?"
        elif "테스트" in query:
            return "테스트 응답입니다. Mock Strands Agent가 정상적으로 작동하고 있습니다."
        elif "검색" in query or "찾아" in query:
            return "Knowledge Base 검색을 시뮬레이션합니다. 관련 정보를 찾았습니다."
        else:
            return f"Mock Strands Agent 응답: {query}에 대한 답변을 생성했습니다."


def mock_tool(func: Callable = None, **kwargs) -> Callable:
    """Mock @tool decorator that can handle both functions and methods"""
    def decorator(f):
        # 원본 함수에 tool 속성 추가
        f._is_mock_tool = True
        f._tool_name = f.__name__
        f._tool_description = f.__doc__ or f"Mock tool: {f.__name__}"
        return f
    
    if func is None:
        # @tool() 형태로 호출된 경우
        return decorator
    else:
        # @tool 형태로 호출된 경우
        return decorator(func)


# Mock 모듈 구조
class MockStrandsModule:
    """Mock strands module"""
    Agent = MockAgent
    tool = mock_tool


# Mock을 실제 import처럼 사용할 수 있도록 설정
import sys
sys.modules['strands'] = MockStrandsModule()


# 사용 예시 및 테스트
if __name__ == "__main__":
    print("🧪 Mock Strands Agents 테스트")
    print("-" * 40)
    
    # Mock tool 생성
    @mock_tool
    def test_tool(query: str) -> str:
        """테스트용 도구"""
        return f"Mock tool 응답: {query}"
    
    # Mock agent 생성
    agent = MockAgent(
        system_prompt="You are a test agent",
        tools=[test_tool]
    )
    
    # 테스트 쿼리들
    test_queries = [
        "안녕하세요",
        "테스트 해주세요",
        "정보를 검색해주세요",
        "일반적인 질문입니다"
    ]
    
    for query in test_queries:
        response = agent(query)
        print(f"Q: {query}")
        print(f"A: {response}")
        print()
    
    print(f"총 {agent.call_count}번 호출됨")
    print("✅ Mock Strands Agents 테스트 완료")
