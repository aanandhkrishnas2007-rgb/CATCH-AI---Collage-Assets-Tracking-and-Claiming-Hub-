from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    student_id = db.Column(db.String(50), unique=True, nullable=False)
    department = db.Column(db.String(100))
    year = db.Column(db.String(20))
    email = db.Column(db.String(150), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    password_hash = db.Column(db.String(255), nullable=False)
    profile_picture = db.Column(db.String(255), default="default.png")
    catch_points = db.Column(db.Integer, default=0)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    lost_items = db.relationship("LostItem", backref="owner", lazy=True, cascade="all, delete-orphan")
    found_items = db.relationship("FoundItem", backref="finder", lazy=True, cascade="all, delete-orphan")
    notifications = db.relationship("Notification", backref="user", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def items_returned_count(self):
        return LostItem.query.filter_by(user_id=self.id, status="returned").count()


class LostItem(db.Model):
    __tablename__ = "lost_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    item_name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    brand = db.Column(db.String(100))
    color = db.Column(db.String(50))
    description = db.Column(db.Text)
    unique_marks = db.Column(db.String(255))
    date_lost = db.Column(db.Date)
    time_lost = db.Column(db.Time)
    location = db.Column(db.String(150))
    image_path = db.Column(db.String(255))
    reward = db.Column(db.String(100))
    status = db.Column(db.Enum("open", "matched", "returned", "closed", name="lost_status"), default="open")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class FoundItem(db.Model):
    __tablename__ = "found_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    item_name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    brand = db.Column(db.String(100))
    color = db.Column(db.String(50))
    description = db.Column(db.Text)
    unique_marks = db.Column(db.String(255))
    date_found = db.Column(db.Date)
    time_found = db.Column(db.Time)
    location = db.Column(db.String(150))
    image_path = db.Column(db.String(255))
    status = db.Column(db.Enum("open", "matched", "returned", "closed", name="found_status"), default="open")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Match(db.Model):
    __tablename__ = "matches"

    id = db.Column(db.Integer, primary_key=True)
    lost_item_id = db.Column(db.Integer, db.ForeignKey("lost_items.id"), nullable=False)
    found_item_id = db.Column(db.Integer, db.ForeignKey("found_items.id"), nullable=False)
    match_score = db.Column(db.Float, nullable=False)
    image_score = db.Column(db.Float, default=0)
    text_score = db.Column(db.Float, default=0)
    status = db.Column(db.Enum("pending", "verified", "rejected", name="match_status"), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    lost_item = db.relationship("LostItem", backref="matches")
    found_item = db.relationship("FoundItem", backref="matches")


class Verification(db.Model):
    __tablename__ = "verification"

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("matches.id"), nullable=False)
    question = db.Column(db.String(255), nullable=False)
    answer_given = db.Column(db.String(255))
    is_correct = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    match = db.relationship("Match", backref="verifications")


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50), default="general")
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ActivityLog(db.Model):
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
