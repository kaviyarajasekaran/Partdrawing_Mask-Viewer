# Partdrawing Mask Viewer
A simple and elegant web application to visualize **mask overlays** on part drawing images.  
This tool allows users to upload multiple images, view them interactively, and switch between them easily using navigation buttons.

# Features
-  Upload part drawing and corresponding mask images.
- 🔁 Navigate between images using **Previous** and **Next** buttons.
-  Modern, responsive user interface with smooth animations.
- ⚙️ Canvas-based overlay rendering for precise visualization.
-  Works fully offline — no backend required.

# Tech Stack
- **HTML5**  
- **CSS3** (custom gradient UI and button styling)  
- **JavaScript (Vanilla)** for interactive image control  

# Folder Structure
Mask website/
│
├── index.html # Main webpage
├── style.css # (or inline CSS)
├── script.js # Handles image rendering & navigation
├── assets/
│ ├── logo.png # Logo (optional)
│ ├── sample1.png # Example image
│ └── sample2.png
└── README.md # Project info

# Usage
1. Open **`index.html`** in your browser.  
2. Upload:
   - A part drawing image.  
   - A mask image to overlay.  
3. Use **← Previous Image** and **Next Image →** to switch between loaded samples.

# Upload Section
Users can upload ZIP files containing noisy images and masks.
<p align="center">
<img src="Noisy img.png" alt="User Interface">
</p>

# Image + Mask Viewer
View part drawings with corresponding colored mask overlays.
<p align="center">
<img src="Mask img.png" alt="Mask viewer">
</p>
 
# Customization
- Replace the logo or background gradient in the CSS to match your style.  
- Adjust button colors and layout directly in the `<style>` section.  
- Modify JavaScript to load from local folders or remote sources.

# License
This project is open for educational and personal use.  
