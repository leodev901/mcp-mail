from fastapi import FastAPI
from cmn.api.endpoint.logs_router import logs_router
from cmn.api.endpoint.auth_router import auth_router
from cmn.api.endpoint.utils_router import utils_router






def register_router(app:FastAPI):

    app.include_router(utils_router)
    
    app.include_router(auth_router)
    app.include_router(logs_router)



    @app.post("/health")
    async def health():
        return {"status": "ok"}
    

    






    
    

    