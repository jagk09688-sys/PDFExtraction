# Quick Start Setup Guide

## For Windows Users (Easiest)

Simply run the automated setup script - it handles everything automatically:

1. **Double-click** `setup.bat` in the project folder
2. The script will:
   - Check for Python
   - Create a virtual environment
   - Install all Python dependencies
   - Detect and set up Poppler (for PDF conversion)
   - Create necessary directories

3. Once setup completes, run the app:
   - **Double-click** `run.bat` to start the Flask server
   - Open http://127.0.0.1:5000/ in your browser

That's it! No command line needed.

---

## Manual Setup (if scripts don't work)

### Step 1: Install Python
- Download Python 3.8+ from https://www.python.org/
- **Important**: Check "Add Python to PATH" during installation

### Step 2: Install Poppler (Windows)
- Download from: https://github.com/oschwartz10612/poppler-windows/releases/
- Choose the latest version (e.g., `Release-24.08.0.zip`)
- Extract to a folder (e.g., `C:\poppler`)
- Add to Windows PATH:
  1. Press `Win + X` → System
  2. Click "Advanced system settings"
  3. Click "Environment Variables"
  4. Under "System variables", click "Path" → "Edit"
  5. Click "New" and add: `C:\poppler\Library\bin`
  6. Click OK and restart your terminal

### Step 3: Install Python Dependencies
```bash
# Navigate to project folder
cd "c:\Users\John\Desktop\PDF Extraction"

# Create virtual environment
python -m venv venv

# Activate it (Windows)
venv\Scripts\activate.bat

# Install dependencies
pip install -r requirements.txt
```

### Step 4: Run the Flask App
```bash
python app.py
```

Open http://127.0.0.1:5000/ in your browser.

---

## For Mac/Linux Users

### macOS
```bash
# Install Poppler
brew install poppler

# Navigate to project
cd ~/Desktop/PDF\ Extraction

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

### Linux (Ubuntu/Debian)
```bash
# Install Poppler
sudo apt-get install poppler-utils

# Rest is same as macOS
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

---

## Troubleshooting

### "PDF conversion failed" Error
- **Cause**: Poppler not installed
- **Solution**: 
  - Windows: Re-run `setup.bat`
  - Mac/Linux: Install via package manager (see above)
  - Verify: Run `pdftoimage -v` in terminal

### "Module not found" Error
- **Cause**: Dependencies not installed
- **Solution**: Run `pip install -r requirements.txt` while venv is activated

### Virtual environment not activating
- **Windows**: Use `venv\Scripts\activate.bat`
- **Mac/Linux**: Use `source venv/bin/activate`

### Port 5000 already in use
- Kill existing Flask process or edit `app.py` to use different port (line end)

### Still having issues?
1. Ensure you have Python 3.8+ (check with `python --version`)
2. Make sure Poppler is in PATH (check with `pdftoimage -v`)
3. Delete `venv` folder and start setup again
4. Check that you're in the correct project directory

---

## Next Steps

Once the app is running:
1. Visit http://127.0.0.1:5000/
2. Upload a sample PDF floorplan
3. The app will automatically detect rooms
4. Optionally adjust detected polygons
5. Download results as CSV

For ML segmentation support, see [TRAINING.md](TRAINING.md)
