import os
import re
import json
from typing import Optional, Tuple
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

from extractor import extract_text_from_stream
from hf_client import SimilarityClient, GradioSpaceError

# ---- Config (via env or defaults) -------------------------------------------
SPACE_URL = os.getenv("SPACE_URL", "https://rathod31-kannada-english-sim.hf.space")
API_NAME  = os.getenv("SPACE_API_NAME", "/_on_click")   # from your current Space
REQUEST_MAX_MB = float(os.getenv("REQUEST_MAX_MB", "20"))
MAX_TEXT_CHARS = int(os.getenv("MAX_TEXT_CHARS", "20000"))  # post-trim cap
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")  # e.g., "https://your-webapp.example"

# -----------------------------------------------------------------------------

app = Flask(__name__)
# Limit request size
app.config['MAX_CONTENT_LENGTH'] = int(REQUEST_MAX_MB * 1024 * 1024)

# CORS for Unity / web clients
CORS(app, resources={r"/*": {"origins": ALLOWED_ORIGINS}})

# Initialize HF client
sim_client = SimilarityClient(space_url=SPACE_URL, api_name=API_NAME)

LANG_SET = {"kannada", "english"}

def _clean_text(s: str) -> str:
    # basic whitespace cleanup + cap
    s = re.sub(r'\s+', ' ', s or '').strip()
    if len(s) > MAX_TEXT_CHARS:
        s = s[:MAX_TEXT_CHARS]
    return s

def _validate_lang(lang: str) -> str:
    if not lang:
        raise ValueError("Missing 'lang'. Valid values: 'kannada' or 'english'.")
    l = lang.strip().lower()
    if l not in LANG_SET:
        raise ValueError("Invalid 'lang'. Use 'kannada' or 'english'.")
    return l.capitalize()  # Space expects first-letter capitalized

@app.get("/healthz")
def healthz():
    ok = sim_client.healthcheck()
    return jsonify({"status": "ok" if ok else "degraded", "space": SPACE_URL})

@app.get("/")
def root():
    return jsonify({
        "ok": True,
        "service": "Similarity Middleware for HF Space",
        "space_url": SPACE_URL,
        "endpoints": ["/v1/compare-text", "/v1/compare-file", "/healthz"]
    })

# -------- JSON: direct text-to-text ------------------------------------------
@app.post("/v1/compare-text")
def compare_text():
    """
    JSON body:
    {
      "lang": "kannada" | "english",
      "text1": "....",
      "text2": "...."
    }
    """
    try:
        body = request.get_json(force=True, silent=False)
    except Exception:
        return jsonify(error="Invalid JSON body."), 400

    lang = body.get("lang")
    text1 = _clean_text(body.get("text1", ""))
    text2 = _clean_text(body.get("text2", ""))

    if not text1 or not text2:
        return jsonify(error="Both 'text1' and 'text2' are required and non-empty."), 400

    try:
        lang_for_space = _validate_lang(lang)
    except ValueError as e:
        return jsonify(error=str(e)), 400

    try:
        similarity = sim_client.compare(lang_for_space, text1, text2)
        return jsonify({
            "ok": True,
            "lang": lang_for_space,
            "similarity": similarity
        })
    except GradioSpaceError as e:
        return jsonify(error=f"Space call failed: {e.message}", detail=e.detail), 502
    except Exception as e:
        return jsonify(error="Unexpected server error.", detail=str(e)), 500

# -------- Multipart: transcript + file ---------------------------------------
@app.post("/v1/compare-file")
def compare_file():
    """
    multipart/form-data fields:
      lang             : kannada|english
      transcript_text  : string
      file             : uploaded file (.txt, .pdf, .docx)
    """
    lang = request.form.get("lang", "")
    transcript_text = _clean_text(request.form.get("transcript_text", ""))

    if "file" not in request.files:
        return jsonify(error="Missing 'file' field."), 400

    uploaded = request.files["file"]
    filename = secure_filename(uploaded.filename or "")
    if not filename:
        return jsonify(error="Invalid file name."), 400

    try:
        file_text, detected_type = extract_text_from_stream(uploaded.stream, filename)
    except ValueError as e:
        return jsonify(error=str(e)), 415
    except Exception as e:
        return jsonify(error="Failed to extract text from file.", detail=str(e)), 500

    file_text = _clean_text(file_text)

    if not transcript_text:
        return jsonify(error="Missing or empty 'transcript_text'."), 400
    if not file_text:
        return jsonify(error=f"No extractable text found in '{filename}'. Ensure it is a text/PDF/Docx."), 422

    try:
        lang_for_space = _validate_lang(lang)
    except ValueError as e:
        return jsonify(error=str(e)), 400

    try:
        similarity = sim_client.compare(lang_for_space, transcript_text, file_text)
        return jsonify({
            "ok": True,
            "lang": lang_for_space,
            "file": {"name": filename, "detected_type": detected_type, "chars": len(file_text)},
            "similarity": similarity
        })
    except GradioSpaceError as e:
        return jsonify(error=f"Space call failed: {e.message}", detail=e.detail), 502
    except Exception as e:
        return jsonify(error="Unexpected server error.", detail=str(e)), 500
