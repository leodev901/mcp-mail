from fastmcp import FastMCP
from typing import Annotated, Optional
from loguru import logger

from app.clients.graph_client import graph_request
from fastmcp.server.dependencies import get_http_request
from app.models.user_info import UserInfo
from app.core.config import settings


DEFAULT_USER_EMAIL = settings.DEFAULT_USER_EMAIL
DEFAULT_COMPANY_CD = settings.DEFAULT_COMPANY_CD


def register_sharepoint_tools(mcp: FastMCP):

    def _get_request_current_user() -> UserInfo | None:
        try:
            request = get_http_request()
            return getattr(request.state, "current_user", None)
        except RuntimeError:
            return None


    @mcp.tool()
    async def list_drive_files(
        folder_id: Annotated[Optional[str], "조회할 대상 폴더의 ID (입력하지 않으면 루트 폴더 조회)"] = None,
        tok_k: Annotated[int, "최대 조회 건수 (기본 15)"] = 15,
        user_email: Annotated[Optional[str], "조회 대상자의 이메일 주소"] = "admin@leodev901.onmicrosoft.com",
    ) -> list[dict]:
        """사용자의 클라우드 드라이브(OneDrive/SharePoint 개인 영역) 내에 있는 파일 및 폴더 목록을 조회합니다.
        
        [LLM 에이전트 가이드]
        1. 사용자가 "내 드라이브에 무슨 파일 있어?", "루트 폴더 내용 보여줘" 할 때 사용합니다.
        2. 특정 폴더 내부를 보고 싶다면 `folder_id`를 명시하여 호출합니다.
        """
        current_user = _get_request_current_user()
        # if not current_user:
        #     raise ValueError("현재 사용자 정보를 찾을 수 없습니다.")
            
        # 1순위 파라미터 
        # 2순위 토큰 사용자 정보 
        # 3순위 Default 값
        if user_email is not None:
            query_email = user_email
            query_company_cd = DEFAULT_COMPANY_CD
        elif current_user is not None:
            query_email = current_user.email
            query_company_cd = current_user.company_cd
        else:
            query_email = DEFAULT_USER_EMAIL
            query_company_cd = DEFAULT_COMPANY_CD
        
        path = f"/drive/items/{folder_id}/children" if folder_id else "/drive/root/children"
        path += f"?$top={tok_k}"
        
        try:
            result = await graph_request(
                method="GET",
                path=path,
                user_email=query_email,
                company_cd=query_company_cd
            )
            
            items = result.get("value", [])
            parsed_items = []
            for item in items:
                is_folder = "folder" in item
                parsed_items.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "is_folder": is_folder,
                    "size_bytes": item.get("size", 0),
                    "created_time": item.get("createdDateTime"),
                    "last_modified_time": item.get("lastModifiedDateTime"),
                    "web_url": item.get("webUrl") # 브라우저에서 바로 열 수 있는 링크
                })
            return parsed_items
        except Exception as e:
            raise RuntimeError(f"드라이브 파일 목록 조회 중 오류 발생: {str(e)}")


    @mcp.tool()
    async def search_drive_files(
        query: Annotated[str, "검색할 파일명이나 본문에 포함된 키워드 (필수)"],
        tok_k: Annotated[int, "최대 조회 건수 (기본 10)"] = 10,
        user_email: Annotated[Optional[str], "조회 대상자의 이메일 주소"] = "admin@leodev901.onmicrosoft.com",
    ) -> list[dict]:
        """내 드라이브 전체에서 특정 키워드가 포함된 파일을 검색합니다.
        
        [LLM 에이전트 가이드]
        1. 사용자가 "주간업무보고 파일 어딨어?", "최근 기획서 찾아줘" 등의 광범위 검색을 원할 때 호출합니다.
        """
        current_user = _get_request_current_user()
        # if not current_user:
        #     raise ValueError("현재 사용자 정보를 찾을 수 없습니다.")
            
        # 1순위 파라미터 
        # 2순위 토큰 사용자 정보 
        # 3순위 Default 값
        if user_email is not None:
            query_email = user_email
            query_company_cd = DEFAULT_COMPANY_CD
        elif current_user is not None:
            query_email = current_user.email
            query_company_cd = current_user.company_cd
        else:
            query_email = DEFAULT_USER_EMAIL
            query_company_cd = DEFAULT_COMPANY_CD
        
        path = f"/drive/root/search(q='{query}')?$top={tok_k}"
        
        try:
            result = await graph_request(
                method="GET",
                path=path,
                user_email=query_email,
                company_cd=query_company_cd
            )
            
            items = result.get("value", [])
            parsed_items = []
            for item in items:
                is_folder = "folder" in item
                parsed_items.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "is_folder": is_folder,
                    "created_time": item.get("createdDateTime"),
                    "last_modified_time": item.get("lastModifiedDateTime"),
                    "web_url": item.get("webUrl")
                })
            return parsed_items
        except Exception as e:
            raise RuntimeError(f"파일 검색 중 오류 발생: {str(e)}")


    @mcp.tool()
    async def get_drive_file_info(
        item_id: Annotated[str, "세부 정보를 조회할 대상 파일/폴더의 고유 ID (필수)"],
        user_email: Annotated[Optional[str], "조회 대상자의 이메일 주소"] = "admin@leodev901.onmicrosoft.com",
    ) -> dict:
        """단일 파일에 대한 상세 다운로드 링크 및 메타데이터를 획득합니다.
        
        [LLM 에이전트 가이드]
        1. 검색 혹은 폴더 리스트에서 식별한 뒤, 해당 파일을 사용자가 '직접 다운로드' 할 수 있도록 다운로드 URL이나 세부 정보를 건네줄 때 쓰입니다.
        2. 응답의 `@microsoft.graph.downloadUrl` 키를 활용하여 사용자가 파일을 받을 수 있게 안내하세요.
        """
        current_user = _get_request_current_user()
        # if not current_user:
        #     raise ValueError("현재 사용자 정보를 찾을 수 없습니다.")
            
        # 1순위 파라미터 
        # 2순위 토큰 사용자 정보 
        # 3순위 Default 값
        if user_email is not None:
            query_email = user_email
            query_company_cd = DEFAULT_COMPANY_CD
        elif current_user is not None:
            query_email = current_user.email
            query_company_cd = current_user.company_cd
        else:
            query_email = DEFAULT_USER_EMAIL
            query_company_cd = DEFAULT_COMPANY_CD
        
        path = f"/drive/items/{item_id}"
        
        try:
            item = await graph_request(
                method="GET",
                path=path,
                user_email=query_email,
                company_cd=query_company_cd
            )
            
            return {
                "id": item.get("id"),
                "name": item.get("name"),
                "size_bytes": item.get("size"),
                "mime_type": item.get("file", {}).get("mimeType", "unknown"),
                "web_url": item.get("webUrl"),
                "download_url": item.get("@microsoft.graph.downloadUrl", "폴더이거나 다운로드를 지원하지 않음"),
                "created_time": item.get("createdDateTime"),
                "last_modified_time": item.get("lastModifiedDateTime")
            }
        except Exception as e:
            raise RuntimeError(f"파일 상세 정보 조회 중 오류 발생: {str(e)}")
