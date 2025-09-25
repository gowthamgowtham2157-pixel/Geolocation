from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from geopy.distance import geodesic

app = Flask(_name_)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///attendance.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Configuration for Attendance Zone ---
OFFICE_LATITUDE = 34.052235
OFFICE_LONGITUDE = -118.243683
RADIUS_THRESHOLD_METERS = 100

# --- Database Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)

    def _repr_(self):
        return f'<User {self.username}>'

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    is_within_zone = db.Column(db.Boolean, nullable=False)

    user = db.relationship('User', backref=db.backref('attendances', lazy=True))

    def _repr_(self):
        return f'<Attendance {self.user.username} - {self.timestamp}>'

# --- Helper Function for Distance Calculation ---
def calculate_distance(lat1, lon1, lat2, lon2):
    coords1 = (lat1, lon1)
    coords2 = (lat2, lon2)
    return geodesic(coords1, coords2).meters

# --- Routes ---
@app.before_first_request
def create_tables():
    db.create_all()
    if not User.query.first():
        admin_user = User(username='admin')
        john_doe = User(username='john.doe')
        db.session.add_all([admin_user, john_doe])
        db.session.commit()
        print("Dummy users created.")

@app.route('/')
def index():
    return "Geolocation Attendance Backend is running!"

@app.route('/api/mark_attendance', methods=['POST'])
def mark_attendance():
    data = request.get_json()
    user_id = data.get('user_id')
    user_latitude = data.get('latitude')
    user_longitude = data.get('longitude')

    if not all([user_id, user_latitude, user_longitude]):
        return jsonify({"message": "Missing user_id, latitude, or longitude"}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": f"User with ID {user_id} not found"}), 404

    distance = calculate_distance(
        OFFICE_LATITUDE, OFFICE_LONGITUDE,
        user_latitude, user_longitude
    )
    is_within_zone = distance <= RADIUS_THRESHOLD_METERS

    new_attendance = Attendance(
        user_id=user_id,
        latitude=user_latitude,
        longitude=user_longitude,
        is_within_zone=is_within_zone
    )
    db.session.add(new_attendance)
    db.session.commit()

    status_message = "Attendance marked successfully."
    if not is_within_zone:
        status_message += f" You are outside the designated attendance zone. Distance: {distance:.2f} meters."
        return jsonify({
            "message": status_message,
            "status": "out_of_zone",
            "distance_from_office_meters": round(distance, 2)
        }), 200
    else:
        status_message += f" You are within the designated attendance zone. Distance: {distance:.2f} meters."
        return jsonify({
            "message": status_message,
            "status": "in_zone",
            "distance_from_office_meters": round(distance, 2)
        }), 201

@app.route('/api/user_attendance/<int:user_id>', methods=['GET'])
def get_user_attendance(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": f"User with ID {user_id} not found"}), 404

    attendances = Attendance.query.filter_by(user_id=user_id).order_by(Attendance.timestamp.desc()).all()
    results = [{
        "id": att.id,
        "timestamp": att.timestamp.isoformat(),
        "latitude": att.latitude,
        "longitude": att.longitude,
        "is_within_zone": att.is_within_zone
    } for att in attendances]

    return jsonify({"user": user.username, "attendance_records": results})

@app.route('/api/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify([{"id": user.id, "username": user.username} for user in users])

if _name_ == '_main_':
    app.run(debug=True, port=5000)
    