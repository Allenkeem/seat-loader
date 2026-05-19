from fastapi import FastAPI, Depends, Request, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session
import database, models, schemas
import secrets
import hashlib
import os

def hash_password(raw: str) -> str:
    salt = os.environ.get('PASSWORD_SALT', 'sogang-drama-club')
    return hashlib.sha256(f"{salt}:{raw}".encode()).hexdigest()

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

SESSIONS = [
    {"id": 1, "name": "5월 29일 (금) 16:30 공연", "subtitle": "종료 약 18:00"},
    {"id": 2, "name": "5월 29일 (금) 20:00 공연", "subtitle": "종료 약 21:30"},
    {"id": 3, "name": "5월 30일 (토) 15:00 공연", "subtitle": "종료 약 16:30"},
    {"id": 4, "name": "5월 30일 (토) 19:00 공연", "subtitle": "종료 약 20:30"}
]

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
def startup_event():
    # Initialize seats if empty
    db = database.SessionLocal()
    existing_seats = db.query(models.Seat).count()
    if existing_seats == 0:
        rows = ["A", "B", "C", "D", "E", "F", "G"]
        for s in SESSIONS:
            for row in rows:
                for num in range(1, 13):
                    if row == "A" and num in [1, 2, 3]:
                        continue
                    seat_id = f"{s['id']}_{row}-{num}"
                    seat = models.Seat(id=seat_id, session_id=s['id'], row=row, number=num)
                    db.add(seat)
        db.commit()
    db.close()

security = HTTPBasic()

def authenticate_admin(credentials: HTTPBasicCredentials = Depends(security)):
    admin_pw = os.environ.get('ADMIN_PASSWORD', 'sogang1234')
    correct_username = secrets.compare_digest(credentials.username, "admin")
    correct_password = secrets.compare_digest(credentials.password, admin_pw)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request, username: str = Depends(authenticate_admin)):
    return templates.TemplateResponse("admin.html", {"request": request})

@app.get("/api/sessions")
def get_sessions():
    return SESSIONS

@app.get("/api/seats", response_model=list[schemas.SeatResponse])
def get_seats(session_id: int, db: Session = Depends(get_db)):
    return db.query(models.Seat).filter(models.Seat.session_id == session_id).all()

@app.post("/api/reserve")
def reserve_seat(res: schemas.ReservationCreate, db: Session = Depends(get_db)):
    if not res.seat_ids:
        raise HTTPException(status_code=400, detail="선택된 좌석이 없습니다.")
    if len(res.seat_ids) > 4:
        raise HTTPException(status_code=400, detail="한 번에 최대 4석까지만 예매 가능합니다.")
        
    # Transaction lock for concurrency
    seats = db.query(models.Seat).filter(models.Seat.id.in_(res.seat_ids)).with_for_update().all()
    
    if len(seats) != len(res.seat_ids):
        raise HTTPException(status_code=404, detail="일부 좌석을 찾을 수 없습니다.")
        
    for seat in seats:
        if seat.status != "available":
            raise HTTPException(status_code=400, detail=f"{seat.id} 좌석은 이미 예매되었습니다.")
            
    # Create reservations and update seats
    for seat in seats:
        reservation = models.Reservation(
            session_id=res.session_id,
            seat_id=seat.id,
            user_name=res.user_name,
            phone=res.phone,
            password=hash_password(res.password)
        )
        seat.status = "reserved"
        db.add(reservation)
        
    db.commit()
    return {"status": "success"}

@app.get("/api/admin/reservations", response_model=list[schemas.ReservationResponse])
def get_reservations(db: Session = Depends(get_db), username: str = Depends(authenticate_admin)):
    return db.query(models.Reservation).all()

@app.post("/api/my_reservations", response_model=list[schemas.ReservationResponse])
def get_my_reservations(req: schemas.ReservationLookup, db: Session = Depends(get_db)):
    reservations = db.query(models.Reservation).filter(
        models.Reservation.user_name == req.user_name,
        models.Reservation.phone == req.phone,
        models.Reservation.password == hash_password(req.password)
    ).all()
    return reservations

@app.post("/api/cancel/{seat_id}")
def cancel_reservation(seat_id: str, req: schemas.ReservationLookup, db: Session = Depends(get_db)):
    reservation = db.query(models.Reservation).filter(
        models.Reservation.seat_id == seat_id,
        models.Reservation.user_name == req.user_name,
        models.Reservation.phone == req.phone,
        models.Reservation.password == hash_password(req.password)
    ).first()
    
    if not reservation:
        raise HTTPException(status_code=404, detail="권한이 없거나 예매 내역을 찾을 수 없습니다.")
        
    seat = db.query(models.Seat).filter(models.Seat.id == seat_id).with_for_update().first()
    if seat:
        seat.status = "available"
        
    db.delete(reservation)
    db.commit()
    return {"status": "success"}

@app.post("/api/admin/claim/bulk")
def bulk_claim_tickets(req: schemas.BulkClaimRequest, db: Session = Depends(get_db), username: str = Depends(authenticate_admin)):
    reservations = db.query(models.Reservation).filter(models.Reservation.id.in_(req.reservation_ids)).all()
    for r in reservations:
        r.claimed = True
    db.commit()
    return {"status": "success"}

@app.post("/api/admin/claim/{reservation_id}")
def claim_ticket(reservation_id: int, db: Session = Depends(get_db), username: str = Depends(authenticate_admin)):
    reservation = db.query(models.Reservation).filter(models.Reservation.id == reservation_id).first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    reservation.claimed = True
    db.commit()
    return {"status": "success"}

@app.post("/api/admin/edit")
def edit_reservation(req: schemas.AdminEditRequest, db: Session = Depends(get_db), username: str = Depends(authenticate_admin)):
    if len(req.reservation_ids) != len(req.new_seat_ids):
        raise HTTPException(status_code=400, detail="요청한 예매 수와 새 좌석 수가 일치하지 않습니다.")
    
    reservations = db.query(models.Reservation).filter(models.Reservation.id.in_(req.reservation_ids)).all()
    if len(reservations) != len(req.reservation_ids):
        raise HTTPException(status_code=404, detail="일부 예매 내역을 찾을 수 없습니다.")

    full_new_seat_ids = [f"{req.new_session_id}_{s.strip()}" for s in req.new_seat_ids]

    new_seats = db.query(models.Seat).filter(models.Seat.id.in_(full_new_seat_ids)).with_for_update().all()
    if len(new_seats) != len(full_new_seat_ids):
        raise HTTPException(status_code=404, detail="지정된 새 좌석 중 유효하지 않은 좌석이 있습니다. (예: H-6)")
        
    for seat in new_seats:
        is_my_own_seat = any(r.seat_id == seat.id for r in reservations)
        if seat.status != "available" and not is_my_own_seat:
            raise HTTPException(status_code=400, detail=f"{seat.id} 좌석은 이미 예매되어 있습니다.")
            
    old_seat_ids = [r.seat_id for r in reservations]
    old_seats = db.query(models.Seat).filter(models.Seat.id.in_(old_seat_ids)).with_for_update().all()
    for os in old_seats:
        os.status = "available"

    for seat in new_seats:
        seat.status = "reserved"

    for i, res in enumerate(reservations):
        res.session_id = req.new_session_id
        res.seat_id = full_new_seat_ids[i]
        
    db.commit()
    return {"status": "success"}
