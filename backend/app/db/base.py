from sqlalchemy.orm import DeclarativeBase


class UserBase(DeclarativeBase):  # All the classes in user_models inherits this as it creates a registry which stores the details about all the attributes and help sqlalchemy
    pass                 # The below classes don't inherit DeclarativeBase directly as that would create different registries and won't be known by their metadata pool.

class AnalysisBase(DeclarativeBase):
    pass