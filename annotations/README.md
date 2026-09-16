# Annotation workflow for current PDFs

This folder was prepared for annotation from the current PDF-derived images.

## Current structure

- `annotations/images/` - copied page images from the prepared dataset
- `annotations/labelme_json/` - where LabelMe JSON files should be saved
- `annotations/masks/` - output mask PNGs generated from LabelMe JSON

## Project-specific room annotation rules

For this floorplan project, the target is to label room regions, not every visual object in the drawing.

### Label only these objects
- Interior room area boundaries
- Main room spaces such as living, bedroom, kitchen, dining, corridor, bathroom, utility, etc.
- Closed room polygons with filled area inside the walls

### Ignore these objects
- Wall thickness or outlines outside the actual room area
- Dimension lines and text annotations
- Door swings, window lines, symbols, furniture, fixtures, labels, and grids
- Exterior border/frame around the plan
- Small noisy artifacts and tiny blobs

### Labeling standard
- One polygon = one room
- The polygon should be drawn tightly around the room interior
- Keep the polygon closed and filled
- Do not include wall thickness
- If a room is a large open area, annotate the whole interior region as one room
- If a room is split by a visible wall, it should usually be treated as a separate room

### Recommended labels
Use simple, consistent labels such as:
- `living_area`
- `bedroom`
- `kitchen`
- `dining`
- `bathroom`
- `corridor`
- `utility`
- `store`

### Material mapping used by the exporter

Use these labels exactly when the material matters:

| Material | Labels |
| --- | --- |
| Carpet | `living_area`, `carpet_area_room`, `bedroom`, `living_room`, `dining`, `study`, `master_bedroom`, `guest_room` |
| Hardflooring | `kitchen`, `bathroom`, `toilet`, `laundry`, `utility`, `wet_area`, `balcony`, `store`, `stairs`, `service` |

The exporter treats any unlisted label as carpet unless its name contains a wet or service-area term. Use `--carpet-labels` or `--hardfloor-labels` to override the defaults for a particular project.

For your current focus, a simple rule is also acceptable:
- `living_area`
- `carpet_area_room`
- `wet_area`

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
2. Draw polygons around each room interior
3. Name each polygon with the room label
4. Save the file after finishing each image

LabelMe will create one JSON file per image in the same folder or in the configured output folder, depending on your setup.

## 2) Export JSON files into the labelme_json folder

Move or copy the generated JSON files into:

```text
annotations/labelme_json/
```

Important:
- each JSON file must have the same base name as the corresponding image
- for example: `FP1_page1.png` should match `FP1_page1.json`

## 3) Convert LabelMe JSON into binary masks

Once the JSON files are in `annotations/labelme_json/`, run:

```bash
python labelme_to_masks.py --images annotations/images --annotations annotations/labelme_json --output annotations/masks
```

This will create one mask PNG per image in `annotations/masks/`.

## 4) Build a train/val dataset from the new masks

After the masks exist, rebuild the prepared dataset with real masks:

```bash
python prepare_floorplan_dataset.py --input-dir Dataset --output-dir prepared_dataset --annotations annotations/labelme_json --val-ratio 0.2 --dpi 200
```

If you want the script to also generate placeholder masks for any missing annotation files, add `--blank-masks`.

## 5) Train the U-Net

Once the masks are real and aligned with the images, run:

```bash
python u_net_for_training_floor_plan_2_pdf.py --data prepared_dataset --epochs 50 --bs 8
```

## Recommended workflow for your project

1. Start with 2-3 floorplans only
2. Label all room polygons carefully
3. Review the generated masks visually
4. Fix any mislabeled thin borders or tiny noise spots
5. Then expand to the rest of the PDFs

## Notes

- The current dataset had blank masks only, so no real rooms were available for training.
- The images in `annotations/images/` are already copied and ready for labeling.
- The conversion script expects masks to be grayscale PNGs where room pixels are `255` and background is `0`.
- Keep the dataset clean before training; quality beats quantity in this task.
