# Floorplan PDF Extraction & Area Calculator

A Flask web application for extracting floor plans from PDFs, detecting rooms, and calculating carpet/tile requirements with optional ML-based segmentation.

## ⚡ Quick Start (Windows)

**For the easiest setup, just run this:**

1. **Double-click** `setup.bat` - it handles everything automatically
2. **Double-click** `run.bat` to start the app
3. Open http://127.0.0.1:5000/ in your browser

Done! No command line knowledge needed.

**For detailed setup instructions**, see [SETUP.md](SETUP.md)

---

## Features

- **PDF Processing**: Upload floorplan PDFs and automatically extract room boundaries
- **Heuristic Detection**: Built-in OpenCV-based contour detection for room identification
- **ML Segmentation**: Optional U-Net model support for improved accuracy on complex plans
- **Accurate Calculations**: Compute room areas, carpet length, number of tiles required
- **Interactive Corrections**: Manually adjust detected polygons and recalculate metrics
- **Carpet Planning**: Optimize carpet roll orientation to minimize seams and waste

## System Requirements

- Python 3.8+
- Poppler (for PDF to image conversion)
- Pip package manager

## Installation

### Quick Setup (Recommended for Windows)

Simply run the automated setup script - it handles everything:

```bash
setup.bat
```

Then start the app with:

```bash
run.bat
```

### Manual Setup or Mac/Linux

For detailed step-by-step instructions for all platforms, see **[SETUP.md](SETUP.md)**

---

## Usage

### Run the Web App

```bash
python app.py
```

Open http://127.0.0.1:5000/ in your browser.

### Generate Sample Training Data

```bash
python sample_data.py
```

Creates a minimal dataset in `dataset/` for testing the segmentation pipeline.

### Train ML Segmentation Model

Prepare a dataset with images and corresponding binary masks:

```bash
python train_segmentation.py --data /path/to/dataset --epochs 30 --bs 8
```

This generates `model.pth` which can be placed in the project root for use in the web app.

### Convert PDFs to Images

```bash
python pdf_to_images.py --input-dir path/to/pdfs --output-dir dataset/images --dpi 300
```

### Generate Masks from LabelMe Annotations

```bash
python labelme_to_masks.py --images dataset/images --annotations labelme_json --output dataset/masks
```

## Configuration

### Web App Settings (in `app.py`)

- `MAX_PDF_SIZE`: Maximum PDF upload size (default: 10 MB)
- DPI for PDF conversion (default: 200)
- Model path: `model.pth` in project root

### Room Detection (in `app.py`)

- `min_area_px`: Minimum contour area to consider as room (default: 2000 pixels)
- Morphological operations for gap closing
- Polygon approximation tolerance

## Features Details

### Detection Modes

1. **Heuristic** (default): Uses thresholding, morphological operations, and contour extraction
2. **ML** (optional): U-Net model for accurate segmentation on complex plans

### Calculations

- **Area**: Room area in square meters (requires scale calibration)
- **Carpet Planning**: Calculates optimal strip orientation to minimize waste and seams
- **Tile Calculation**: Computes number of tiles needed based on tile size
- **Interactive Editing**: Drag vertices to adjust detected polygons in real-time

### Quality Improvements

- Proper error logging with timestamps
- Input validation and security checks
- Graceful fallback from ML to heuristic detection
- Type hints for better code clarity
- Comprehensive exception handling

## Project Structure

```
├── app.py                      # Main Flask application
├── sample_data.py              # Generate sample training data
├── train_segmentation.py       # Train U-Net model
├── ml_dataset.py               # Dataset loader for training
├── pdf_to_images.py            # Convert PDFs to images
├── labelme_to_masks.py         # Convert LabelMe JSON to masks
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── TRAINING.md                 # Training guide
├── templates/
│   ├── index.html              # Upload form
│   └── result.html             # Results with interactive editor
├── static/
│   └── output/                 # Generated images and CSVs
└── dataset/                    # Training dataset (if used)
```

## Troubleshooting

- **"PDF conversion failed"**: Ensure poppler is installed and in PATH
- **"Model not found"**: Place trained `model.pth` in project root
- **Slow performance**: Reduce PDF DPI or use GPU (update app.py for CUDA)
- **Poor detection**: Train an ML model or adjust heuristic parameters

## See Also

- [TRAINING.md](TRAINING.md) - Detailed ML training instructions
- [segmentation-models-pytorch](https://github.com/qubvel-org/segmentation_models.pytorch) - Model library
- [LabelMe](http://labelme.csail.mit.edu/) - Annotation tool

## Future Improvements

- UI to calibrate scale by drawing a reference line
- Support for multi-page PDFs
- GPU acceleration for ML inference
- REST API for batch processing
- Improved heuristic for colored/complex plans
