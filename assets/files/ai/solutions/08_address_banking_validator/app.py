#!/usr/bin/env python3
"""
Workday Address & Banking Validator
Accenture Finance Technology Practice

Run: python app.py
Opens at: http://localhost:8090
"""

from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
import os
import uuid
import tempfile
from pathlib import Path

from workday_validator import validate_address_file, validate_banking_file

app = Flask(__name__)
CORS(app)

SESSIONS = {}  # session_id -> {address_path, banking_path}
TEMP_DIR = Path(tempfile.gettempdir()) / "wd_validator"
TEMP_DIR.mkdir(exist_ok=True)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok", "tool": "Workday Address & Banking Validator"})


@app.route("/api/validate/addresses", methods=["POST"])
def validate_addresses():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    ext = Path(f.filename).suffix.lower()
    if ext not in (".xlsx", ".xls", ".csv"):
        return jsonify({"error": "File must be .xlsx, .xls, or .csv"}), 400

    session_id = str(uuid.uuid4())
    input_path = TEMP_DIR / f"{session_id}_input{ext}"
    output_path = TEMP_DIR / f"{session_id}_address_output.xlsx"

    try:
        f.save(str(input_path))
        results = validate_address_file(str(input_path), str(output_path))
        SESSIONS[session_id] = {"address_output": str(output_path)}
        results["session_id"] = session_id
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if input_path.exists():
            input_path.unlink(missing_ok=True)


@app.route("/api/validate/banking", methods=["POST"])
def validate_banking():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    ext = Path(f.filename).suffix.lower()
    if ext not in (".xlsx", ".xls", ".csv"):
        return jsonify({"error": "File must be .xlsx, .xls, or .csv"}), 400

    session_id = str(uuid.uuid4())
    input_path = TEMP_DIR / f"{session_id}_input{ext}"
    output_path = TEMP_DIR / f"{session_id}_banking_output.xlsx"

    try:
        f.save(str(input_path))
        results = validate_banking_file(str(input_path), str(output_path))
        SESSIONS[session_id] = {"banking_output": str(output_path)}
        results["session_id"] = session_id
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if input_path.exists():
            input_path.unlink(missing_ok=True)


@app.route("/api/download/address/<session_id>")
def download_address(session_id):
    sess = SESSIONS.get(session_id)
    if not sess or "address_output" not in sess:
        return jsonify({"error": "Session not found"}), 404
    path = sess["address_output"]
    if not os.path.exists(path):
        return jsonify({"error": "Output file not found"}), 404
    return send_file(path, as_attachment=True, download_name="workday_address_validated.xlsx")


@app.route("/api/download/banking/<session_id>")
def download_banking(session_id):
    sess = SESSIONS.get(session_id)
    if not sess or "banking_output" not in sess:
        return jsonify({"error": "Session not found"}), 404
    path = sess["banking_output"]
    if not os.path.exists(path):
        return jsonify({"error": "Output file not found"}), 404
    return send_file(path, as_attachment=True, download_name="workday_banking_validated.xlsx")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8090))
    print(f"\n{'='*60}")
    print(f"  Workday Address & Banking Validator")
    print(f"  Accenture Finance Technology Practice")
    print(f"{'='*60}")
    print(f"  Open in browser: http://localhost:{port}")
    print(f"  Press Ctrl+C to stop\n")
    app.run(host="0.0.0.0", port=port, debug=False)
