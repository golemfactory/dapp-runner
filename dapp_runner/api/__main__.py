"""Dapp Runner API."""
import yaml
from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse

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


@app.post("/suspend")
async def suspend():
    """
    Suspend the app.

    Stop the dapp-runner without killing the services.
    Send back the YAML-encoded GAOM tree state from just before suspension.
    """
    runner = Runner.get_instance()
    dapp_dict = runner.dapp.dict()

    runner.request_suspend()

    return PlainTextResponse(content=yaml.dump(dapp_dict))
