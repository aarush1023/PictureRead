from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from auth import router as auth
from models import router as models
import os
import keys

uri = keys.MONGO_URI
# Create a new client and connect to the server
client = MongoClient(uri, server_api=ServerApi('1'))

api = FastAPI()
api.include_router(auth, prefix='/auth')
api.include_router(models, prefix='/model')


class Health(BaseModel):
    running: bool = Field(True, description='Determine whether API is running or not')


@api.get('/healthz', response_model=Health, status_code=status.HTTP_200_OK)
def api_health():
    return Health(running=True)
