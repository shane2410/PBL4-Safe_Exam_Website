from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.core.database import Base

class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)  # ADMIN | TEACHER | STUDENT
    name = Column(String(50), nullable=False)

    users = relationship("User", back_populates="role")
