from fastapi import FastAPI

from dapp_runner.runner import Runner

app = FastAPI()

import json


@app.get("/")
async def root():
    dapp_dict = Runner.get_instance().dapp.dict()
    return json.dumps(dapp_dict)
