from fastapi import FastAPI
from cmn.api.endpoint.logs_router import logs_router
from cmn.api.endpoint.auth_router import auth_router
from cmn.api.endpoint.utils_router import utils_router

from cmn.core.config import settings





def register_router(app:FastAPI):

    #로컬에서 Authorize 헤더를 encode/decode 하기 위함
    if getattr(settings, "ENV", 'local').lower() == 'local': 
        app.include_router(utils_router)
    
    app.include_router(auth_router)
    app.include_router(logs_router)

    # health check
    @app.post("/health")
    async def health():
        return {"status": "ok"}
    

    






    
    

    