from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class Seat(Base):
    __tablename__ = "seats"

    id = Column(String, primary_key=True, index=True) # e.g. "1_A-1"
    session_id = Column(Integer, index=True)
    row = Column(String, index=True) # "A"
    number = Column(Integer) # 1
    # Status can be: 'available', 'reserved'
    status = Column(String, default="available") 

    reservation = relationship("Reservation", back_populates="seat", uselist=False)

class Reservation(Base):
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, index=True)
    seat_id = Column(String, ForeignKey("seats.id"), unique=True)
    user_name = Column(String, index=True)
    phone = Column(String)
    password = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    claimed = Column(Boolean, default=False)

    seat = relationship("Seat", back_populates="reservation")
