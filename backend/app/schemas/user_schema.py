from pydantic import BaseModel, EmailStr
from datetime import date
from typing import Optional


class UserBase(BaseModel):
    email: EmailStr
    is_active: bool = True


class CreateUser(UserBase):
    password: str


class EnrollUser(BaseModel):
    subscription_plan: str


class SendReq(BaseModel):
    pass


class UserCreated(BaseModel):
    user_id: str
    email: EmailStr

    model_config = {"from_attributes": True}


class UserLoginInput(BaseModel):
    email: EmailStr
    password: str

    model_config = {"from_attributes": True}


class UserEnrollment(UserBase):
    subscription_plan: str
    start_date: date
    end_date: date

    model_config = {"from_attributes": True}


class ReqAccepted(UserBase):
    user_id: str
    task: str
    status: str

    model_config = {"from_attributes": True}


class UserLogCreate(BaseModel):
    req_id: str
    user_id: str
    task: str
    req_received: bool
    req_processed: bool
    error_log: str | None = None


class UserLogResponse(BaseModel):
    model_config = {"from_attributes": True}
    req_id: str
    task: str
    req_received: bool
    req_processed: bool
    error_log: str | None = None


class CheckoutSessionRequest(BaseModel):
    plan: str


class CheckoutSessionResponse(BaseModel):
    checkout_url: str


class UserProfileResponse(BaseModel):
    model_config = {"from_attributes": True}
    user_id: str
    email: EmailStr
    organization_name: Optional[str]
    is_organization: Optional[bool]
    is_active: bool
    subscription_plan: str
    subscription_start: Optional[date]
    subscription_end: Optional[date]
    max_requests: int