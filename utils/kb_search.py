"""
Amazon Bedrock Knowledge Base 검색 유틸리티
"""

import boto3
from typing import List, Dict, Optional
from botocore.exceptions import ClientError
import streamlit as st

from .config import AWS_REGION, KB_DEFAULT_CONFIG


class KnowledgeBaseSearcher:
    """Amazon Bedrock Knowledge Base 검색 클래스"""
    
    def __init__(self, region_name: str = AWS_REGION):
        """
        KB 검색 클라이언트 초기화
        
        Args:
            region_name: AWS 리전명
        """
        try:
            self.bedrock_agent_runtime = boto3.client(
                'bedrock-agent-runtime',
                region_name=region_name
            )
            self.region_name = region_name
        except Exception as e:
            st.error(f"Bedrock Agent Runtime 클라이언트 초기화 실패: {str(e)}")
            raise
    
    def search(self, 
              kb_id: str, 
              query: str, 
              max_results: int = KB_DEFAULT_CONFIG["max_results"],
              search_type: str = KB_DEFAULT_CONFIG["search_type"]) -> List[Dict]:
        """
        Knowledge Base에서 검색 수행
        
        Args:
            kb_id: Knowledge Base ID
            query: 검색 쿼리
            max_results: 최대 결과 수
            search_type: 검색 타입 (SEMANTIC, HYBRID)
            
        Returns:
            검색 결과 리스트
        """
        if not kb_id or not kb_id.strip():
            st.warning("Knowledge Base ID가 설정되지 않았습니다.")
            return []
        
        try:
            response = self.bedrock_agent_runtime.retrieve(
                knowledgeBaseId=kb_id,
                retrievalQuery={'text': query},
                retrievalConfiguration={
                    'vectorSearchConfiguration': {
                        'numberOfResults': max_results,
                        'overrideSearchType': search_type
                    }
                }
            )
            
            search_results = []
            for i, result in enumerate(response.get('retrievalResults', [])):
                search_result = {
                    'rank': i + 1,
                    'citation_id': i + 1,  # Citation 번호 추가
                    'content': result.get('content', {}).get('text', ''),
                    'score': result.get('score', 0.0),
                    'source': self._extract_source(result),
                    'metadata': result.get('metadata', {})
                }
                search_results.append(search_result)
            
            return search_results
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            if error_code == 'ResourceNotFoundException':
                st.error(f"Knowledge Base를 찾을 수 없습니다: {kb_id}")
            elif error_code == 'AccessDeniedException':
                st.error("Knowledge Base 접근 권한이 없습니다.")
            else:
                st.error(f"KB 검색 오류 ({error_code}): {error_message}")
            
            return []
            
        except Exception as e:
            st.error(f"KB 검색 중 예상치 못한 오류: {str(e)}")
            return []
    
    def search_multiple_queries(self, 
                               kb_id: str, 
                               queries: List[str],
                               max_results_per_query: int = 3) -> List[Dict]:
        """
        여러 쿼리로 검색하고 결과 통합
        
        Args:
            kb_id: Knowledge Base ID
            queries: 검색 쿼리 리스트
            max_results_per_query: 쿼리당 최대 결과 수
            
        Returns:
            통합된 검색 결과 (중복 제거 및 점수순 정렬)
        """
        all_results = []
        seen_contents = set()
        
        for query in queries:
            if not query.strip():
                continue
                
            results = self.search(
                kb_id=kb_id,
                query=query,
                max_results=max_results_per_query
            )
            
            # 중복 제거
            for result in results:
                content_hash = hash(result['content'][:100])  # 첫 100자로 중복 판단
                if content_hash not in seen_contents:
                    result['query'] = query  # 어떤 쿼리로 찾았는지 기록
                    all_results.append(result)
                    seen_contents.add(content_hash)
        
        # 점수순으로 정렬하고 상위 5개만 반환
        all_results.sort(key=lambda x: x['score'], reverse=True)
        return all_results[:KB_DEFAULT_CONFIG["max_results"]]
    
    def _extract_source(self, retrieval_result: Dict) -> str:
        """검색 결과에서 소스 정보 추출"""
        try:
            location = retrieval_result.get('location', {})
            location_type = location.get('type', 'UNKNOWN')
            
            if location_type == 'S3':
                s3_location = location.get('s3Location', {})
                uri = s3_location.get('uri', 'Unknown S3 Location')
                return f"S3: {uri}"
            
            elif location_type == 'WEB':
                web_location = location.get('webLocation', {})
                url = web_location.get('url', 'Unknown Web Location')
                return f"Web: {url}"
            
            elif location_type == 'CONFLUENCE':
                confluence_location = location.get('confluenceLocation', {})
                url = confluence_location.get('url', 'Unknown Confluence Location')
                return f"Confluence: {url}"
            
            else:
                return f"{location_type}: Unknown Location"
                
        except Exception as e:
            return f"Source extraction error: {str(e)}"
    
    def test_kb_connection(self, kb_id: str) -> bool:
        """Knowledge Base 연결 테스트"""
        if not kb_id or not kb_id.strip():
            return False
        
        try:
            # 간단한 테스트 검색
            results = self.search(
                kb_id=kb_id,
                query="test",
                max_results=1
            )
            return True  # 오류가 없으면 연결 성공
        except Exception as e:
            st.error(f"KB 연결 테스트 실패: {str(e)}")
            return False
