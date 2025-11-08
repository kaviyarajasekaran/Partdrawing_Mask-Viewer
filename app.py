import os
import uuid
import zipfile
import numpy as np
from flask import Flask, render_template, request, jsonify, url_for
from PIL import Image

# === Setup ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static", template_folder="templates")


# === Normalize .npy masks ===
def normalize_masks_array(arr):
    arr = np.asarray(arr)
    if arr.ndim == 2:
        arr = arr[np.newaxis, ...]
    elif arr.ndim == 3:
        N, A, B = arr.shape
        if N > 50 and (A <= 50 or B <= 50):
            arr = np.transpose(arr, (2, 0, 1))
    else:
        raise ValueError("Unsupported .npy shape: " + str(arr.shape))
    arr = (arr != 0).astype(np.uint8)
    return arr


@app.route("/")
def index():
    return render_template("index.html")

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

if __name__ == "__main__":
    app.run(debug=True)
