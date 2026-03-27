from fastapi import APIRouter
from cmn.api.dependencies import get_company_schema
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends


logs_router = APIRouter(prefix="/api/logs",tags=["logs"])


@logs_router.post("/tools")
async def log_tools(db: AsyncSession = Depends(get_company_schema)):
        # 회사코드(company_cd)에 따라 해라서 해당 schema에 DB seesion 가져와서 저장
        return {"status": "tools logging"}


@logs_router.post("/graph")
async def log_grphs(db: AsyncSession = Depends(get_company_schema)):
    # 회사코드(company_cd)에 따라 해라서 해당 schema에 DB seesion 가져와서 저장
    return {"status": "api logging"}