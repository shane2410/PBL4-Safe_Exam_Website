from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

# --- Option Schemas ---
class QuestionOptionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str

class QuestionOptionAdmin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    is_correct: bool
    order_index: int

class QuestionOptionCreate(BaseModel):
    content: str = Field(..., min_length=1)
    is_correct: bool = False
    order_index: int = 0

# --- Question Schemas ---
class QuestionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    type: str  # SINGLE_CHOICE | MULTI_CHOICE | FILL_BLANK
    difficulty: str  # EASY | MEDIUM | HARD
    subject_id: int
    image_url: Optional[str] = None
    score: Optional[float] = 1.0
    options: List[QuestionOptionPublic] = []

class QuestionAdmin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    type: str
    difficulty: str
    subject_id: int
    created_by: Optional[int] = None
    image_url: Optional[str] = None
    created_at: datetime
    options: List[QuestionOptionAdmin] = []

class QuestionCreate(BaseModel):
    subject_id: int
    content: str = Field(..., min_length=3)
    type: str = Field(default="SINGLE_CHOICE")  # SINGLE_CHOICE | MULTI_CHOICE | FILL_BLANK
    difficulty: str = Field(default="MEDIUM")  # EASY | MEDIUM | HARD
    image_url: Optional[str] = None
    options: List[QuestionOptionCreate] = []

class QuestionUpdate(BaseModel):
    content: Optional[str] = None
    type: Optional[str] = None
    difficulty: Optional[str] = None
    image_url: Optional[str] = None
    options: Optional[List[QuestionOptionCreate]] = None

class SubjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str

class SubjectCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=20)
    name: str = Field(..., min_length=2, max_length=100)
