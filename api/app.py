import os
import sys
import uuid
import json
import logging
import shutil
import time
from datetime import datetime, timedelta

from flask import Flask, request, jsonify, url_for, abort
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from celery import Celery
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import functools

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../cli/BAT2')))
from cli.BAT2.api_endpoint import run_analyze

import secrets
from werkzeug.security import generate_password_hash, check_password_hash

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ─── Environment & Config ────────────────────────────────────────────────────
SERVER_NAME        = os.getenv("SERVER_NAME", "localhost:5000")
APPLICATION_ROOT   = os.getenv("APPLICATION_ROOT", "/api")
PREFERRED_URL_SCHEME = os.getenv("PREFERRED_URL_SCHEME", "https")
DATA_FOLDER        = os.getenv("DATA_FOLDER", "/app/data/")
DATABASE_FOLDER    = os.getenv("DATABASE_FOLDER", "/app/db")
DATABASE_URI       = os.getenv("DATABASE_URI", f"sqlite:///{os.path.join(DATABASE_FOLDER, 'state.db')}")
BROKER_URL         = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
RESULT_BACKEND     = os.getenv("CELERY_RESULT_BACKEND", BROKER_URL)
CLEANUP_DAYS       = int(os.getenv("CLEANUP_DAYS", "30"))

logger.debug(f"Server={SERVER_NAME}, Root={APPLICATION_ROOT}, Scheme={PREFERRED_URL_SCHEME}")
os.makedirs(DATA_FOLDER, exist_ok=True)
os.makedirs(DATABASE_FOLDER, exist_ok=True)
logger.debug(f"Data folder={DATA_FOLDER}, Database folder={DATABASE_FOLDER}")

# ─── Flask & SQLAlchemy Setup ────────────────────────────────────────────────
app = Flask(__name__)
app.config.update(
    SERVER_NAME=SERVER_NAME,
    APPLICATION_ROOT=APPLICATION_ROOT,
    PREFERRED_URL_SCHEME=PREFERRED_URL_SCHEME,
    SQLALCHEMY_DATABASE_URI=DATABASE_URI,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    broker_url=BROKER_URL,
    result_backend=RESULT_BACKEND,
)
CORS(app, resources={r"/*": {"origins": "*"}})

db = SQLAlchemy(app)

# ─── Models ───────────────────────────────────────────────────────────────────
class Job(db.Model):
    __tablename__ = "jobs"
    id              = db.Column(db.String, primary_key=True)
    status          = db.Column(db.String, nullable=False, default="pending")
    created_at      = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    keep            = db.Column(db.Boolean, default=False)
    options         = db.Column(db.Text,   nullable=False)  # JSON
    processed_files = db.Column(db.Text,   nullable=False)  # JSON list
    result_metadata = db.Column(db.Text)        # Final JSON
    snapshots       = db.relationship("Snapshot", back_populates="job",
                                    cascade="all, delete-orphan")
    password        = db.Column(db.String(255), nullable=True)

class Snapshot(db.Model):
    __tablename__ = "snapshots"
    id        = db.Column(db.Integer, primary_key=True)
    job_id    = db.Column(db.String, db.ForeignKey("jobs.id"), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    state     = db.Column(db.Text, nullable=False)  # JSON
    job       = db.relationship("Job", back_populates="snapshots")

with app.app_context():
    db.create_all()
    logger.info("Initialized SQLite database")

# ─── Celery Setup ─────────────────────────────────────────────────────────────
def make_celery(app):
    celery = Celery("app", broker=BROKER_URL, backend=RESULT_BACKEND)
    celery.conf.update(app.config)
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    celery.Task = ContextTask
    return celery

celery = make_celery(app)
logger.info("Celery initialized")

# ─── Helpers ─────────────────────────────────────────────────────────────────
def _upload_dir(job_id):
    path = os.path.join(DATA_FOLDER, job_id, "uploads")
    os.makedirs(path, exist_ok=True)
    return path

url_for = functools.partial(url_for, _scheme=PREFERRED_URL_SCHEME, _external=True)

def _get_processed_files(job_id):
    job = Job.query.get(job_id)
    if not job:
        return {}
    processed_list = json.loads(job.processed_files or "[]")
    return {
        "input": next((f for f in processed_list), None),
    }

# ─── Celery Task ─────────────────────────────────────────────────────────────
@celery.task(bind=True)
def process_annotation(self, job_id, keep_flag):
    logger.info(f"[Celery] Start job {job_id}")
    job = Job.query.get(job_id)
    if not job:
        logger.error(f"[Celery] Job {job_id} not found in DB")
        return

    # 1) update status & keep flag
    job.status  = "processing"
    job.keep    = keep_flag
    job.options = json.dumps({"keep": keep_flag})
    db.session.commit()

    try:
        logger.info(f"[Celery] Running BAT2 analysis for job {job_id}")
        results_path: str | None = run_analyze(_upload_dir(job_id))
        if results_path is None:
            raise RuntimeError("BAT2 failed")

        with open(results_path, "r") as fd:
            final_json = fd.read()
        _job = Job.query.get(job_id)
        _job.result_metadata = final_json
        _job.status = "completed"
        db.session.commit()
        logger.info(f"[Celery] Job {job_id} completed")

    except Exception as e:
        logger.error(f"[Celery] BAT2 failed: {e}")
        _job = Job.query.get(job_id)
        _job.status = "error"
        db.session.commit()

# ─── Cleanup Scheduler ───────────────────────────────────────────────────────
def cleanup_old_entries():
    logger.info("[Scheduler] Running cleanup")
    cutoff = datetime.utcnow() - timedelta(days=CLEANUP_DAYS)
    old_jobs = Job.query.filter(Job.keep==False, Job.created_at < cutoff).all()
    for job in old_jobs:
        folder = os.path.join(DATA_FOLDER, job.id)
        shutil.rmtree(folder, ignore_errors=True)
        db.session.delete(job)
        logger.info(f"[Scheduler] Removed job {job.id}")
    db.session.commit()

scheduler = BackgroundScheduler()
scheduler.add_job(func=cleanup_old_entries,
                  trigger=CronTrigger(hour=0, minute=0),
                  id="cleanup")
scheduler.start()
logger.info("Scheduled daily cleanup at midnight UTC")

# ─── API Endpoints ──────────────────────────────────────────────────────────
@app.route("/api/annotate", methods=["POST"])
def create_annotation():
    logger.info("[API] Create new job")
    job_id = str(uuid.uuid4())
    keep   = request.form.get("keep", "false").lower() == "true"
    os.makedirs(os.path.join(DATA_FOLDER, job_id), exist_ok=True)

    # save uploaded files
    for f in request.files.values():
        dest = os.path.join(_upload_dir(job_id), f.filename)
        f.save(dest)
        logger.debug(f"[API] Saved {dest}")

    # create DB record
    pin = str(secrets.randbelow(900000) + 100000)  # generate a 6-digit pincode
    hashed_pin = generate_password_hash(pin)

    job = Job(
        id=job_id,
        status="pending",
        keep=keep,
        options=json.dumps({"keep": keep}),
        processed_files=json.dumps([]),
        result_metadata=None,
        password=hashed_pin,
    )
    db.session.add(job)
    db.session.commit()

    # enqueue
    process_annotation.delay(job_id, keep)
    logger.info(f"[API] Enqueued {job_id}")

    return jsonify({
        "uuid": job_id,
        "status_url":  url_for("get_status",  uuid=job_id, _external=True),
        "results_url": url_for("get_results", uuid=job_id, _external=True),
        "pin": pin,
        "delete_url":  url_for("delete_job", uuid=job_id, _external=True),
    }), 202

@app.route("/api/annotate/<uuid>", methods=["POST"])
def update_annotation(uuid):
    logger.info(f"[API] Update job {uuid}")
    job = Job.query.get(uuid)
    if not job:
        abort(404)
    # save any new files only
    for f in request.files.values():
        dest = os.path.join(_upload_dir(uuid), f.filename)
        if os.path.exists(dest):
            logger.debug(f"[API] {f.filename} already exists, skipping")
            continue
        f.save(dest)
        logger.debug(f"[API] Saved additional {dest}")

    # re-enqueue
    job.status = "pending"
    db.session.commit()
    process_annotation.delay(uuid, False)
    logger.info(f"[API] Re-enqueued {uuid}")
    return jsonify({"uuid": uuid}), 202

@app.route("/api/annotate/<uuid>", methods=["DELETE"])
def delete_job(uuid):
    logger.info(f"[API] Delete job {uuid}")
    job = Job.query.get(uuid)
    if not job:
        abort(404)

    # check password
    pin = request.form.get("pin")
    if not pin or not job.password or not check_password_hash(job.password, pin):
        return jsonify({"error": "Invalid PIN"}), 403

    # delete files and DB entry
    folder = os.path.join(DATA_FOLDER, uuid)
    shutil.rmtree(folder, ignore_errors=True)
    db.session.delete(job)
    db.session.commit()
    logger.info(f"[API] Deleted job {uuid}")
    return jsonify({"message": f"Job {uuid} deleted"}), 200

@app.route("/api/annotate/<uuid>", methods=["GET"])
def get_status(uuid):
    logger.info(f"[API] Status check for {uuid}")
    job = Job.query.get(uuid)
    if not job:
        abort(404)
    resp = {
        "uuid":    job.id,
        "status":  job.status,
        "created": job.created_at.isoformat(),
        "expires": (job.created_at + timedelta(days=CLEANUP_DAYS)).isoformat(),
        "options": json.loads(job.options),
        "processed_files": _get_processed_files(job.id),
    }
    if job.status == "completed":
        resp["results_url"] = url_for("get_results", uuid=job.id, _external=True)
    return jsonify(resp)

@app.route("/api/annotate/<uuid>/results", methods=["GET"])
def get_results(uuid):
    logger.info(f"[API] Results for {uuid}")
    job = Job.query.get(uuid)
    if not job or not job.result_metadata:
        abort(404)

    return jsonify(json.loads(job.result_metadata))

if __name__ == "__main__":
    logger.info("Starting GROMACS MetaDump API...")
    app.run(host="0.0.0.0", port=5000)