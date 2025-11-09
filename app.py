import os
import uuid
import zipfile
import base64
import numpy as np
from flask import Flask, render_template, request, jsonify, send_file, url_for
from PIL import Image
import glob

# === Setup ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
CLEANED_DIR = os.path.join(BASE_DIR, "static", "cleaned")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CLEANED_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static", template_folder="templates")
app.static_folder = 'static'

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

@app.route("/upload", methods=["POST"])
def upload():
    try:
        if "noisy_zip" not in request.files or "mask_zip" not in request.files:
            return jsonify({"error": "Please upload both noisy and mask ZIP files."}), 400

        noisy_zip = request.files["noisy_zip"]
        mask_zip = request.files["mask_zip"]

        uid = uuid.uuid4().hex
        noisy_folder = os.path.join(UPLOAD_DIR, f"noisy_{uid}")
        mask_folder = os.path.join(UPLOAD_DIR, f"mask_{uid}")
        os.makedirs(noisy_folder, exist_ok=True)
        os.makedirs(mask_folder, exist_ok=True)

        noisy_zip_path = os.path.join(UPLOAD_DIR, f"noisy_{uid}.zip")
        mask_zip_path = os.path.join(UPLOAD_DIR, f"mask_{uid}.zip")
        noisy_zip.save(noisy_zip_path)
        mask_zip.save(mask_zip_path)

        def extract_flat(zip_path, dest_folder):
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for member in zip_ref.namelist():
                    filename = os.path.basename(member)
                    if not filename:
                        continue
                    with zip_ref.open(member) as source, open(os.path.join(dest_folder, filename), "wb") as target:
                        target.write(source.read())

        extract_flat(noisy_zip_path, noisy_folder)
        extract_flat(mask_zip_path, mask_folder)
        os.remove(noisy_zip_path)
        os.remove(mask_zip_path)

        def list_files(path, exts):
            files = {}
            for f in os.listdir(path):
                ext = os.path.splitext(f)[1].lower()
                if ext in exts:
                    base = os.path.splitext(f)[0]
                    files[base] = os.path.join(path, f)
            return files

        noisy_files = list_files(noisy_folder, {".png", ".jpg", ".jpeg"})
        mask_files = list_files(mask_folder, {".npy"})

        def normalize_name(n):
            n = n.lower()
            for prefix in ["mask_", "output_", "pred_", "seg_", "m_"]:
                if n.startswith(prefix):
                    n = n[len(prefix):]
            for suffix in ["_mask", "_seg", "_output", "_pred"]:
                if n.endswith(suffix):
                    n = n[: -len(suffix)]
            return n

        normalized_noisy = {normalize_name(k): v for k, v in noisy_files.items()}
        normalized_masks = {normalize_name(k): v for k, v in mask_files.items()}

        matched_names = sorted(set(normalized_noisy.keys()) & set(normalized_masks.keys()))
        if not matched_names:
            return jsonify({"error": "No matching image/mask filenames found — even after normalization."}), 400

        pairs = []
        for name in matched_names[:10]:
            noisy_path = normalized_noisy[name]
            mask_path = normalized_masks[name]

            try:
                masks_arr = np.load(mask_path, allow_pickle=False)
                masks = normalize_masks_array(masks_arr)
            except Exception as e:
                return jsonify({"error": f"Failed to load {name}.npy: {str(e)}"}), 400

            N, H, W = masks.shape
            if N > 254:
                return jsonify({"error": f"{name}.npy has too many masks (>254)."}), 400

            label_map = np.zeros((H, W), dtype=np.uint8)
            for i in range(N):
                label_map[masks[i] > 0] = i + 1

            label_name = f"{name}_label.png"
            label_path = os.path.join(UPLOAD_DIR, label_name)
            Image.fromarray(label_map, mode="L").save(label_path)

            noisy_rel = os.path.relpath(noisy_path, UPLOAD_DIR).replace(os.sep, "/")
            pairs.append({
                "noisy_url": url_for('static', filename=f'uploads/{noisy_rel}'),
                "label_url": url_for('static', filename=f'uploads/{label_name}'),
                "width": int(W),
                "height": int(H),
                "num_masks": int(label_map.max()),
                "name": name
            })

        return jsonify({"pairs": pairs})

    except Exception as e:
        # Always return JSON on any crash
        return jsonify({"error": f"Server error: {str(e)}"}), 500

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
