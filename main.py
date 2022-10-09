from fastapi import FastAPI

from httprunner import __version__
from routers import run

app = FastAPI()

@app.get("/hrun/version")
async def get_hrun_version():
    return {"code": 0, "message": "success", "result": {"HttpRunner": __version__}}

app.include_router(run.router)
