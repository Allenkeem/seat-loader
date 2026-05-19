from pydantic import BaseModel
from typing import List, Optional

class ReservationCreate(BaseModel):
    session_id: int
    seat_ids: List[str]
    user_name: str
    phone: str
    password: str

class ReservationLookup(BaseModel):
    user_name: str
    phone: str
    password: str

class BulkClaimRequest(BaseModel):
    reservation_ids: List[int]

class AdminEditRequest(BaseModel):
    reservation_ids: List[int]
    new_session_id: int
    new_seat_ids: List[str]

class SeatResponse(BaseModel):
    id: str
    session_id: int
    row: str
    number: int
    status: str
    
    class Config:
        from_attributes = True

class ReservationResponse(BaseModel):
    id: int
    session_id: int
    seat_id: str
    user_name: str
    phone: str
    claimed: bool

    class Config:
        from_attributes = True
