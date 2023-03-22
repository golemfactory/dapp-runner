"""Dapp Runner API."""
from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse

from dapp_runner.runner import Runner

app = FastAPI()


@app.get("/")
async def root():
    """Redirect to the API docs."""
    return RedirectResponse(url="/docs")


@app.get("/gaom")
async def get_gaom():
    """Retrieve the application's GAOM tree."""
    dapp_dict = Runner.get_instance().dapp.dict()
    return JSONResponse(content=dapp_dict)
