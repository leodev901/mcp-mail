from fastmcp import FastMCP
from typing import Annotated, Optional
from loguru import logger

from app.clients.graph_client import graph_request
from fastmcp.server.dependencies import get_http_request
from app.models.user_info import UserInfo

def register_teams_tools(mcp: FastMCP):

    def _get_request_current_user() -> UserInfo | None:
        try:
            request = get_http_request()
            return getattr(request.state, "current_user", None)
        except RuntimeError:
            return None


    @mcp.tool()
    async def list_my_chats(
        tok_k: Annotated[int, "최대 조회할 채팅방 개수 (기본 10)"] = 10,
        user_email: Annotated[Optional[str], "조회 대상자의 이메일 주소"] = "admin@leodev901.onmicrosoft.com",
    ) -> list[dict]:
        """사용자가 참여 중인 Teams 채팅방(1:1, 그룹, 미팅 등) 목록을 조회합니다.
        
        [LLM 에이전트 가이드]
        1. 사용자가 "내 채팅방 목록 보여줘" 또는 "최근에 대화한 채팅방 찾아줘"라고 요청할 때 사용합니다.
        2. 반환되는 `id` (chat_id)는 향후 특정 채팅방의 메시지를 조회하거나 메시지를 보낼 때 사용되는 **필수 식별자**입니다.
        """
        current_user = _get_request_current_user()
        # if not current_user:
            # raise ValueError("현재 사용자 정보를 찾을 수 없습니다.")
            
        # 1순위: user_email 파라미터
        # 2순위: current_user
        # 3순위: 기본값
        if user_email is not None:
            query_email = user_email
            query_company_cd = "leodev901"
        elif current_user:
            query_email = current_user.email
            query_company_cd = current_user.company_cd
        else:
            query_email = "admin@leodev901.onmicrosoft.com" #DEFAULT_USER_EMAIL
            query_company_cd = "leodev901" #DEFAULT_COMPANY_CD
        
        path = f"/chats?$top={tok_k}&$expand=lastMessagePreview"
        
        try:
            result = await graph_request(
                method="GET",
                path=path,
                user_email=query_email,
                company_cd=query_company_cd
            )
            
            chats = result.get("value", [])
            parsed_chats = []
            for chat in chats:
                topic = chat.get("topic") or "(제목 없는 채팅방)"
                chat_type = chat.get("chatType", "unknown")
                preview = chat.get("lastMessagePreview", {})
                last_msg_body = preview.get("body", {}).get("content", "")
                
                parsed_chats.append({
                    "id": chat.get("id"),
                    "topic": topic,
                    "chat_type": chat_type,
                    "last_message_preview": last_msg_body,
                    "last_updated": chat.get("lastUpdatedDateTime")
                })
            
            return parsed_chats
        except Exception as e:
            raise RuntimeError(f"채팅방 목록 조회 중 오류 발생: {str(e)}")


    @mcp.tool()
    async def get_chat_messages(
        chat_id: Annotated[str, "메시지를 조회할 대상 채팅방의 고유 ID. (list_my_chats 에서 획득한 id)"],
        tok_k: Annotated[int, "최대 가져올 최근 메시지 수 (기본 15)"] = 15,
        user_email: Annotated[Optional[str], "조회 대상자의 이메일 주소"] = "admin@leodev901.onmicrosoft.com",
    ) -> list[dict]:
        """지정된 채팅방 내부의 최근 메시지 내역을 다건 조회합니다.
        
        [LLM 에이전트 가이드]
        1. 사용자가 특정 채팅방의 최근 대화 내역이나 맥락을 확인할 때 사용합니다.
        2. 최신순(내림차순)으로 반환됩니다.
        """
        current_user = _get_request_current_user()
        # if not current_user:
            # raise ValueError("현재 사용자 정보를 찾을 수 없습니다.")
            
        # 1순위: user_email 파라미터
        # 2순위: current_user
        # 3순위: 기본값
        if user_email is not None:
            query_email = user_email
            query_company_cd = "leodev901"
        elif current_user:
            query_email = current_user.email
            query_company_cd = current_user.company_cd
        else:
            query_email = "admin@leodev901.onmicrosoft.com" #DEFAULT_USER_EMAIL
            query_company_cd = "leodev901" #DEFAULT_COMPANY_CD
        

        path = f"/chats/{chat_id}/messages?$top={tok_k}&$orderby=createdDateTime desc"
        
        try:
            result = await graph_request(
                method="GET",
                path=path,
                user_email=query_email,
                company_cd=query_company_cd
            )
            
            messages = result.get("value", [])
            parsed_messages = []
            for msg in messages:
                # 시스템 메시지 등 제외하고 일반 메시지 위주 파싱
                content = msg.get("body", {}).get("content", "")
                sender = msg.get("from", {}).get("user", {}).get("displayName", "알 수 없음")
                msg_type = msg.get("messageType", "unknown")
                
                parsed_messages.append({
                    "id": msg.get("id"),
                    "sender": sender,
                    "created_time": msg.get("createdDateTime"),
                    "content": content,
                    "type": msg_type
                })
            return parsed_messages
        except Exception as e:
            raise RuntimeError(f"채팅 메시지 조회 중 오류 발생: {str(e)}")


    @mcp.tool()
    async def send_chat_message(
        chat_id: Annotated[str, "메시지를 보낼 대상 채팅방의 고유 ID (필수)"],
        content: Annotated[str, "보낼 메시지 본문 (텍스트 또는 HTML)"],
        user_email: Annotated[Optional[str], "메시지를 보내는 주체가 될 이메일 주소"] = "admin@leodev901.onmicrosoft.com",
    ) -> dict:
        """기존 Teams 채팅방에 새로운 메시지를 전송합니다.
        
        [LLM 에이전트 가이드]
        1. 사용자가 "마케팅팀 방에 이 문서 전달했다고 메시지 남겨줘"와 같이 메신저 발송을 요청할 때 사용합니다.
        """
        current_user = _get_request_current_user()
        # if not current_user:
            # raise ValueError("현재 사용자 정보를 찾을 수 없습니다.")
            
        # 1순위: user_email 파라미터
        # 2순위: current_user
        # 3순위: 기본값
        if user_email is not None:
            query_email = user_email
            query_company_cd = "leodev901"
        elif current_user:
            query_email = current_user.email
            query_company_cd = current_user.company_cd
        else:
            query_email = "admin@leodev901.onmicrosoft.com" #DEFAULT_USER_EMAIL
            query_company_cd = "leodev901" #DEFAULT_COMPANY_CD
        

        path = f"/chats/{chat_id}/messages"
        payload = {
            "body": {
                "contentType": "html",
                "content": content
            }
        }
        
        try:
            result = await graph_request(
                method="POST",
                path=path,
                json_body=payload,
                user_email=query_email,
                company_cd=query_company_cd
            )
            return {
                "status": "success",
                "message_id": result.get("id"),
                "created_time": result.get("createdDateTime")
            }
        except Exception as e:
            raise RuntimeError(f"메시지 전송 중 오류 발생: {str(e)}")
