# Annotation workflow for current PDFs

This folder was prepared for annotation from the current PDF-derived images.

## Current structure

- `annotations/images/` - copied page images from the prepared dataset
- `annotations/labelme_json/` - where LabelMe JSON files should be saved
- `annotations/masks/` - output mask PNGs generated from LabelMe JSON

## 1) Open the images in LabelMe

Install LabelMe if needed:

```bash
pip install labelme
```

Then start LabelMe against the image folder:

```bash
labelme annotations/images
```

In LabelMe:

1. Open each image from `annotations/images/`
2. Draw polygons around each room
3. Name each polygon with the room label (for example: `bedroom`, `living_room`, `bathroom`, `kitchen`)
4. Save the file after finishing each image

LabelMe will create one JSON file per image in the same folder or in the configured output folder, depending on your setup.

## 2) Export JSON files into the labelme_json folder

Move or copy the generated JSON files into:

```text
annotations/labelme_json/
```

Important:
- each JSON file must have the same base name as the corresponding image
- for example: `Floor Plan (2)_page1.png` should match `Floor Plan (2)_page1.json`

## 3) Convert LabelMe JSON into binary masks

Once the JSON files are in `annotations/labelme_json/`, run:

```bash
python labelme_to_masks.py --images annotations/images --annotations annotations/labelme_json --output annotations/masks
```

This will create one mask PNG per image in `annotations/masks/`.

## 4) Build a train/val dataset from the new masks

After the masks exist, rebuild the prepared dataset (or create a new dataset folder):

```bash
python prepare_floorplan_dataset.py --input-dir Dataset --output-dir prepared_dataset --annotations annotations/labelme_json --val-ratio 0.2 --dpi 300
```

If you want the script to also generate placeholder masks for any missing annotation files, add `--blank-masks`.

## 5) Train the U-Net

Once the masks are real and aligned with the images, run:

```bash
python u_net_for_training_floor_plan_2_pdf.py --data prepared_dataset --epochs 50 --bs 8
```

## Notes

- The current dataset had blank masks only, so no real rooms were available for training.
- The images in `annotations/images/` are already copied and ready for labeling.
- The conversion script expects masks to be grayscale PNGs where room pixels are `255` and background is `0`.
