# Data Gathering & Augmentation Guide

Strategies to make your room detection model more robust with diverse, high-quality training data.

---

## 1. **Synthetic Data Generation (Fast & Free)**

### Expand `sample_data.py` with Variations

Generate diverse floorplan layouts programmatically:

```bash
python generate_synthetic_dataset.py --count 500 --output dataset/synthetic
```

**Creates:**
- Various room shapes (rectangles, L-shapes, polygons)
- Different wall thicknesses
- Multiple room counts per floorplan
- Various wall colors and materials
- Doors and windows with different styles
- Furniture outlines
- Scale variations (small apartments → large offices)

### Recommended Features:
- ✅ **Room shapes**: rectangles, L-shapes, T-shapes, trapezoids, curves
- ✅ **Wall styles**: thin (2px), thick (8px), double walls
- ✅ **Wall colors**: black, dark gray, light gray, colored
- ✅ **Doors/Windows**: single swing, double swing, sliding, casement
- ✅ **Room labels**: text annotations with room names
- ✅ **Dimensions**: varied image sizes (512x512, 768x768, 1024x1024)
- ✅ **Clutter**: furniture, closets, fixtures within rooms

---

## 2. **Real-World Data Collection**

### Sources for Real Floorplans:

#### A. **Free Online Databases**
| Source | URL | Count | License |
|--------|-----|-------|---------|
| OpenStreetMap Buildings | https://www.openstreetmap.org/ | 1M+ | ODbL |
| WikiArch Floorplans | https://commons.wikimedia.org/ | 10K+ | CC |
| Archivision | https://archivision.com | 50K+ | Commercial |
| The Eames Office | https://eamesoffice.com | 1K+ | CC |
| Historic Plans Archive | Various universities | 50K+ | Public |

#### B. **Collection Strategy**
1. **Screenshot PDFs**: Save blueprints as high-res images (300+ DPI)
2. **Photo Scanning**: Use phone camera app for physical plans
3. **CAD Conversion**: Download .dwg files and render to PNG
4. **Real Estate**: Scrape Zillow, Redfin, Airbnb listing images

#### C. **Data Cleanup**
```bash
# Convert varied formats to standard PNG
python convert_floorplans.py --input raw_pdfs --output standardized --dpi 300
```

---

## 3. **Annotation Workflow (LabelMe)**

### Setup LabelMe
```bash
pip install labelImg
# or web-based: pip install labelme
labelme --output-file annotations.json --imagedir dataset/raw_images
```

### Efficient Annotation:
1. **Keyboard shortcuts**: Space to draw, Enter to confirm
2. **Pre-draw templates**: Save common shapes as templates
3. **Batch processing**: Annotate similar-looking plans together
4. **Quality review**: Second-pass check for accuracy

### Expected effort:
- 5-10 seconds per simple floorplan
- 30-60 seconds per complex floorplan
- 100 plans ≈ 1-2 hours with practice

---

## 4. **Advanced Data Augmentation**

### Upgrade Augmentation Pipeline

Replace basic transforms with advanced ones:

```python
# Add to train_segmentation.py
advanced_transforms = A.Compose([
    # Geometric
    A.HorizontalFlip(p=0.5),
    A.VerticalFlip(p=0.5),
    A.Rotate(limit=45, p=0.5),
    A.ElasticTransform(p=0.3),
    A.GridDistortion(p=0.3),
    
    # Perspective
    A.Perspective(scale=(0.05, 0.1), p=0.5),
    A.Affine(shear=(-15, 15), p=0.5),
    
    # Optical
    A.GaussNoise(p=0.2),
    A.GaussianBlur(blur_limit=3, p=0.2),
    A.MotionBlur(blur_limit=3, p=0.2),
    
    # Intensity
    A.RandomBrightnessContrast(p=0.5),
    A.RandomGamma(p=0.2),
    A.CLAHE(p=0.2),
    
    # Texture
    A.CoarseDropout(max_holes=8, max_height=8, max_width=8, p=0.3),
    
    # Resize to target
    A.Resize(512, 512),
    ToTensorV2()
])
```

### Why these help:
- **Geometric**: Handles scanned/rotated documents
- **Perspective**: Handles camera angles from photos
- **Noise**: Handles scanner artifacts
- **Brightness**: Handles lighting variations
- **Texture**: Handles paper degradation

---

## 5. **Mixup & CutMix Strategies**

### Combine samples for better generalization:

```python
def mixup_augment(img1, mask1, img2, mask2, alpha=0.6):
    """Blend two samples together"""
    weight = np.random.beta(alpha, alpha)
    img_mix = (weight * img1 + (1 - weight) * img2).astype(np.uint8)
    mask_mix = (weight * mask1 + (1 - weight) * mask2).astype(np.uint8)
    return img_mix, mask_mix
```

**Benefits:**
- ✅ Trains on intermediate cases
- ✅ Better generalization
- ✅ Smoother decision boundaries

---

## 6. **Transfer Learning & Few-Shot**

### Use Pre-trained Models

Instead of training from scratch:

```python
# Use ImageNet pre-trained ResNet34
model = smp.Unet(
    encoder_name='resnet34',
    encoder_weights='imagenet',  # ← Use this!
    in_channels=3,
    classes=1
)
```

**Benefits:**
- ✅ Works well with 50-100 samples
- ✅ Faster convergence
- ✅ Better edge detection

### Try Different Encoders:
```python
encoders = ['resnet34', 'efficientnet-b1', 'timm-densenet121', 'se_resnext50_32x4d']
# Each has different biases useful for building/room detection
```

---

## 7. **Active Learning Loop**

### Strategy: Improve iteratively

```python
# Pseudo-code
for iteration in range(10):
    # Train current model
    train_model(model, current_dataset)
    
    # Find hard examples
    hard_samples = find_low_confidence(model, unlabeled_data)
    
    # Annotate only hard samples
    new_annotations = annotate_samples(hard_samples[:50])
    
    # Add to training set
    current_dataset.update(new_annotations)
```

**Why it works:**
- Focus annotation effort on challenging cases
- 50 well-chosen samples > 500 random ones
- Reduces annotation burden

---

## 8. **Cross-Domain Data**

### Diversify floor sources:

| Domain | Characteristics | Collection Method |
|--------|-----------------|-------------------|
| **Residential** | Varied shapes, many rooms | Real estate websites |
| **Commercial** | Grid-like, large open spaces | Architectural databases |
| **Historic** | Ornate, irregular | Library archives |
| **Minimal** | Simple lines, clean | CAD software |
| **Hand-drawn** | Rough, informal | User sketches |

**Collect from each domain:**
- 100-200 samples per category
- Mix during training
- Test on each domain separately

---

## 9. **Recommended Dataset Sizes**

| Scenario | Required Samples | Annotation Time |
|----------|------------------|-----------------|
| **Proof of Concept** | 50 (20 synthetic) | 1-2 hours |
| **Prototype** | 200 (100 synthetic) | 4-6 hours |
| **Production Ready** | 500+ (200 synthetic) | 12-18 hours |
| **Robust System** | 1000+ (300 synthetic) | 30-40 hours |

---

## 10. **Quick-Start Data Workflow**

### Month 1: Bootstrap Phase
```bash
# Week 1: Generate synthetic data
python generate_synthetic_dataset.py --count 300

# Week 2: Collect 100 real samples
# - Download from archives
# - Screenshot from websites
# - Scan paper documents

# Week 3: Annotate in LabelMe
labelme --output-file annotations.json dataset/

# Week 4: Train and evaluate
python train_segmentation.py --data dataset --epochs 50
```

### Month 2-3: Refinement Phase
- Find hard examples with model
- Annotate 50-100 new hard samples
- Retrain with full dataset
- Evaluate on different domains

---

## 11. **Implementation: Better Synthetic Generator**

I'll create an improved version with these features:

```bash
# Generate 1000 varied synthetic floorplans
python generate_synthetic_dataset.py \
  --count 1000 \
  --output dataset/synthetic \
  --variation-level high \
  --room-shapes mixed \
  --wall-styles varied \
  --seed 42
```

Would you like me to create this enhanced generator?

---

## 12. **Quality Metrics to Track**

Monitor your data quality:

```python
# Check dataset statistics
print(f"Train: {len(train_ds)} samples")
print(f"Val: {len(val_ds)} samples")
print(f"Rooms per image: {avg_rooms_per_image}")
print(f"Room area range: {min_area} - {max_area}")
print(f"Image size distribution: {size_distribution}")
```

---

## 13. **Recommended Next Steps**

**Priority 1 (Do First):**
- ✅ Generate 500 synthetic samples with variations
- ✅ Collect 100-200 real floorplans from online sources
- ✅ Annotate them using LabelMe

**Priority 2 (Do Second):**
- ✅ Improve augmentation pipeline (add elastic transforms, perspective)
- ✅ Train model with transfer learning
- ✅ Evaluate performance per domain

**Priority 3 (For Production):**
- ✅ Implement active learning loop
- ✅ Collect domain-specific hard cases
- ✅ Ensemble multiple models

---

## Resources

- **LabelMe**: https://github.com/wkentaro/labelme
- **Albumentations Docs**: https://albumentations.ai/
- **Segmentation Models**: https://smp.readthedocs.io/
- **OpenStreetMap**: https://www.openstreetmap.org/
- **Wikimedia Commons**: https://commons.wikimedia.org/

