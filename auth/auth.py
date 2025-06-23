from fastapi import APIRouter, HTTPException, Body, status, Depends
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import ConfigDict, BaseModel, Field, EmailStr
from pydantic.functional_validators import BeforeValidator

from typing import Optional, List
from typing_extensions import Annotated

from pymongo import AsyncMongoClient, ReturnDocument
from bson import ObjectId
from passlib.hash import sha256_crypt
from jose import jwt, JWTError
from passlib.context import CryptContext
from datetime import timedelta, datetime

uri = "mongodb+srv://aarush:Kv097f8P1vXZdM65@cluster0.nxphn.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
# Create a new client and connect to the server
client = AsyncMongoClient(uri)
db = client.BookRead
users = db.get_collection("users")
PyObjectId = Annotated[str, BeforeValidator(str)]

router = APIRouter()

SECRET_KEY = 'L3UyFYhcsv2LxbDHxJTUTII3mjTKwKw4'
ALGORITHM = 'HS256'

bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
oauth2_bearer = OAuth2PasswordBearer(tokenUrl='auth/login')


class UserBase(BaseModel):
    email: EmailStr = Field(..., min_length=3, max_length=512, description="email of user")
    username: str = Field(..., min_length=3, max_length=30, description="username")
    password: str = Field(..., min_length=8, max_length=512, description="password of user")


class UserCreate(UserBase):
    password_check: str = Field(..., min_length=8, max_length=512, description="password of user")
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_schema_extra={
            "example": {
                "username": "datguy",
                "email": "datguy@example.com",
                "password": "password1",
                "password_check": "password1"
            }
        }
    )


class User(UserBase):
    user_id: PyObjectId = Field(..., description='Unique identifier of user', alias='_id')


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = Field(..., min_length=3, max_length=512, description="email of user")
    username: Optional[str] = Field(..., min_length=3, max_length=30, description="username")
    password: str = Field(..., min_length=8, max_length=512, description="password of user")
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_schema_extra={
            "example": {
                "username": "datguy",
                "email": "datguy@example.com",
                "password": "your password"
            }
        }
    )


class PasswordUpdate(BaseModel):
    old_pass: str = Field(..., min_length=8, max_length=512, description="old password")
    new_pass: str = Field(..., min_length=8, max_length=512, description="new password")
    confirm_new_pass: str = Field(..., min_length=8, max_length=512, description="confirm new password")


class Token(BaseModel):
    access_token: str
    token_type: str


@router.get('/user/{user_id}', response_model=User)
async def get_user(user_id: str):
    if (
            user := await users.find_one({'_id': ObjectId(user_id)})
    ) is not None:
        return user
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Student {user_id} not found")


@router.get('/user', response_model=List[User])
async def get_users():
    return users.find()


@router.post('/register', response_model=User, status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate = Body(...)):
    if (await users.find_one({'username': user.username})) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"User with {user.username} as username already exists")
    if user.password != user.password_check:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Password must be same as password check")
    user.password = str(sha256_crypt.hash(user.password))
    new_user = await users.insert_one(
        user.model_dump(by_alias=True, exclude=["password_check"])
    )
    created_user = await users.find_one({"_id": new_user.inserted_id})
    return created_user


@router.post('/login', response_model=Token, status_code=status.HTTP_200_OK)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    if (user := await users.find_one({"username": form_data.username})) is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='No user with this username')
    if not sha256_crypt.verify(form_data.password, user['password']):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Wrong password')
    token = create_access_token(user['username'], str(user['_id']), timedelta(days=2))

    return {'access_token': token, 'token_type': 'bearer'}


@router.put('/{user_id})', response_model=User, status_code=status.HTTP_200_OK)
async def update_user(updated_user: UserUpdate, user_id: str):
    if (user := await users.find_one({"_id": ObjectId(user_id)})) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User does not exist')
    if not sha256_crypt.verify(updated_user.password, user["password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Wrong password')
    updated_user = {k: v for k, v in updated_user.model_dump(by_alias=True).items() if v is not None and k is not "password"}
    if len(updated_user) < 1:
        return user
    update_result = await users.find_one_and_update(
        {"_id": ObjectId(user_id)},
        {"$set": updated_user},
        return_document=ReturnDocument.AFTER
    )
    return update_result


@router.put('/password/{user_id}', response_model=User, status_code=status.HTTP_200_OK)
async def update_password(updated_password: PasswordUpdate, user_id: str):
    if (user := await users.find_one({"_id": ObjectId(user_id)})) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User does not exist')
    if not sha256_crypt.verify(updated_password.old_pass, user["password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong password")
    if updated_password.new_pass != updated_password.confirm_new_pass:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Confirm and password do not match")
    updated_password = {"password": sha256_crypt.hash(updated_password.new_pass)}
    update_result = await users.find_one_and_update(
        {"_id": ObjectId(user_id)},
        {"$set": updated_password},
        return_document=ReturnDocument.AFTER
    )
    return update_result


@router.delete('/{user_id}', response_description="Delete a user")
async def delete_user(user_id: str):
    delete_result = await users.delete_one({"_id": ObjectId(user_id)})

    if delete_result.deleted_count == 1:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User does not exist')


def create_access_token(username: str, user_id: str, expired_delta: timedelta):
    encode = {'sub': username, 'id': user_id}
    expires = datetime.utcnow() + expired_delta
    encode.update({'exp': expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: Annotated[str, Depends(oauth2_bearer)]):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get('sub')
        user_id: str = payload.get('id')
        if username is None or user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Could not validate user')
        return {'username': username, 'user_id': user_id}
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Could not validate user')


user_dependency = Annotated[dict, Depends(get_current_user)]


@router.get('/', status_code=status.HTTP_200_OK)
def get_current_user(user: user_dependency):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication Failed')
    return {"User": user}
