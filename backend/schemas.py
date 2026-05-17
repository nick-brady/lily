from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ContractionCreate(BaseModel):
    start_time: datetime
    end_time: Optional[datetime] = None


class ContractionUpdate(BaseModel):
    end_time: datetime


class Contraction(BaseModel):
    id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[int] = None

    class Config:
        from_attributes = True


class ContractionResponse(BaseModel):
    id: int
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: Optional[int] = None
    ignore_interval_before: bool = False


class UpdateResponse(BaseModel):
    id: int
    timestamp: str
    type: str
    content: Optional[str] = None
    photo_filename: Optional[str] = None
    audio_filename: Optional[str] = None
    milestone: Optional[str] = None
