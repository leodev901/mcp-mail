from fastapi import FastAPI
from cmn.api.endpoint.logs import logs_router
from cmn.api.endpoint.auth import m365_oauth_router





def register_router(app:FastAPI):

    app.include_router(logs_router)
    app.include_router(m365_oauth_router)

    @app.post("/health")
    async def health():
        return {"status": "ok"}

    






    
    

    