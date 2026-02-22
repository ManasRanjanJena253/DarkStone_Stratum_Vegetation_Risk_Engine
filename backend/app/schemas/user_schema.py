# Reasons for using schema :
# The incoming request might have fields you don't want in the DB (or vice versa)
# You never want to accidentally return sensitive fields like hashed_pwd in a response
# SQLAlchemy objects aren't directly JSON-serializable — FastAPI needs Pydantic models for that
# Schemas act as the contract layer — they define what comes in and what goes out through your endpoints, completely separate from what's in your DB.

from pydantic import BaseModel, EmailStr
from datetime import date

class UserBase(BaseModel):
    email : EmailStr
    is_active : bool = True

# Classes for api's which will take input from the user
class CreateUser(UserBase):
    password : str

class EnrollUser(BaseModel):    # It will get user_id from jwt token
    subscription_plan : str

class SendReq(BaseModel):   # Will get user_id from jwt token
    pass

# Classes for return values by apis
class UserCreated(BaseModel):   # Don't need to inherit from UserBase as it doesn't need is_active field.
    user_id : str
    email : EmailStr     # Also returning the email from which the user registered .

    model_config = {"from_attributes": True}

class UserLogin(UserBase):
    user_id : str
    session_id : str  # To be stored in redis for that particular session of the user.

    model_config = {"from_attributes": True}   # This is needed for each pydantic class which validates ORM form of data, otherwise it will through error.

class UserEnrollment(UserBase):
    subscription_plan : str
    start_date : date
    end_date : date

    model_config = {"from_attributes": True}

class ReqAccepted(UserBase):
    user_id : str
    task : str
    status : str    # Accepted or Not

    model_config = {"from_attributes": True}

# Log schemas
class UserLogCreate(BaseModel):      # Used internally by Celery task
    req_id: str
    user_id: str
    task: str
    req_received: bool
    req_processed: bool
    error_log: str | None = None    # This tells pydantic that this field can have both str and None values, if written as error : str = None, it will throw error. Because None is not str type.

class UserLogResponse(BaseModel):
    model_config = {"from_attributes": True}
    req_id: str
    task: str
    req_received: bool
    req_processed: bool
    error_log: str | None = None

