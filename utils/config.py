"""
KB 설명이 추가된 Agent 설정 관리 클래스
"""

from dataclasses import dataclass
from typing import Optional
import streamlit as st


@dataclass
class AgentConfig:
    """ReAct Agent 설정 클래스"""
    
    # 모델 설정
    orchestration_model: str
    action_model: str
    observation_model: str
    
    # 시스템 설정
    system_prompt: str
    kb_id: Optional[str]
    kb_description: Optional[str]  # 새로 추가
    
    # 파라미터 설정
    temperature: float
    max_tokens: int
    
    # 안전장치 설정
    max_iterations: int = 5
    max_errors: int = 3
    
    @classmethod
    def from_streamlit_session(cls) -> 'AgentConfig':
        """Streamlit 세션 상태에서 설정 로드"""
        return cls(
            orchestration_model=st.session_state.get('orchestration_model', 'us.anthropic.claude-3-5-haiku-20241022-v1:0'),
            action_model=st.session_state.get('action_model', 'us.amazon.nova-micro-v1:0'),  # 경제적 조합
            observation_model=st.session_state.get('observation_model', 'us.anthropic.claude-3-5-haiku-20241022-v1:0'),
            system_prompt=st.session_state.get('system_prompt', ''),
            kb_id=st.session_state.get('kb_id'),
            kb_description=st.session_state.get('kb_description', ''),  # 새로 추가
            temperature=st.session_state.get('temperature', 0.1),
            max_tokens=st.session_state.get('max_tokens', 4000)
        )
    
    def get_max_tokens_for_model(self, model_id: str) -> int:
        """모델별 최대 토큰 수 반환"""
        if 'claude' in model_id.lower():
            return min(self.max_tokens, 8000)
        elif 'nova' in model_id.lower():
            return min(self.max_tokens, 5000)
        else:
            return self.max_tokens
    
    def is_kb_enabled(self) -> bool:
        """Knowledge Base 사용 여부"""
        return bool(self.kb_id and self.kb_id.strip())
    
    def has_kb_description(self) -> bool:
        """KB 설명 존재 여부"""
        return bool(self.kb_description and self.kb_description.strip())
    
    def get_kb_description(self) -> str:
        """KB 설명 반환 (안전한 방식)"""
        return self.kb_description.strip() if self.kb_description else ""
    
    def validate_model_selection(self) -> bool:
        """모델 선택 유효성 검증"""
        # Claude 모델 목록
        claude_models = [
            'us.anthropic.claude-sonnet-4-20250514-v1:0',
            'us.anthropic.claude-3-7-sonnet-20250219-v1:0',
            'us.anthropic.claude-3-5-sonnet-20241022-v2:0',
            'us.anthropic.claude-3-5-haiku-20241022-v1:0'
        ]
        
        # Orchestration과 Observation은 Claude 모델만 허용
        if self.orchestration_model not in claude_models:
            return False
        if self.observation_model not in claude_models:
            return False
            
        return True
    
    def get_model_recommendations(self) -> dict:
        """권장 모델 조합 반환"""
        return {
            "high_performance": {
                "orchestration": "us.anthropic.claude-sonnet-4-20250514-v1:0",
                "action": "us.anthropic.claude-3-7-sonnet-20250219-v1:0", 
                "observation": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                "description": "최고 성능 (최고 비용)"
            },
            "balanced": {
                "orchestration": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
                "action": "us.amazon.nova-lite-v1:0",
                "observation": "us.anthropic.claude-3-5-haiku-20241022-v1:0", 
                "description": "균형잡힌 성능과 비용"
            },
            "cost_effective": {
                "orchestration": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
                "action": "us.amazon.nova-micro-v1:0",
                "observation": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
                "description": "비용 최적화 (기본 성능)"
            }
        }


# 사용 가능한 모델 목록
AVAILABLE_MODELS = {
    "Claude Sonnet 4": "us.anthropic.claude-sonnet-4-20250514-v1:0",
    "Claude 3.7 Sonnet": "us.anthropic.claude-3-7-sonnet-20250219-v1:0", 
    "Claude 3.5 Sonnet v2": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
    "Claude 3.5 Haiku": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
    "Nova Lite": "us.amazon.nova-lite-v1:0",
    "Nova Micro": "us.amazon.nova-micro-v1:0"
}

# 모델별 특성 정의
MODEL_CHARACTERISTICS = {
    "Claude Sonnet 4": {
        "type": "claude",
        "performance": "highest",
        "cost": "highest", 
        "suitable_for": ["orchestration", "observation"],
        "max_tokens": 8000,
        "description": "최고 성능의 Claude 모델"
    },
    "Claude 3.7 Sonnet": {
        "type": "claude",
        "performance": "very_high",
        "cost": "high",
        "suitable_for": ["orchestration", "observation"],
        "max_tokens": 8000,
        "description": "매우 높은 성능의 Claude 모델"
    },
    "Claude 3.5 Sonnet v2": {
        "type": "claude", 
        "performance": "high",
        "cost": "medium_high",
        "suitable_for": ["orchestration", "observation"],
        "max_tokens": 8000,
        "description": "높은 성능의 Claude 모델"
    },
    "Claude 3.5 Haiku": {
        "type": "claude",
        "performance": "good",
        "cost": "low",
        "suitable_for": ["orchestration", "action", "observation"],
        "max_tokens": 8000,
        "description": "빠르고 경제적인 Claude 모델"
    },
    "Nova Lite": {
        "type": "nova",
        "performance": "medium", 
        "cost": "very_low",
        "suitable_for": ["action"],
        "max_tokens": 5000,
        "description": "경제적인 Nova 모델 (Action 전용)"
    },
    "Nova Micro": {
        "type": "nova",
        "performance": "basic",
        "cost": "lowest",
        "suitable_for": ["action"],
        "max_tokens": 5000,
        "description": "가장 경제적인 Nova 모델 (Action 전용)"
    }
}

# AWS 리전
AWS_REGION = "us-west-2"

# Knowledge Base 기본 설정
KB_DEFAULT_CONFIG = {
    "search_type": "HYBRID",
    "max_results": 5
}
