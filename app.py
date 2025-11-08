import os
import uuid
import zipfile
import base64
import numpy as np
from flask import Flask, render_template, request, jsonify, send_file, url_for
from PIL import Image

# === Setup ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
CLEANED_DIR = os.path.join(BASE_DIR, "static", "cleaned")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CLEANED_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static", template_folder="templates")

def normalize_masks_array(arr):
    arr = np.asarray(arr)
    if arr.ndim == 2:
        arr = arr[np.newaxis, ...]
    elif arr.ndim == 3:
        N, A, B = arr.shape
        if N > 50 and (A <= 50 or B <= 50):
            arr = np.transpose(arr, (2, 0, 1))
    arr = (arr != 0).astype(np.uint8)
    return arr

# === ROUTES ===

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/viewer")
def viewer():
    return render_template("mask-viewer.html")

@app.route("/clean")
def clean():
    return render_template("clean.html")


# === UPLOAD FOR ERASER PAGE ===
@app.route("/upload_clean", methods=["POST"])
def upload_clean():
    try:
        if "image_zip" not in request.files:
            return jsonify({"error": "Please upload an image or ZIP file."}), 400

        file = request.files["image_zip"]
        uid = uuid.uuid4().hex
        folder = os.path.join(UPLOAD_DIR, f"clean_{uid}")
        os.makedirs(folder, exist_ok=True)

        zip_path = os.path.join(folder, file.filename)
        file.save(zip_path)

        image_urls = []

        # Handle ZIP or single file
        if zip_path.lower().endswith(".zip"):
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(folder)
            for root, _, files in os.walk(folder):
                for f in files:
                    if f.lower().endswith((".png", ".jpg", ".jpeg")):
                        rel = os.path.relpath(os.path.join(root, f), UPLOAD_DIR)
                        image_urls.append(url_for('static', filename=f"uploads/{rel.replace(os.sep, '/')}"))
        else:
            rel = os.path.relpath(zip_path, UPLOAD_DIR)
            image_urls.append(url_for('static', filename=f"uploads/{rel.replace(os.sep, '/')}"))

        if not image_urls:
            return jsonify({"error": "No images found in upload."}), 400

        return jsonify({"images": image_urls})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# === SAVE SINGLE CLEANED IMAGE ===
@app.route('/save_cleaned_image', methods=['POST'])
def save_cleaned_image():
    try:
        image_data = request.form['image_data']
        filename = request.form['filename']

        image_data = image_data.split(',')[1]
        img_bytes = base64.b64decode(image_data)

        file_path = os.path.join(CLEANED_DIR, filename)
        with open(file_path, 'wb') as f:
            f.write(img_bytes)

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# === DOWNLOAD ALL CLEANED IMAGES AS ZIP ===
@app.route('/download_all_cleaned')
def download_all_cleaned():
    zip_filename = "cleaned_images.zip"
    zip_path = os.path.join(CLEANED_DIR, zip_filename)

    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for root, _, files in os.walk(CLEANED_DIR):
            for f in files:
                if f.endswith(('.png', '.jpg', '.jpeg')):
                    zipf.write(os.path.join(root, f), f)

    return send_file(zip_path, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
