# Quick Start: Building a Robust Floorplan Detection Model

## Phase 1: Bootstrap with Synthetic Data (1-2 hours)

### Step 1: Generate Synthetic Dataset
```bash
# Generate 500 synthetic floorplans with medium variation
python generate_synthetic_dataset.py \
  --count 500 \
  --output dataset/synthetic \
  --variation-level medium \
  --seed 42

# For higher variation
python generate_synthetic_dataset.py \
  --count 1000 \
  --output dataset/synthetic \
  --variation-level high
```

**What you get:**
- `dataset/synthetic/train/images/` - 400 training floorplans
- `dataset/synthetic/train/masks/` - Corresponding room masks
- `dataset/synthetic/val/images/` - 100 validation floorplans
- `dataset/synthetic/val/masks/` - Corresponding masks

### Step 2: Train Model on Synthetic Data
```bash
# Train with basic augmentation
python train_segmentation.py \
  --data dataset/synthetic \
  --epochs 30 \
  --bs 8 \
  --checkpoint model_synthetic.pth

# Or use advanced training with more augmentation
python train_advanced.py \
  --data dataset/synthetic \
  --epochs 50 \
  --bs 8 \
  --augment-level high \
  --checkpoint model_synthetic_v2.pth
```

**Expected results:**
- ✅ Train loss: ~0.15
- ✅ Val loss: ~0.25
- ✅ Works on simple, clean PDFs

---

## Phase 2: Gather Real Data (4-6 hours)

### Option A: Download from Online Archives (Easiest)

**Free Floorplan Sources:**

1. **Wikimedia Commons** (~10K plans)
   - Download from: https://commons.wikimedia.org/wiki/Category:Floorplans
   - Search: "floorplan", "floor plan", "architectural plan"
   - Bulk download script:
   ```bash
   wget -r -l 2 -nd -A "*.jpg" -A "*.png" \
     "https://commons.wikimedia.org/wiki/Category:Floorplans"
   ```

2. **OpenStreetMap Buildings** (~1M buildings)
   - Export buildings as images: https://overpass-turbo.eu/
   - Use OSM data with rendering tools

3. **Historic Preservation Archives**
   - Library of Congress: https://www.loc.gov/
   - University archives: Check local universities
   - Search: "historic floor plans"

4. **Real Estate Websites**
   - Zillow, Redfin, Airbnb (screenshot listing images)
   - Home renovation sites (Pinterest, Houzz)
   - Property management sites

### Option B: Scan Physical Plans

Use a scanner or phone camera:
```bash
# If using image files directly
python pdf_to_images.py \
  --input-dir raw_scans/ \
  --output-dir dataset/real_data/images \
  --dpi 300
```

### Option C: Convert CAD Plans

If you have .dwg or .dxf files:
```bash
# Use LibreCAD or Inkscape to export as PNG
# Then process with pdf_to_images.py equivalently
```

### Organize Real Data
```bash
dataset/
├── real_data/
│   ├── images/         ← Download screenshots here
│   └── unlabeled.txt   ← List of files to annotate
```

---

## Phase 3: Annotate with LabelMe (8-12 hours for 200 samples)

### Install LabelMe
```bash
pip install labelme
```

### Annotate Images
```bash
# Start annotation GUI
labelme dataset/real_data/images --output-file annotations.json

# Keyboard shortcuts:
# - Space: Draw polygon
# - Enter: Finish shape
# - Delete: Remove last point
# - D: Toggle polygon display
# - Ctrl+Z: Undo
```

### Tips for Faster Annotation:
- **Template Mode**: Save common room shapes as templates
- **Batch Similar Plans**: Group similar-looking plans together
- **Draw Quickly**: You don't need perfect accuracy (85%+ is fine)
- **Second Pass**: Review annotations for quality
- **Take Breaks**: Annotation is tedious; 50 samples/hour is realistic

### Expected Time:
- Simple plans: 5-10 seconds/image
- Complex plans: 30-60 seconds/image
- 100 plans: 1-2 hours
- 200 plans: 3-5 hours

### Convert Annotations to Masks
```bash
python labelme_to_masks.py \
  --images dataset/real_data/images \
  --annotations annotations.json \
  --output dataset/real_data/masks
```

---

## Phase 4: Combine & Train on Mixed Data (2-4 hours)

### Merge Synthetic + Real Data
```bash
# Copy synthetic data
cp -r dataset/synthetic/train/* dataset/combined/train/
cp -r dataset/synthetic/val/* dataset/combined/val/

# Add real data to training (80/20 split)
# Real: 160 → train, 40 → val
mkdir -p dataset/combined/train/{images,masks}
mkdir -p dataset/combined/val/{images,masks}

# Copy real training data
cp dataset/real_data/images/*.png dataset/combined/train/images/
cp dataset/real_data/masks/*.png dataset/combined/train/masks/

# Split validation
# Move 40 random images to val/
```

### Train on Combined Dataset
```bash
# Standard training
python train_advanced.py \
  --data dataset/combined \
  --epochs 100 \
  --bs 16 \
  --augment-level high \
  --encoder resnet34 \
  --lr 5e-5 \
  --checkpoint model_combined.pth \
  --mixup \
  --cutmix

# If limited VRAM, use smaller batch size
python train_advanced.py \
  --data dataset/combined \
  --epochs 100 \
  --bs 8 \
  --augment-level high \
  --checkpoint model_combined.pth
```

**Expected Results:**
- ✅ Train loss: ~0.10
- ✅ Val loss: ~0.15-0.20
- ✅ Works on real, messy PDFs

---

## Phase 5: Validate & Improve (2-3 hours)

### Test on Different Document Types

Create test set with different domains:
```bash
dataset/test/
├── residential/     ← Apartments, houses
├── commercial/      ← Offices, stores
├── historic/        ← Old plans, degraded
└── messy/          ← Poor scans, artifacts
```

### Evaluate Performance
```bash
# Generate predictions on test set
python evaluate_model.py \
  --model model_combined.pth \
  --test-dir dataset/test \
  --output results/predictions
```

### Find Hard Examples
```python
# Pseudocode: Find predictions with low confidence
for image in test_set:
    pred = model(image)
    if pred.confidence < 0.7:
        hard_examples.append(image)

# Manually check these
# Add top-50 to training set for retraining
```

### Retrain with Hard Examples
```bash
# Add 50 hard examples to training set
# Retrain for 20-30 epochs
python train_advanced.py \
  --data dataset/combined \
  --epochs 30 \
  --checkpoint model_v2.pth
```

---

## Recommended Timeline

### Week 1:
- Day 1: Generate 500 synthetic samples
- Day 2: Train on synthetic data (model_v1.pth)
- Day 3-4: Collect 200 real floorplans
- Day 5-7: Annotate 100 real samples

### Week 2:
- Day 1-2: Annotate remaining 100 samples
- Day 3-4: Combine datasets + retrain
- Day 5-7: Evaluate and collect hard examples

### Result:
- ✅ Robust model working on diverse documents
- ✅ 600+ total training samples
- ✅ ~20 hours human effort
- ✅ Production-ready system

---

## Configuration Recommendations

### Balanced Setup (Recommended)
```bash
# 300 synthetic + 200 real = 500 total
python generate_synthetic_dataset.py --count 300
# + 200 annotated real samples
python train_advanced.py \
  --data dataset/combined \
  --epochs 50 \
  --bs 16 \
  --augment-level medium \
  --checkpoint model.pth
```

### High-Accuracy Setup (If you have time)
```bash
# 500 synthetic + 500 real = 1000 total
python generate_synthetic_dataset.py --count 500
# + 500 annotated real samples
python train_advanced.py \
  --data dataset/combined \
  --epochs 100 \
  --bs 8 \
  --augment-level high \
  --encoder efficientnet-b3 \
  --checkpoint model_best.pth \
  --mixup --cutmix
```

### Quick Prototype (If time-limited)
```bash
# 200 synthetic only
python generate_synthetic_dataset.py --count 200
python train_advanced.py \
  --data dataset/synthetic \
  --epochs 20 \
  --bs 8 \
  --checkpoint model_quick.pth
```

---

## Copying Best Model to Application

After training completes:

```bash
# Copy trained model
cp model.pth .

# Enable in web UI:
# 1. Open http://127.0.0.1:5000/
# 2. Check "Use ML segmentation" box
# 3. Upload PDF to test

# Or set in .env:
echo "ML_MODEL_PATH=model.pth" >> .env
echo "ML_INFERENCE_DEVICE=cpu" >> .env
echo "ML_THRESHOLD=0.5" >> .env
```

---

## Troubleshooting

### Issue: Memory Error on GPU
```bash
# Reduce batch size
python train_advanced.py \
  --data dataset/combined \
  --bs 4 \
  --checkpoint model.pth
```

### Issue: Training too slow
```bash
# Use smaller model
python train_advanced.py \
  --data dataset/combined \
  --encoder resnet34 \
  --size 384 \
  --checkpoint model.pth
```

### Issue: Model not improving
```bash
# Use higher augmentation + learning rate decay
python train_advanced.py \
  --data dataset/combined \
  --augment-level high \
  --lr 1e-4 \
  --epochs 100 \
  --checkpoint model.pth
```

### Issue: Works on synthetic, fails on real
```bash
# Train more epochs on combined data
python train_advanced.py \
  --data dataset/combined \
  --epochs 100 \
  --augment-level high \
  --checkpoint model.pth
```

---

## Next Steps

1. **Run Phase 1**: Generate synthetic data and train
2. **Test**: Try the model on your own PDFs
3. **Run Phase 2**: Collect 100-200 real samples
4. **Run Phase 3**: Annotate using LabelMe
5. **Run Phase 4**: Retrain on mixed dataset
6. **Evaluate**: Test on different document types
7. **Deploy**: Copy model.pth to project and use

---

## Files Created

- ✅ `generate_synthetic_dataset.py` - Synthetic data generator
- ✅ `train_advanced.py` - Advanced training with augmentation
- ✅ `DATA_GATHERING_GUIDE.md` - Comprehensive reference
- ✅ `QUICK_START.md` - This file
- ✅ All existing scripts still work (train_segmentation.py, etc.)

**Ready to build a robust model? Start with Phase 1! 🚀**
