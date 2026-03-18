from app.clients.graph_client import graph_request
from typing import Optional, Annotated
from fastmcp import FastMCP
from loguru import logger
from app.models.user_info import UserInfo
from fastmcp.server.dependencies import get_http_request

def register_todo_tools(mcp: FastMCP):
    
    def _get_request_current_user() -> UserInfo | None:
        try:
            request = get_http_request()
            return getattr(request.state, "current_user", None)
        except RuntimeError:
            return None
    
    @mcp.tool()
    async def todo_list_task_lists(
        title: Annotated[Optional[str], "할 일 목록의 제목"] = None,
        user_email: Annotated[Optional[str], "조회 대상자의 이메일 주소"] = None,  
    ) -> list:
        """
        Microsoft Graph API를 사용하여 할 일 목록을 읽어옵니다.
        이 툴은 할 일(task) 도구를 사용하기 위한 할 일 목록 ID를 찾는 용도로 사용됩니다.
        사용 자가 특정 할 일(task)에 대한 작업을 요청할 때, 이 도구를 사용하여 해당 할 일의 목록 ID를 찾은 뒤, 반한 된 tas_list_id를 사용하여 할 일(task) 도구를 호출해야 합니다.

        [LLM 에이전트 사용 가이드]
        1. 사용자가 "할 일 확인해줘" 혹은 "오늘 할 일 보여줘" 할 일을 확인 할 때 호출하세요. 
        2. 반환값은 딕셔너리(dict) 요소들로 구성된 형태의 리스트(list)입니다. 필요한 항목(제목, 마감일 등)을 가공하여 사용자에게 응답하세요.

        Args:
            - title (str): 할 일 목록의 제목 (기본값: None)
            - user_email (str, optional): 조회 대상자의 이메일 주소 (기본값: None)

        Returns:
            list: 조건에 맞는 할 일 목록을 담고 있는 딕셔너리의 리스트입니다.
        """
        try:
            current_user = _get_request_current_user()

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

            path = f"/todo/lists"
            if title is not None:
                path += f"?$filter=title eq '{title}'"
            
            result = await graph_request(
                method="GET",
                path=path,
                user_email=query_email,
                company_cd=query_company_cd
            )

            task_lists = result.get("value", [])
            if not task_lists:
                return []
            
            return task_lists

            # parsed_task_lists = []
            # for task_list in task_lists:
            #     parsed_task_lists.append({
            #         "id": task_list.get("id"),
            #         "title": task_list.get("title", "(제목 없음)"),
            #         "due_date": task_list.get("dueDateTime"),
            #         "status": task.get("status")
            #     })

            # return parsed_tasks

        except Exception as e:
            raise RuntimeError(f"할 일 조회 도중 오류 발생: {str(e)}")




    @mcp.tool()
    async def todo_list_tasks(
        task_list_id: Annotated[str, "할 일 목록의 ID"],
        user_email: Annotated[Optional[str], "조회 대상자의 이메일 주소"] = None,
        top_k: Annotated[Optional[int], "최대 조회할 할 일 개수"] = 10,
    ) -> list:
        """
        Microsoft Graph API를 사용하여 특정 할 일 목록에 속한 할 일들을 읽어옵니다.


        [LLM 에이전트 사용 가이드]
        1. 사용자가 "할 일 확인해줘" 혹은 "오늘 할 일 보여줘" 할 일을 확인 할 때 호출하세요. 
        2. 사용 자가 작업 목록 ID를 명시하지 않은 경우, todo_list_task_lists()를 호출하여 작업 목록 ID를 찾은 뒤, 반한 된 tas_list_id를 사용하여 todo_list_tasks()를 호출해야 합니다.
        3. 반환값은 딕셔너리(dict) 요소들로 구성된 형태의 리스트(list)입니다. 필요한 항목(제목, 마감일 등)을 가공하여 사용자에게 응답하세요.

        Args:
            - task_list_id (str): 할 일 목록의 ID (기본값: None)
            - user_email (str, optional): 조회 대상자의 이메일 주소 (기본값: None)
            - top_k (int, optional): 최대 조회할 할 일 개수 (기본값: 10)

        Returns:
            list: 조건에 맞는 할 일 목록을 담고 있는 딕셔너리의 리스트입니다.
        """
        try:
            current_user = _get_request_current_user()

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

            path = (
                f"/todo/lists/{task_list_id}/tasks"
                f"?$top={top_k}&$count=true"
                f"&$orderby=createdDateTime desc"
            )
            
            result = await graph_request(
                method="GET",
                path=path,
                user_email=query_email,
                company_cd=query_company_cd
            )

            tasks = result.get("value", [])
            if not tasks:
                return []
            
            return tasks

        except Exception as e:
            raise RuntimeError(f"할 일 조회 도중 오류 발생: {str(e)}")


    @mcp.tool()
    async def todo_create_task(
        task_list_id: Annotated[str, "할 일 목록의 ID"],
        title: Annotated[str, "할 일의 제목"],
        user_email: Annotated[Optional[str], "할 일을 생성할 사용자의 이메일 주소"] = None,
        due_date: Annotated[Optional[str], "할 일의 마감일 (YYYY-MM-DD 형식)"] = None,
    ) -> dict:
        """
        Microsoft Graph API를 사용하여 특정 할 일 목록에 새로운 할 일을 생성합니다.


        [LLM 에이전트 사용 가이드]
        1. 사용자가 "할 일 추가해줘" 혹은 "오늘 할 일 보여줘" 할 일을 확인 할 때 호출하세요. 
        2. 사용 자가 작업 목록 ID를 명시하지 않은 경우, todo_list_task_lists()를 호출하여 작업 목록 ID를 찾은 뒤, 반한 된 tas_list_id를 사용하여 이 도구를 호출해야 합니다.
        3. 반환값은 딕셔너리(dict) 요소들로 구성된 형태의 리스트(list)입니다. 필요한 항목(제목, 마감일 등)을 가공하여 사용자에게 응답하세요.

        Args:
            - task_list_id (str): 할 일 목록의 ID (기본값: None)
            - title (str): 할 일의 제목 (기본값: None)
            - user_email (str, optional): 할 일을 생성할 사용자의 이메일 주소 (기본값: None)
            - due_date (str, optional): 할 일의 마감일 (YYYY-MM-DD 형식) (기본값: None)

        Returns:
            dict: 생성된 할 일 정보를 담고 있는 딕셔너리입니다.
        """
        try:
            current_user = _get_request_current_user()

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

            path = f"/todo/lists/{task_list_id}/tasks"

            body = {
                "title": title,
                "dueDateTime": due_date
            }
            
            result = await graph_request(
                method="POST",
                path=path,
                user_email=query_email,
                company_cd=query_company_cd,
                json_body=body
            )

            return result

        except Exception as e:
            raise RuntimeError(f"할 일 생성 도중 오류 발생: {str(e)}")


    @mcp.tool()
    async def todo_update_task(
        task_list_id: Annotated[str, "할 일 목록의 ID"],
        task_id: Annotated[str, "할 일의 ID"],
        title: Annotated[Optional[str], "할 일의 제목"] = None,
        user_email: Annotated[Optional[str], "할 일을 수정할 사용자의 이메일 주소"] = None,
        due_date: Annotated[Optional[str], "할 일의 마감일 (YYYY-MM-DD 형식)"] = None,
    ) -> dict:
        """
        Microsoft Graph API를 사용하여 특정 할 일 목록에 새로운 할 일을 생성합니다.


        [LLM 에이전트 사용 가이드]
        1. 사용자가 "할 일 추가해줘" 혹은 "오늘 할 일 보여줘" 할 일을 확인 할 때 호출하세요. 
        2. 사용 자가 작업 목록 ID를 명시하지 않은 경우, todo_list_task_lists()를 호출하여 작업 목록 ID를 찾은 뒤, 반한 된 tas_list_id를 사용하여 todo_list_tasks()를 호출해야 합니다.
        3. 반환값은 딕셔너리(dict) 요소들로 구성된 형태의 리스트(list)입니다. 필요한 항목(제목, 마감일 등)을 가공하여 사용자에게 응답하세요.

        Args:
            - task_list_id (str): 할 일 목록의 ID (기본값: None)
            - title (str): 할 일의 제목 (기본값: None)
            - user_email (str, optional): 할 일을 생성할 사용자의 이메일 주소 (기본값: None)
            - due_date (str, optional): 할 일의 마감일 (YYYY-MM-DD 형식) (기본값: None)

        Returns:
            dict: 생성된 할 일 정보를 담고 있는 딕셔너리입니다.
        """
        try:
            current_user = _get_request_current_user()

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

            path = f"/todo/lists/{task_list_id}/tasks"
            
            result = await graph_request(
                method="PATCH",
                path=path,
                user_email=query_email,
                company_cd=query_company_cd
            )

            tasks = result.get("value", [])
            if not tasks:
                return []
            
            return tasks

        except Exception as e:
            raise RuntimeError(f"할 일 수정 도중 오류 발생: {str(e)}")


    @mcp.tool()
    async def todo_delete_task(
        task_list_id: Annotated[str, "할 일 목록의 ID"],
        task_id: Annotated[str, "할 일의 ID"],
        user_email: Annotated[Optional[str], "할 일을 삭제할 사용자의 이메일 주소"] = None,
    ) -> dict:
        """
        Microsoft Graph API를 사용하여 특정 할 일 목록에 새로운 할 일을 생성합니다.


        [LLM 에이전트 사용 가이드]
        1. 사용자가 "할 일 추가해줘" 혹은 "오늘 할 일 보여줘" 할 일을 확인 할 때 호출하세요. 
        2. 사용 자가 작업 목록 ID를 명시하지 않은 경우, todo_list_task_lists()를 호출하여 작업 목록 ID를 찾은 뒤, 반한 된 tas_list_id를 사용하여 todo_list_tasks()를 호출해야 합니다.
        3. 반환값은 딕셔너리(dict) 요소들로 구성된 형태의 리스트(list)입니다. 필요한 항목(제목, 마감일 등)을 가공하여 사용자에게 응답하세요.

        Args:
            - task_list_id (str): 할 일 목록의 ID (기본값: None)
            - title (str): 할 일의 제목 (기본값: None)
            - user_email (str, optional): 할 일을 생성할 사용자의 이메일 주소 (기본값: None)
            - due_date (str, optional): 할 일의 마감일 (YYYY-MM-DD 형식) (기본값: None)

        Returns:
            dict: 생성된 할 일 정보를 담고 있는 딕셔너리입니다.
        """
        try:
            current_user = _get_request_current_user()

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

            path = f"/todo/lists/{task_list_id}/tasks"
            
            result = await graph_request(
                method="DELETE",
                path=path,
                user_email=query_email,
                company_cd=query_company_cd
            )

            tasks = result.get("value", [])
            if not tasks:
                return []
            
            return tasks

        except Exception as e:
            raise RuntimeError(f"할 일 삭제 도중 오류 발생: {str(e)}")