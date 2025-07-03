"""
Amazon Bedrock 클라이언트 유틸리티
"""

import json
import boto3
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError
import streamlit as st

from .config import AWS_REGION


class BedrockClient:
    """Amazon Bedrock 클라이언트 래퍼"""
    
    def __init__(self, region_name: str = AWS_REGION):
        """
        Bedrock 클라이언트 초기화
        
        Args:
            region_name: AWS 리전명
        """
        try:
            self.bedrock_runtime = boto3.client(
                'bedrock-runtime',
                region_name=region_name
            )
            self.region_name = region_name
        except Exception as e:
            st.error(f"Bedrock 클라이언트 초기화 실패: {str(e)}")
            raise
    
    def invoke_model(self, 
                    model_id: str, 
                    prompt: str, 
                    temperature: float = 0.1,
                    max_tokens: int = 4000,
                    system_prompt: str = "") -> str:
        """
        Bedrock 모델 호출
        
        Args:
            model_id: 모델 ID
            prompt: 사용자 프롬프트
            temperature: 온도 설정
            max_tokens: 최대 토큰 수
            system_prompt: 시스템 프롬프트
            
        Returns:
            모델 응답 텍스트
        """
        try:
            # 모델별 요청 형식 구성
            if 'claude' in model_id.lower():
                body = self._build_claude_request(
                    prompt, temperature, max_tokens, system_prompt
                )
            elif 'nova' in model_id.lower():
                body = self._build_nova_request(
                    prompt, temperature, max_tokens, system_prompt
                )
            else:
                raise ValueError(f"지원하지 않는 모델: {model_id}")
            
            # API 호출
            response = self.bedrock_runtime.invoke_model(
                modelId=model_id,
                body=json.dumps(body),
                contentType='application/json'
            )
            
            # 응답 파싱
            response_body = json.loads(response['body'].read())
            return self._extract_response_text(response_body, model_id)
            
        except ClientError as e:
            error_msg = f"Bedrock API 호출 실패: {str(e)}"
            st.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"모델 호출 중 오류: {str(e)}"
            st.error(error_msg)
            raise Exception(error_msg)
    
    def _build_claude_request(self, 
                             prompt: str, 
                             temperature: float, 
                             max_tokens: int,
                             system_prompt: str) -> Dict[str, Any]:
        """Claude 모델용 요청 구성"""
        
        # Claude API v3 형식 사용
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        # System 프롬프트가 있는 경우 별도 필드로 처리
        if system_prompt:
            request_body["system"] = system_prompt
        
        # Messages 배열에는 user 메시지만 포함
        request_body["messages"] = [
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        return request_body
    
    def _build_nova_request(self, 
                           prompt: str, 
                           temperature: float, 
                           max_tokens: int,
                           system_prompt: str) -> Dict[str, Any]:
        """Nova 모델용 요청 구성"""
        messages = []
        
        if system_prompt:
            messages.append({
                "role": "system",
                "content": [{"text": system_prompt}]
            })
        
        messages.append({
            "role": "user", 
            "content": [{"text": prompt}]
        })
        
        return {
            "messages": messages,
            "inferenceConfig": {
                "temperature": temperature,
                "maxTokens": max_tokens
            }
        }
    
    def _extract_response_text(self, response_body: Dict, model_id: str) -> str:
        """응답에서 텍스트 추출"""
        try:
            if 'claude' in model_id.lower():
                # Claude 응답 형식
                if 'content' in response_body and response_body['content']:
                    return response_body['content'][0]['text']
                else:
                    return "응답을 파싱할 수 없습니다."
            
            elif 'nova' in model_id.lower():
                # Nova 응답 형식 (새로운 형식)
                if 'output' in response_body and 'message' in response_body['output']:
                    content = response_body['output']['message'].get('content', [])
                    if content and len(content) > 0:
                        return content[0].get('text', '응답을 파싱할 수 없습니다.')
                    else:
                        return "응답을 파싱할 수 없습니다."
                # 이전 형식도 지원
                elif 'results' in response_body and response_body['results']:
                    return response_body['results'][0]['outputText']
                else:
                    return "응답을 파싱할 수 없습니다."
            
            else:
                return str(response_body)
                
        except (KeyError, IndexError, TypeError) as e:
            st.error(f"응답 파싱 오류: {str(e)}")
            return f"응답 파싱 실패: {str(response_body)}"
    
    def test_connection(self) -> bool:
        """Bedrock 연결 테스트"""
        try:
            # 간단한 테스트 호출
            test_response = self.invoke_model(
                model_id="us.anthropic.claude-3-5-haiku-20241022-v1:0",
                prompt="Hello",
                temperature=0.1,
                max_tokens=10
            )
            return bool(test_response)
        except Exception as e:
            st.error(f"Bedrock 연결 테스트 실패: {str(e)}")
            return False
