import os
import uuid
from datetime import datetime, date, time

from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, abort, send_from_directory
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)
from werkzeug.utils import secure_filename

from config import Config
from models import db, User, LostItem, FoundItem, Match, Verification, Notification, ActivityLog
from ai_matching import find_best_matches, compute_match_score

# ------------------------------------------------------------------
# APP SETUP
# ------------------------------------------------------------------
app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# SQLite: create the database file and all tables automatically on first run
with app.app_context():
    db.create_all()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]
    )


def save_upload(file_storage):
    """Saves an uploaded image with a unique filename. Returns the stored filename or None."""
    if not file_storage or file_storage.filename == "":
        return None
    if not allowed_file(file_storage.filename):
        flash("Invalid image file type. Allowed: png, jpg, jpeg, gif, webp.", "danger")
        return None
    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(app.config["UPLOAD_FOLDER"], unique_name))
    return unique_name


def log_activity(user_id, action):
    db.session.add(ActivityLog(user_id=user_id, action=action))


def notify(user_id, message, ntype="general"):
    db.session.add(Notification(user_id=user_id, message=message, type=ntype))


def award_points(user, points, reason=""):
    user.catch_points = (user.catch_points or 0) + points
    notify(user.id, f"You earned {points} Catch Points! {reason}", ntype="points")


def parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date() if value else None
    except ValueError:
        return None


def parse_time(value):
    try:
        return datetime.strptime(value, "%H:%M").time() if value else None
    except ValueError:
        return None


# ------------------------------------------------------------------
# PUBLIC PAGES
# ------------------------------------------------------------------
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/")
def index():
    stats = {
        "lost_count": LostItem.query.count(),
        "found_count": FoundItem.query.count(),
        "returned_count": LostItem.query.filter_by(status="returned").count(),
        "user_count": User.query.count(),
    }
    return render_template("index.html", stats=stats)


# ------------------------------------------------------------------
# AUTH
# ------------------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        student_id = request.form.get("student_id", "").strip()
        department = request.form.get("department", "").strip()
        year = request.form.get("year", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        errors = []

        if not all([name, student_id, email, password, confirm_password]):
            errors.append("Please fill in all required fields.")

        if password != confirm_password:
            errors.append("Passwords do not match.")

        if len(password) < 6:
            errors.append("Password must be at least 6 characters long.")

        allowed_domain = app.config.get("ALLOWED_EMAIL_DOMAIN")
        if allowed_domain and not email.endswith(f"@{allowed_domain}"):
            errors.append(f"Please register with your college email (@{allowed_domain}).")

        if User.query.filter_by(email=email).first():
            errors.append("An account with this email already exists.")

        if User.query.filter_by(student_id=student_id).first():
            errors.append("An account with this student ID already exists.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("register.html", form=request.form)

        profile_picture = "default.png"
        if "profile_picture" in request.files:
            saved = save_upload(request.files["profile_picture"])
            if saved:
                profile_picture = saved

        user = User(
            name=name,
            student_id=student_id,
            department=department,
            year=year,
            email=email,
            phone=phone,
            profile_picture=profile_picture,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        log_activity(user.id, "Registered a new account")
        db.session.commit()

        flash("Account created successfully! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html", form={})


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            log_activity(user.id, "Logged in")
            db.session.commit()
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    log_activity(current_user.id, "Logged out")
    db.session.commit()
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ------------------------------------------------------------------
# DASHBOARD
# ------------------------------------------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    my_lost = LostItem.query.filter_by(user_id=current_user.id).order_by(LostItem.created_at.desc()).all()
    my_found = FoundItem.query.filter_by(user_id=current_user.id).order_by(FoundItem.created_at.desc()).all()

    my_lost_ids = [item.id for item in my_lost]
    recent_matches = (
        Match.query.filter(Match.lost_item_id.in_(my_lost_ids)).order_by(Match.created_at.desc()).limit(5).all()
        if my_lost_ids else []
    )

    unread_notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()

    top_helpers = User.query.order_by(User.catch_points.desc()).limit(5).all()

    stats = {
        "lost_count": len(my_lost),
        "found_count": len(my_found),
        "returned_count": len([i for i in my_lost if i.status == "returned"]),
        "points": current_user.catch_points,
    }

    return render_template(
        "dashboard.html",
        my_lost=my_lost,
        my_found=my_found,
        recent_matches=recent_matches,
        unread_notifications=unread_notifications,
        top_helpers=top_helpers,
        stats=stats,
    )


# ------------------------------------------------------------------
# REPORT LOST ITEM
# ------------------------------------------------------------------
@app.route("/report-lost", methods=["GET", "POST"])
@login_required
def report_lost():
    if request.method == "POST":
        image_filename = None
        if "image" in request.files:
            image_filename = save_upload(request.files["image"])

        item = LostItem(
            user_id=current_user.id,
            item_name=request.form.get("item_name", "").strip(),
            category=request.form.get("category", "").strip(),
            brand=request.form.get("brand", "").strip(),
            color=request.form.get("color", "").strip(),
            description=request.form.get("description", "").strip(),
            unique_marks=request.form.get("unique_marks", "").strip(),
            date_lost=parse_date(request.form.get("date_lost")),
            time_lost=parse_time(request.form.get("time_lost")),
            location=request.form.get("location", "").strip(),
            image_path=image_filename,
            reward=request.form.get("reward", "").strip(),
        )

        if not item.item_name or not item.category:
            flash("Item name and category are required.", "danger")
            return render_template("report_lost.html", form=request.form)

        db.session.add(item)
        log_activity(current_user.id, f"Reported lost item: {item.item_name}")
        db.session.commit()

        flash("Lost item reported! We're searching for matches now.", "success")
        return redirect(url_for("match_results", item_id=item.id))

    return render_template("report_lost.html", form={})


# ------------------------------------------------------------------
# REPORT FOUND ITEM
# ------------------------------------------------------------------
@app.route("/report-found", methods=["GET", "POST"])
@login_required
def report_found():
    if request.method == "POST":
        image_filename = None
        if "image" in request.files:
            image_filename = save_upload(request.files["image"])

        item = FoundItem(
            user_id=current_user.id,
            item_name=request.form.get("item_name", "").strip(),
            category=request.form.get("category", "").strip(),
            brand=request.form.get("brand", "").strip(),
            color=request.form.get("color", "").strip(),
            description=request.form.get("description", "").strip(),
            unique_marks=request.form.get("unique_marks", "").strip(),
            date_found=parse_date(request.form.get("date_found")),
            time_found=parse_time(request.form.get("time_found")),
            location=request.form.get("location", "").strip(),
            image_path=image_filename,
        )

        if not item.item_name or not item.category:
            flash("Item name and category are required.", "danger")
            return render_template("report_found.html", form=request.form)

        db.session.add(item)
        award_points(current_user, 5, "for reporting a found item.")
        log_activity(current_user.id, f"Reported found item: {item.item_name}")
        db.session.commit()

        flash("Found item reported — thank you for helping! +5 Catch Points", "success")
        return redirect(url_for("dashboard"))

    return render_template("report_found.html", form={})


# ------------------------------------------------------------------
# AI MATCH RESULTS
# ------------------------------------------------------------------
@app.route("/matches/<int:item_id>")
@login_required
def match_results(item_id):
    lost_item = LostItem.query.get_or_404(item_id)

    if lost_item.user_id != current_user.id and not current_user.is_admin:
        abort(403)

    candidate_found_items = FoundItem.query.filter_by(status="open").all()

    ranked = find_best_matches(
        lost_item,
        candidate_found_items,
        app.config["UPLOAD_FOLDER"],
        top_n=app.config["MATCH_TOP_N"],
        min_score=app.config["MIN_MATCH_SCORE"],
    )

    # Persist matches so they can be verified / referenced later
    for r in ranked:
        existing = Match.query.filter_by(
            lost_item_id=lost_item.id, found_item_id=r["found_item"].id
        ).first()
        if not existing:
            match = Match(
                lost_item_id=lost_item.id,
                found_item_id=r["found_item"].id,
                match_score=r["overall"],
                image_score=r["image_score"],
                text_score=r["text_score"],
            )
            db.session.add(match)
    db.session.commit()

    stored_matches = Match.query.filter_by(lost_item_id=lost_item.id).order_by(Match.match_score.desc()).all()

    return render_template("match_results.html", lost_item=lost_item, matches=stored_matches)


# ------------------------------------------------------------------
# VERIFICATION (owner proves ownership before contact info is revealed)
# ------------------------------------------------------------------
@app.route("/verify/<int:match_id>", methods=["GET", "POST"])
@login_required
def verify_match(match_id):
    match = Match.query.get_or_404(match_id)
    lost_item = match.lost_item

    if lost_item.user_id != current_user.id:
        abort(403)

    if request.method == "POST":
        answer = request.form.get("answer", "").strip()
        # The unique mark the lost-item owner originally provided is the "secret"
        expected = (lost_item.unique_marks or "").strip().lower()
        is_correct = bool(expected) and answer.strip().lower() == expected

        verification = Verification(
            match_id=match.id,
            question="Describe a unique mark, sticker, or identifying feature on this item.",
            answer_given=answer,
            is_correct=is_correct,
        )
        db.session.add(verification)

        if is_correct:
            match.status = "verified"
            lost_item.status = "returned"
            match.found_item.status = "returned"
            award_points(current_user, 10, "for a verified item recovery.")
            finder = match.found_item.finder
            award_points(finder, 15, "for helping recover a lost item.")
            notify(finder.id, f"Your found item '{match.found_item.item_name}' was verified and returned to its owner!", "match")
            flash("Ownership verified! Contact details are now unlocked below.", "success")
        else:
            match.status = "rejected"
            flash("That answer doesn't match our records. This match has been rejected.", "danger")

        db.session.commit()
        return redirect(url_for("match_results", item_id=lost_item.id))

    return render_template("verify.html", match=match)


# ------------------------------------------------------------------
# NOTIFICATIONS
# ------------------------------------------------------------------
@app.route("/notifications")
@login_required
def notifications():
    items = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return render_template("notifications.html", notifications=items)


# ------------------------------------------------------------------
# PROFILE
# ------------------------------------------------------------------
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_user.name = request.form.get("name", current_user.name).strip()
        current_user.department = request.form.get("department", current_user.department).strip()
        current_user.year = request.form.get("year", current_user.year).strip()
        current_user.phone = request.form.get("phone", current_user.phone).strip()

        if "profile_picture" in request.files:
            saved = save_upload(request.files["profile_picture"])
            if saved:
                current_user.profile_picture = saved

        new_password = request.form.get("new_password", "").strip()
        if new_password:
            if len(new_password) < 6:
                flash("New password must be at least 6 characters.", "danger")
                return redirect(url_for("profile"))
            current_user.set_password(new_password)
            flash("Password updated.", "success")

        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("profile"))

    my_lost = LostItem.query.filter_by(user_id=current_user.id).all()
    my_found = FoundItem.query.filter_by(user_id=current_user.id).all()
    return render_template("profile.html", my_lost=my_lost, my_found=my_found)


# ------------------------------------------------------------------
# LEADERBOARD
# ------------------------------------------------------------------
@app.route("/leaderboard")
@login_required
def leaderboard():
    top_users = User.query.order_by(User.catch_points.desc()).limit(20).all()

    def badge_for(points):
        if points >= 100:
            return "Campus Guardian"
        elif points >= 50:
            return "Trusted Student"
        elif points >= 10:
            return "Honest Hero"
        return "Newcomer"

    return render_template("leaderboard.html", top_users=top_users, badge_for=badge_for)


# ------------------------------------------------------------------
# ADMIN
# ------------------------------------------------------------------
def admin_required():
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)


@app.route("/admin")
@login_required
def admin_dashboard():
    admin_required()
    stats = {
        "users": User.query.count(),
        "lost_items": LostItem.query.count(),
        "found_items": FoundItem.query.count(),
        "returned": LostItem.query.filter_by(status="returned").count(),
        "pending_matches": Match.query.filter_by(status="pending").count(),
    }
    recent_lost = LostItem.query.order_by(LostItem.created_at.desc()).limit(10).all()
    recent_found = FoundItem.query.order_by(FoundItem.created_at.desc()).limit(10).all()
    return render_template("admin/admin_dashboard.html", stats=stats, recent_lost=recent_lost, recent_found=recent_found)


@app.route("/admin/users")
@login_required
def admin_manage_users():
    admin_required()
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/manage_users.html", users=users)


@app.route("/admin/items")
@login_required
def admin_manage_items():
    admin_required()
    lost_items = LostItem.query.order_by(LostItem.created_at.desc()).all()
    found_items = FoundItem.query.order_by(FoundItem.created_at.desc()).all()
    return render_template("admin/manage_items.html", lost_items=lost_items, found_items=found_items)


@app.route("/admin/items/lost/<int:item_id>/delete", methods=["POST"])
@login_required
def admin_delete_lost(item_id):
    admin_required()
    item = LostItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Lost item report deleted.", "info")
    return redirect(url_for("admin_manage_items"))


@app.route("/admin/items/found/<int:item_id>/delete", methods=["POST"])
@login_required
def admin_delete_found(item_id):
    admin_required()
    item = FoundItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Found item report deleted.", "info")
    return redirect(url_for("admin_manage_items"))


# ------------------------------------------------------------------
# CLI: create an admin user   ->   flask create-admin
# ------------------------------------------------------------------
@app.cli.command("create-admin")
def create_admin():
    """Usage: flask create-admin"""
    import getpass
    print("=== Create CATCH Admin Account ===")
    name = input("Name: ")
    email = input("Email: ").strip().lower()
    student_id = input("Staff/Admin ID: ")
    password = getpass.getpass("Password: ")

    if User.query.filter_by(email=email).first():
        print("A user with that email already exists.")
        return

    admin = User(name=name, email=email, student_id=student_id, is_admin=True)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    print(f"Admin account created for {email}")


# ------------------------------------------------------------------
# ERROR HANDLERS
# ------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    return render_template("errors/404.html"), 404


@app.errorhandler(403)
def forbidden(e):
    return render_template("errors/403.html"), 403


@app.errorhandler(500)
def server_error(e):
    return render_template("errors/500.html"), 500


# ------------------------------------------------------------------
# ENTRY POINT
# ------------------------------------------------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
