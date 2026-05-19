from flask import Flask, render_template, request, jsonify, g, make_response
import secrets
import hashlib
import os
from functools import wraps
from sqlalchemy.orm import Session
import database, models

def hash_password(raw: str) -> str:
    salt = os.environ.get('PASSWORD_SALT')
    if not salt:
        raise RuntimeError("PASSWORD_SALT environment variable is not set")
    return hashlib.sha256(f"{salt}:{raw}".encode()).hexdigest()

# DB Schema init
models.Base.metadata.create_all(bind=database.engine)

SESSIONS = [
    {"id": 1, "name": "5월 29일 (금) 16:30 공연", "subtitle": "종료 약 18:00"},
    {"id": 2, "name": "5월 29일 (금) 20:00 공연", "subtitle": "종료 약 21:30"},
    {"id": 3, "name": "5월 30일 (토) 15:00 공연", "subtitle": "종료 약 16:30"},
    {"id": 4, "name": "5월 30일 (토) 19:00 공연", "subtitle": "종료 약 20:30"}
]

# Seat Generation on Startup (bypasses ASGI/WSGI startup event lifecycle)
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

app = Flask(__name__)

# --- Database Session Management ---
@app.before_request
def before_request():
    g.db = database.SessionLocal()

@app.teardown_request
def teardown_request(exception):
    db = getattr(g, 'db', None)
    if db is not None:
        db.close()

# --- Auth Middleware ---
def authenticate_admin():
    auth = request.authorization
    if not auth or not auth.username or not auth.password:
        return False
    admin_pw = os.environ.get('ADMIN_PASSWORD', '')
    correct_username = secrets.compare_digest(auth.username, "admin")
    correct_password = secrets.compare_digest(auth.password, admin_pw)
    return correct_username and correct_password

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not authenticate_admin():
            return make_response(
                'Could not verify your access level.\nYou have to login with proper credentials', 
                401, 
                {'WWW-Authenticate': 'Basic realm="Admin Required"'}
            )
        return f(*args, **kwargs)
    return decorated

# --- Routes ---
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/admin")
@requires_auth
def admin():
    return render_template("admin.html")

@app.route("/api/sessions", methods=["GET"])
def get_sessions():
    return jsonify(SESSIONS)

@app.route("/api/seats", methods=["GET"])
def get_seats():
    session_id = int(request.args.get('session_id'))
    seats = g.db.query(models.Seat).filter(models.Seat.session_id == session_id).all()
    return jsonify([{"id": s.id, "session_id": s.session_id, "row": s.row, "number": s.number, "status": s.status} for s in seats])

@app.route("/api/reserve", methods=["POST"])
def reserve_seat():
    data = request.json
    seat_ids = data.get("seat_ids", [])
    phone = data.get("phone", "").strip()
    
    if not phone.isdigit() or len(phone) < 10:
        return jsonify({"detail": "연락처는 하이픈(-) 없이 10자리 이상의 숫자만 입력해주세요."}), 400
        
    if not seat_ids:
        return jsonify({"detail": "선택된 좌석이 없습니다."}), 400
    if len(seat_ids) > 4:
        return jsonify({"detail": "한 번에 최대 4석까지만 예매 가능합니다."}), 400
        
    seats = g.db.query(models.Seat).filter(models.Seat.id.in_(seat_ids)).with_for_update().all()
    
    if len(seats) != len(seat_ids):
        return jsonify({"detail": "일부 좌석을 찾을 수 없습니다."}), 404
        
    for seat in seats:
        if seat.status != "available":
            return jsonify({"detail": f"{seat.id} 좌석은 이미 예매되었습니다."}), 400
            
    for seat in seats:
        reservation = models.Reservation(
            session_id=data["session_id"],
            seat_id=seat.id,
            user_name=data["user_name"],
            phone=data["phone"],
            password=hash_password(data["password"])
        )
        seat.status = "reserved"
        g.db.add(reservation)
        
    g.db.commit()
    return jsonify({"status": "success"})

@app.route("/api/my_reservations", methods=["POST"])
def get_my_reservations():
    data = request.json
    reservations = g.db.query(models.Reservation).filter(
        models.Reservation.user_name == data["user_name"],
        models.Reservation.phone == data["phone"],
        models.Reservation.password == hash_password(data["password"])
    ).all()
    return jsonify([{
        "id": r.id, "session_id": r.session_id, "seat_id": r.seat_id,
        "user_name": r.user_name, "phone": r.phone, "claimed": r.claimed
    } for r in reservations])

@app.route("/api/cancel/<seat_id>", methods=["POST"])
def cancel_reservation(seat_id):
    data = request.json
    reservation = g.db.query(models.Reservation).filter(
        models.Reservation.seat_id == seat_id,
        models.Reservation.user_name == data["user_name"],
        models.Reservation.phone == data["phone"],
        models.Reservation.password == hash_password(data["password"])
    ).first()
    
    if not reservation:
        return jsonify({"detail": "권한이 없거나 예매 내역을 찾을 수 없습니다."}), 404
        
    seat = g.db.query(models.Seat).filter(models.Seat.id == seat_id).with_for_update().first()
    if seat:
        seat.status = "available"
        
    g.db.delete(reservation)
    g.db.commit()
    return jsonify({"status": "success"})

@app.route("/api/admin/reservations", methods=["GET"])
@requires_auth
def get_admin_reservations():
    reservations = g.db.query(models.Reservation).all()
    return jsonify([{
        "id": r.id, "session_id": r.session_id, "seat_id": r.seat_id,
        "user_name": r.user_name, "phone": r.phone, "claimed": r.claimed
    } for r in reservations])

@app.route("/api/admin/claim/bulk", methods=["POST"])
@requires_auth
def bulk_claim_tickets():
    data = request.json
    reservations = g.db.query(models.Reservation).filter(models.Reservation.id.in_(data["reservation_ids"])).all()
    for r in reservations:
        r.claimed = True
    g.db.commit()
    return jsonify({"status": "success"})

@app.route("/api/admin/claim/<int:reservation_id>", methods=["POST"])
@requires_auth
def claim_ticket(reservation_id):
    reservation = g.db.query(models.Reservation).filter(models.Reservation.id == reservation_id).first()
    if not reservation:
        return jsonify({"detail": "Reservation not found"}), 404
    reservation.claimed = True
    g.db.commit()
    return jsonify({"status": "success"})

@app.route("/api/admin/edit", methods=["POST"])
@requires_auth
def edit_reservation():
    data = request.json
    if len(data["reservation_ids"]) != len(data["new_seat_ids"]):
        return jsonify({"detail": "요청한 예매 수와 새 좌석 수가 일치하지 않습니다."}), 400
    
    reservations = g.db.query(models.Reservation).filter(models.Reservation.id.in_(data["reservation_ids"])).all()
    if len(reservations) != len(data["reservation_ids"]):
        return jsonify({"detail": "일부 예매 내역을 찾을 수 없습니다."}), 404

    full_new_seat_ids = [f"{data['new_session_id']}_{s.strip()}" for s in data["new_seat_ids"]]

    new_seats = g.db.query(models.Seat).filter(models.Seat.id.in_(full_new_seat_ids)).with_for_update().all()
    if len(new_seats) != len(full_new_seat_ids):
        return jsonify({"detail": "지정된 새 좌석 중 유효하지 않은 좌석이 있습니다. (예: H-6)"}), 404
        
    for seat in new_seats:
        is_my_own_seat = any(r.seat_id == seat.id for r in reservations)
        if seat.status != "available" and not is_my_own_seat:
            return jsonify({"detail": f"{seat.id} 좌석은 이미 예매되어 있습니다."}), 400
            
    old_seat_ids = [r.seat_id for r in reservations]
    old_seats = g.db.query(models.Seat).filter(models.Seat.id.in_(old_seat_ids)).with_for_update().all()
    for os in old_seats:
        os.status = "available"

    for seat in new_seats:
        seat.status = "reserved"

    for i, res in enumerate(reservations):
        res.session_id = data["new_session_id"]
        res.seat_id = full_new_seat_ids[i]
        
    g.db.commit()
    return jsonify({"status": "success"})

@app.route("/api/admin/cancel/bulk", methods=["POST"])
@requires_auth
def admin_bulk_cancel():
    data = request.json
    reservation_ids = data.get("reservation_ids", [])
    if not reservation_ids:
        return jsonify({"detail": "선택된 예매 내역이 없습니다."}), 400
        
    reservations = g.db.query(models.Reservation).filter(models.Reservation.id.in_(reservation_ids)).all()
    if not reservations:
        return jsonify({"detail": "예매 내역을 찾을 수 없습니다."}), 404
        
    seat_ids = [r.seat_id for r in reservations]
    seats = g.db.query(models.Seat).filter(models.Seat.id.in_(seat_ids)).with_for_update().all()
    
    for seat in seats:
        seat.status = "available"
        
    for r in reservations:
        g.db.delete(r)
        
    g.db.commit()
    return jsonify({"status": "success"})

if __name__ == "__main__":
    app.run(debug=True, port=8001)
