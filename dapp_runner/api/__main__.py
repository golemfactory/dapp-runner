"""Dapp Runner API."""
import json

from fastapi import FastAPI

from dapp_runner.runner import Runner

app = FastAPI()


@app.get("/")
async def root():  # noqa D103
    dapp_dict = Runner.get_instance().dapp.dict()
    return json.dumps(dapp_dict)
