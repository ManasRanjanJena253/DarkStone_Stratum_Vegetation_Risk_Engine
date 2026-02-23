from sqlalchemy import Column, Integer, String, Boolean, Date
from sqlalchemy import ForeignKey
from ..db.base import UserBase

class User(UserBase):
    __tablename__ = "users"

    user_id = Column(String, primary_key = True, index = True)
    email = Column(String, unique = True, index = True)
    hashed_pwd = Column(String)
    organization_name = Column(String, index = True)
    is_organization = Column(Boolean, index = True)
    is_active = Column(Boolean, default = True)
    subscription_plan = Column(String, default = "Free")  # This can either be Free, Individual, Entrepreneurial, Government
    subscription_start = Column(Date, default = None)  # Stores the starting date of subscription
    subscription_end = Column(Date, default = None)   # Stores the subscription end date.
    max_requests = Column(Integer, default = 5)   # The maximum no. of requests the user can send for analysis. For 'Free' subscription, the limit is 5.

class User_Logs(UserBase):
    __tablename__ = "user_req_logs"

    req_id = Column(String, primary_key = True, index = True)
    user_id = Column(String, ForeignKey("users.user_id"))
    req_received = Column(Boolean)   # Separating the received_req and processed_req separately as it will help us know if the received req was processed and the user
                                     # received the output, if not the user won't be charged from any of his max_req_limit
    req_processed = Column(Boolean)
    error_log = Column(String, default = None)
    task = Column(String)   # What task req has the user send.