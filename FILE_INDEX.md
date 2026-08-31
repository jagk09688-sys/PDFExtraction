# Project File Index

A quick reference guide to every file in the project and what it does.

## 🚀 Getting Started Files

These are the files users interact with first:

| File | What it is | What to do with it |
|------|-----------|-------------------|
| **START_HERE.txt** | Quick reference card | Read this first |
| **setup.bat** | Windows setup automation | Double-click to install everything |
| **run.bat** | Flask app launcher | Double-click to start the server |
| **test_smoke.py** | Diagnostic tool | Run to verify setup: `python test_smoke.py` |

---

## 📖 Documentation Files

These explain how to use and develop the project:

| File | Purpose | Read when you want to... |
|------|---------|--------------------------|
| **README.md** | Main documentation | Understand features and basic usage |
| **SETUP.md** | Installation guide | Set up the project (detailed steps) |
| **TRAINING.md** | ML training guide | Train your own segmentation model |
| **DEVELOPMENT.md** | Developer guide | Modify or extend the code |
| **STATUS.md** | Project status | Know what's complete and what's not |
| **.env.example** | Configuration template | Customize settings (copy to `.env`) |

---

## 🎯 Core Application Files

The main Python code that runs the app:

| File | Purpose | Used by |
|------|---------|---------|
| **app.py** | Main Flask web server | The Flask development server |
| **config.py** | Configuration loader | app.py (reads from .env) |
| **templates/index.html** | PDF upload form | Web server (route: /) |
| **templates/result.html** | Results display & editor | Web server (route: /extract) |
| **static/output/** | Generated images & CSVs | app.py (saves results here) |

---

## 🤖 ML Training & Utilities

These are optional utilities for advanced ML features:

| File | Purpose | When to use |
|------|---------|-----------|
| **sample_data.py** | Generate test data | For testing ML pipeline |
| **train_segmentation.py** | Train segmentation model | To create your own ML model |
| **ml_dataset.py** | Dataset loader for training | Used by train_segmentation.py |
| **pdf_to_images.py** | Batch PDF to image converter | To prepare training data |
| **labelme_to_masks.py** | LabelMe annotation converter | To convert annotations to masks |
| **TRAINING.md** | ML training instructions | To understand the process |

---

## 📝 Configuration & Environment Files

Control app behavior without editing code:

| File | Purpose |
|------|---------|
| **.env.example** | Configuration template (copy to .env) |
| **.env** | Your custom configuration (create from .env.example) |
| **.gitignore** | Files to exclude from version control |

---

## 📊 Dependency Files

Define what Python packages are needed:

| File | Purpose |
|------|---------|
| **requirements.txt** | All Python package dependencies |

---

## 🧪 Testing Files

For verifying the setup works:

| File | Purpose | How to run |
|------|---------|-----------|
| **test_smoke.py** | Basic smoke tests | `python test_smoke.py` |

---

## 📁 Directory Structure

```
PDF Extraction/
│
├── 📄 START_HERE.txt              ← Read this first!
├── 📋 README.md                   ← Main documentation
├── 📋 SETUP.md                    ← Setup instructions
├── 📋 TRAINING.md                 ← ML training guide
├── 📋 DEVELOPMENT.md              ← Developer guide
├── 📋 STATUS.md                   ← Project status
│
├── 🚀 setup.bat                   ← Run once: installation
├── ▶️  run.bat                     ← Run daily: start server
├── 🧪 test_smoke.py               ← Test: verify setup
│
├── 🐍 app.py                      ← Main Flask app
├── ⚙️  config.py                  ← Configuration loader
├── 📄 .env.example                ← Config template
├── 📄 .env                        ← Your custom config
│
├── 📚 requirements.txt            ← Python dependencies
├── 🔒 .gitignore                  ← Git ignore rules
│
├── 🎯 sample_data.py              ← Generate test data
├── 🤖 train_segmentation.py       ← Train ML model
├── 🔧 ml_dataset.py               ← ML dataset loader
├── 📄 pdf_to_images.py            ← Batch PDF converter
├── 📄 labelme_to_masks.py         ← Annotation converter
│
├── 📁 templates/                  ← HTML templates
│   ├── index.html                 ← Upload form
│   └── result.html                ← Results page
│
└── 📁 static/                     ← Web static files
    └── output/                    ← Generated results
```

---

## 🎯 Common Workflows

### I just downloaded the project
1. Read: **START_HERE.txt**
2. Read: **README.md** (quick overview)
3. Run: **setup.bat** (installation)
4. Run: **run.bat** (start server)
5. Open: http://127.0.0.1:5000/

### I want to change settings
1. Copy **.env.example** → **.env**
2. Edit **.env** with your preferred settings
3. Restart **run.bat**

### I want to train an ML model
1. Read: **TRAINING.md**
2. Prepare dataset with images and masks
3. Run: `python train_segmentation.py --data /path/to/dataset`
4. Place resulting `model.pth` in project root

### I want to modify the code
1. Read: **DEVELOPMENT.md**
2. Edit **app.py** or relevant files
3. Restart **run.bat** to test changes
4. Debug using browser DevTools (F12)

### Something's not working
1. Run: `python test_smoke.py`
2. Check: **SETUP.md** troubleshooting section
3. Enable: `LOG_LEVEL=DEBUG` in **.env**
4. Restart: **run.bat**

---

## 📊 File Size Guide

| File | Size | What it affects |
|------|------|-----------------|
| app.py | ~15 KB | Server functionality |
| requirements.txt | ~0.3 KB | Package versions |
| templates/result.html | ~20 KB | Web UI interactivity |
| Installed packages | ~2+ GB | Disk space needed |
| model.pth (optional) | ~100-500 MB | Optional ML feature |

---

## 🔐 Security Notes

**Safe files to share:**
- README.md, SETUP.md, DEVELOPMENT.md, STATUS.md
- app.py, config.py
- templates/, static/
- requirements.txt

**Keep private:**
- .env (contains configuration)
- model.pth (if trained on sensitive data)
- static/output/ (user PDFs and results)

**Already ignored:**
- Virtual environment (venv/)
- Python cache (__pycache__/)
- Dependencies (site-packages/)

See .gitignore for full list.

---

## 📚 Quick Reference

**To START the app:**
```
Double-click run.bat
```

**To STOP the app:**
```
Press Ctrl+C in the terminal
```

**To CHANGE settings:**
```
Edit .env file and restart
```

**To TRAIN an ML model:**
```
python train_segmentation.py --data dataset/
```

**To TEST the setup:**
```
python test_smoke.py
```

---

## 🎓 Learning Path

1. **Beginner**: START_HERE.txt → README.md → setup.bat
2. **User**: SETUP.md → use the web interface
3. **Advanced**: TRAINING.md → train ML models
4. **Developer**: DEVELOPMENT.md → modify code

---

**Note**: This index was last updated 2026-08-31. File descriptions may change as features are added or updated.
