
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, jsonify, send_from_directory
)
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
import cv2
import time
import random
import os
import hashlib
import json
import uuid

app = Flask(__name__)

# Configuration
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY", "change-this-secret-key"
)

ADMIN_ID = "admin@123"
ADMIN_PASSWORD = "admin@123"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///evoting.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Email configuration
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = "your-email@gmail.com"
app.config["MAIL_PASSWORD"] = "your-email-password"

db = SQLAlchemy(app)
mail = Mail(app)

# Upload folders
UPLOAD_FOLDER = "adhaarcardphoto"
VIDEO_UPLOAD_FOLDER = "video_records"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(VIDEO_UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["VIDEO_UPLOAD_FOLDER"] = VIDEO_UPLOAD_FOLDER

# Blockchain storage
BLOCKCHAIN_FILE = "blockchain.json"

if not os.path.exists(BLOCKCHAIN_FILE):
    with open(BLOCKCHAIN_FILE, "w") as f:
        json.dump([], f)


# --------------------------------------------------
# BLOCKCHAIN
# --------------------------------------------------

class Blockchain:
    def __init__(self):
        self.chain = self.load_blockchain()

    def load_blockchain(self):
        try:
            with open(BLOCKCHAIN_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def save_blockchain(self):
        with open(BLOCKCHAIN_FILE, "w") as f:
            json.dump(self.chain, f, indent=4)

    def create_block(self, voter_id, candidate):
        previous_hash = (
            self.chain[-1]["hash"] if self.chain else "0"
        )

        vote_data = f"{voter_id}-{candidate}-{time.time()}"
        block_hash = hashlib.sha256(
            vote_data.encode()
        ).hexdigest()

        block = {
            "index": len(self.chain) + 1,
            "voter_id": voter_id,
            "candidate": candidate,
            "timestamp": time.time(),
            "previous_hash": previous_hash,
            "hash": block_hash,
        }

        self.chain.append(block)
        self.save_blockchain()

        return block

    def verify_integrity(self):
        for i in range(1, len(self.chain)):
            if (
                self.chain[i]["previous_hash"]
                != self.chain[i - 1]["hash"]
            ):
                return False
        return True


blockchain = Blockchain()


# --------------------------------------------------
# DATABASE MODELS
# --------------------------------------------------

class User(db.Model):
    id = db.Column(
        db.Integer, primary_key=True, autoincrement=True
    )
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    voter_id = db.Column(
        db.String(10), unique=True, nullable=False
    )
    aadhaar_id = db.Column(
        db.String(12), unique=True, nullable=False
    )
    phone_number = db.Column(
        db.String(15), unique=True, nullable=False
    )
    otp = db.Column(db.String(6), nullable=True)
    aadhaar_card_path = db.Column(
        db.String(255), nullable=True
    )
    voted = db.Column(db.Boolean, default=False)
    video_path = db.Column(db.String(255), nullable=True)


class VotingRecord(db.Model):
    id = db.Column(
        db.Integer, primary_key=True, autoincrement=True
    )
    voter_id = db.Column(
        db.String(10),
        db.ForeignKey("user.voter_id"),
        nullable=False
    )
    candidate = db.Column(db.String(100), nullable=False)
    video_path = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(
        db.DateTime, default=db.func.current_timestamp()
    )

    user = db.relationship(
        "User",
        backref=db.backref("voting_records", lazy=True)
    )


# --------------------------------------------------
# VOTING PAGE
# --------------------------------------------------

@app.route("/vote", methods=["GET"])
def vote():
    if "voter_id" not in session:
        flash("Please log in first.", "danger")
        return redirect(url_for("login"))

    user = User.query.filter_by(
        voter_id=session["voter_id"]
    ).first()

    if not user:
        session.pop("voter_id", None)
        flash("User not found.", "danger")
        return redirect(url_for("login"))

    if user.voted:
        return redirect(url_for("dashboard"))

    # One-minute voting window
    session["expiry_time"] = time.time() + 60

    return render_template(
        "voting_page.html",
        voter_id=session["voter_id"]
    )


# --------------------------------------------------
# SUBMIT VOTE OR SAVE EXPIRED RECORDING
# --------------------------------------------------

@app.route("/submit_vote", methods=["POST"])
def submit_vote():
    if "voter_id" not in session:
        return jsonify({
            "error": "User not logged in."
        }), 401

    voter_id = session["voter_id"]

    user = User.query.filter_by(
        voter_id=voter_id
    ).first()

    if not user:
        return jsonify({
            "error": "User not found."
        }), 404

    if user.voted:
        return jsonify({
            "error": "You have already voted."
        }), 400

    video_file = request.files.get("video")

    if not video_file or not video_file.filename:
        return jsonify({
            "error": "No video recording received."
        }), 400

    expired = request.form.get("expired") == "true"
    candidate = request.form.get("candidate", "").strip()

    # Candidate is required only when submitting an actual vote.
    if not expired and not candidate:
        return jsonify({
            "error": "Please select a candidate."
        }), 400

    # Generate a unique filename to prevent overwriting videos.
    safe_voter_id = secure_filename(voter_id)
    video_filename = (
        f"{safe_voter_id}_{uuid.uuid4().hex}.webm"
    )

    video_folder = os.path.abspath(
        app.config["VIDEO_UPLOAD_FOLDER"]
    )
    os.makedirs(video_folder, exist_ok=True)

    video_full_path = os.path.join(
        video_folder, video_filename
    )

    try:
        # Save the recording first.
        video_file.save(video_full_path)

        if not os.path.isfile(video_full_path):
            return jsonify({
                "error": "The video file could not be saved."
            }), 500

        # Save a relative path in the database.
        saved_video_path = os.path.join(
            app.config["VIDEO_UPLOAD_FOLDER"],
            video_filename
        )

        user.video_path = saved_video_path

        print("Recording saved:", video_full_path)
        print(
            "Recording exists:",
            os.path.isfile(video_full_path)
        )

        # Timer expired: save recording but do not count a vote.
        if expired:
            db.session.commit()

            return jsonify({
                "message": (
                    "Time expired. Recording saved for admin "
                    "review. No vote was cast."
                ),
                "video_saved": True,
                "voted": False
            }), 200

        # Normal vote: create the voting record and blockchain block.
        new_vote = VotingRecord(
            voter_id=voter_id,
            candidate=candidate,
            video_path=saved_video_path
        )

        user.voted = True
        db.session.add(new_vote)
        db.session.commit()

        blockchain.create_block(voter_id, candidate)

        return jsonify({
            "message": "Vote submitted successfully!",
            "video_saved": True,
            "voted": True
        }), 200

    except Exception as error:
        db.session.rollback()

        print("Error saving recording/vote:", str(error))

        return jsonify({
            "error": "Could not save the recording or vote."
        }), 500


# --------------------------------------------------
# VERIFY BLOCKCHAIN
# --------------------------------------------------

@app.route("/verify_blockchain", methods=["GET"])
def verify_blockchain():
    if blockchain.verify_integrity():
        return jsonify({
            "message": (
                "Blockchain integrity verified. "
                "No tampering detected!"
            )
        })

    return jsonify({
        "error": "Blockchain has been tampered with!"
    }), 400


# --------------------------------------------------
# LOGIN
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        voter_id = request.form.get(
            "voterId", ""
        ).strip()

        phone_number = request.form.get(
            "phoneNumber", ""
        ).strip()

        entered_otp = request.form.get(
            "otp", ""
        ).strip()

        user = User.query.filter_by(
            voter_id=voter_id,
            phone_number=phone_number
        ).first()

        if not user:
            flash(
                "User not found. Please register first.",
                "danger"
            )
            return redirect(url_for("register"))

        if user.voted:
            session.pop("voter_id", None)

            return render_template(
                "login.html",
                already_voted=True
            )

        correct_otp = session.get(phone_number)

        if not correct_otp or entered_otp != correct_otp:
            return """
                <script>
                    alert("Invalid OTP. Please verify your OTP again.");
                    window.location.href = "/login";
                </script>
            """

        session["voter_id"] = voter_id
        session.pop(phone_number, None)

        return redirect(url_for("vote"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("voter_id", None)
    session.pop("expiry_time", None)

    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))


# --------------------------------------------------
# REGISTRATION
# --------------------------------------------------

@app.route("/", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        voter_id = request.form.get(
            "voterId", ""
        ).strip()

        phone_number = request.form.get(
            "phoneNumber", ""
        ).strip()

        first_name = request.form.get(
            "first_name", ""
        ).strip()

        last_name = request.form.get(
            "last_name", ""
        ).strip()

        aadhaar_id = request.form.get(
            "aadhaar_id", ""
        ).strip()

        if not first_name or not last_name:
            flash(
                "First name and last name are required.",
                "danger"
            )
            return redirect(url_for("register"))

        if not voter_id or not phone_number or not aadhaar_id:
            flash(
                "Please fill in all required details.",
                "danger"
            )
            return redirect(url_for("register"))

        if "aadhaarCard" not in request.files:
            flash(
                "Please upload your Aadhaar card.",
                "danger"
            )
            return redirect(url_for("register"))

        aadhaar_card = request.files["aadhaarCard"]

        if not aadhaar_card.filename:
            flash(
                "No Aadhaar card selected.",
                "danger"
            )
            return redirect(url_for("register"))

        if User.query.filter_by(
            voter_id=voter_id
        ).first():
            flash(
                "Voter ID already registered. Try logging in.",
                "danger"
            )
            return redirect(url_for("login"))

        if User.query.filter_by(
            phone_number=phone_number
        ).first():
            flash(
                "Phone number already registered. Try logging in.",
                "danger"
            )
            return redirect(url_for("login"))

        if User.query.filter_by(
            aadhaar_id=aadhaar_id
        ).first():
            flash(
                "Aadhaar ID already registered.",
                "danger"
            )
            return redirect(url_for("register"))

        aadhaar_filename = (
            f"{uuid.uuid4().hex}_"
            f"{secure_filename(aadhaar_card.filename)}"
        )

        aadhaar_path = os.path.join(
            UPLOAD_FOLDER, aadhaar_filename
        )

        aadhaar_card.save(aadhaar_path)

        otp = str(random.randint(100000, 999999))
        session[phone_number] = otp

        new_user = User(
            voter_id=voter_id,
            phone_number=phone_number,
            first_name=first_name,
            last_name=last_name,
            aadhaar_id=aadhaar_id,
            aadhaar_card_path=aadhaar_path,
            otp=otp
        )

        db.session.add(new_user)
        db.session.commit()

        print(f"Registration OTP for {phone_number}: {otp}")

        flash(
            "Registration successful! Please log in.",
            "success"
        )
        return redirect(url_for("login"))

    return render_template("register.html")


# --------------------------------------------------
# REGISTRATION OTP
# --------------------------------------------------

@app.route("/send_otp", methods=["POST"])
def send_otp():
    phone_number = request.form.get(
        "phoneNumber", ""
    ).strip()

    if not phone_number:
        return jsonify({
            "error": "Phone number is required."
        }), 400

    otp = str(random.randint(100000, 999999))
    session[phone_number] = otp

    print(f"OTP for {phone_number}: {otp}")

    return jsonify({
        "message": "OTP generated successfully.",
        "otp": otp
    })


@app.route("/verify_otp", methods=["POST"])
def verify_otp():
    data = request.get_json(silent=True) or {}

    phone_number = data.get("phoneNumber", "")
    otp_entered = data.get("otp", "")

    correct_otp = session.get(phone_number)

    if not correct_otp:
        return jsonify({
            "error": "No OTP found. Please request a new OTP."
        }), 400

    if str(otp_entered) == str(correct_otp):
        return jsonify({
            "message": "OTP verified successfully!"
        }), 200

    return jsonify({
        "error": "Invalid OTP. Please try again."
    }), 400


# --------------------------------------------------
# LOGIN OTP
# --------------------------------------------------

@app.route("/send_login_otp", methods=["POST"])
def send_login_otp():
    voter_id = request.form.get(
        "voterId", ""
    ).strip()

    phone_number = request.form.get(
        "phoneNumber", ""
    ).strip()

    if not voter_id or not phone_number:
        return jsonify({
            "error": "Voter ID and phone number are required."
        }), 400

    user = User.query.filter_by(
        voter_id=voter_id,
        phone_number=phone_number
    ).first()

    if not user:
        return jsonify({
            "error": "User not found. Please register first."
        }), 400

    otp = str(random.randint(100000, 999999))
    session[phone_number] = otp

    print(f"Login OTP for {phone_number}: {otp}")

    return jsonify({
        "message": "Login OTP generated successfully.",
        "otp": otp
    })


@app.route("/verify_login_otp", methods=["POST"])
def verify_login_otp():
    data = request.get_json(silent=True) or {}

    phone_number = data.get("phoneNumber", "")
    otp_entered = data.get("otp", "")

    correct_otp = session.get(phone_number)

    if not correct_otp:
        return jsonify({
            "error": "No OTP found. Please request a new OTP."
        }), 400

    if str(otp_entered) == str(correct_otp):
        return jsonify({
            "message": "OTP verified successfully! You can now log in."
        }), 200

    return jsonify({
        "error": "Invalid OTP. Please try again."
    }), 400


# --------------------------------------------------
# DASHBOARD AND RESULTS
# --------------------------------------------------

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/result")
def result_page():
    vote_counts = db.session.query(
        VotingRecord.candidate,
        db.func.count(VotingRecord.candidate)
    ).group_by(
        VotingRecord.candidate
    ).order_by(
        db.func.count(VotingRecord.candidate).desc()
    ).all()

    results = {
        candidate: count
        for candidate, count in vote_counts
    }

    leading_candidate = (
        vote_counts[0] if vote_counts else None
    )

    return render_template(
        "result.html",
        results=results,
        leading_candidate=leading_candidate
    )


# --------------------------------------------------
# ADMIN LOGIN AND USER LIST
# --------------------------------------------------

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        admin_id = request.form.get(
            "admin_id", ""
        ).strip()

        admin_password = request.form.get(
            "admin_password", ""
        )

        if (
            admin_id == ADMIN_ID
            and admin_password == ADMIN_PASSWORD
        ):
            session["is_admin"] = True
            return redirect(url_for("admins_page"))

        return render_template(
            "admin_login.html",
            message="Incorrect Admin ID or Password!"
        )

    return render_template("admin_login.html")


@app.route("/admins")
def admins_page():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    # Include all registered users, not only users who voted.
    users = User.query.order_by(User.id.desc()).all()

    return render_template("admins.html", users=users)


# --------------------------------------------------
# ADMIN: VIEW AADHAAR
# --------------------------------------------------

@app.route("/view-aadhaar/<int:user_id>")
def view_aadhaar(user_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    user = db.session.get(User, user_id)

    if user is None:
        return "User not found.", 404

    if not user.aadhaar_card_path:
        return "No Aadhaar file found.", 404

    aadhaar_folder = os.path.abspath(UPLOAD_FOLDER)
    aadhaar_filename = os.path.basename(
        user.aadhaar_card_path
    )

    aadhaar_full_path = os.path.join(
        aadhaar_folder, aadhaar_filename
    )

    if not os.path.isfile(aadhaar_full_path):
        return "Aadhaar file not found.", 404

    return send_from_directory(
        aadhaar_folder,
        aadhaar_filename
    )


# --------------------------------------------------
# ADMIN: WATCH USER VIDEO
# --------------------------------------------------

@app.route("/view-user-video/<int:user_id>")
def view_user_video(user_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    user = db.session.get(User, user_id)

    if user is None:
        return "User not found.", 404

    if not user.video_path:
        return "No video recording is saved for this user.", 404

    video_folder = os.path.abspath(
        app.config["VIDEO_UPLOAD_FOLDER"]
    )

    video_filename = os.path.basename(user.video_path)

    video_full_path = os.path.join(
        video_folder, video_filename
    )

    if not os.path.isfile(video_full_path):
        print("Missing video file:", video_full_path)
        return "Video file not found in video_records.", 404

    return send_from_directory(
        video_folder,
        video_filename,
        mimetype="video/webm",
        as_attachment=False
    )


# --------------------------------------------------
# ADMIN LOGOUT
# --------------------------------------------------

@app.route("/admin-logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


# Compatibility route for older links.
@app.route("/video_records/<filename>")
def get_video(filename):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    return send_from_directory(
        os.path.abspath(app.config["VIDEO_UPLOAD_FOLDER"]),
        os.path.basename(filename)
    )


# --------------------------------------------------
# START APPLICATION
# --------------------------------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
