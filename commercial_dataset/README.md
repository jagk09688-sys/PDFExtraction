# Commercial Carpet Dataset

This dataset follows `Commercial_Carpet_AI_Master_Strategy.docx`. One project
is the unit of record. Do not overwrite `original.pdf`; all derived files live
beside it.

## Project layout

```text
commercial_dataset/
  projects.csv
  projects/
    CW-0001/
      original.pdf
      metadata.json
      pages/page_001.png
      annotations/page_001.json
      masks/*.png
      final_layouts/
```

Create a project from a new PDF:

```powershell
python create_project_dataset.py --pdf "path\to\plan.pdf" --project-id CW-0001
```

Import a folder of new PDFs. Identical duplicate files are skipped and existing
project folders are preserved:

```powershell
python ingest_dataset_folder.py --input-dir Dataset --dpi 300
```

## Official annotation workflow

1. Keep the original PDF and use the rendered `pages/page_###.png` files.
2. Open each page in LabelMe, CVAT, or Roboflow. Keep coordinates in original
   pixel space.
3. Draw one tight polygon around every room interior and label it, such as
   `Bed 1`, `Hallway`, `Living`, or `Balcony`.
4. Draw a bounding box around every printed dimension. Record exact text,
   numeric value, room association when known, and `length`, `width`, or
   `unknown` type.
5. Draw bounding boxes around room names and symbols in `text_labels`. Use
   `room_name`, `symbol`, or `note` as the type.
6. Annotate doors, windows, walls, stairs, arrows, notes, and symbols such as
   `DP`, `AJ`, and `FR`. Structures need a bounding box; walls also need a
   polygon.
7. For FP2/FP3-style Dunlop sheets, record every table row with room number,
   length, width, notes, and row bounding box.
8. Complete `annotations/page_###.json` using `annotation_schema.json`.
9. Validate the completed annotations:

   ```powershell
   python validate_annotations.py commercial_dataset/projects/CW-0001/annotations
   ```

10. Convert reviewed room polygons to masks:

    ```powershell
    python official_annotations_to_masks.py `
       commercial_dataset/projects/CW-0001/annotations `
       commercial_dataset/projects/CW-0001/masks
    ```

11. Fill `metadata.json` with room dimensions, material, roll width, linear
    metres ordered, waste percentage, join positions, and offcut decisions.
12. Put the final carpet layout or marked-up plan in `final_layouts/`.
13. Add installer feedback after installation and update the project status.

## Annotation rules

- Coordinates are pixel coordinates in the original rendered page image.
- Room polygons are mandatory and should tightly follow the room interior.
- Record dimension text exactly as printed, plus numeric value and bounding box.
- Record room names and symbols in `text_labels` with bounding boxes.
- Annotate doors, windows, walls, stairs, arrows, notes, `DP`, `AJ`, and `FR`
   with bounding boxes; walls also require polygons.
- Add `table_rows` for Dunlop sheets such as FP2 and FP3.
- Do not guess OCR values, room dimensions, joins, waste, or installer outcomes.

Unknown values must remain `null` or empty. Do not guess measurements, waste,
joins, or ordered length. That distinction is essential for reliable quantity
and waste prediction.

## Automatic annotation drafts

To create preliminary room polygons for review:

```powershell
python generate_draft_annotations.py
```

Drafts are written to each project under `annotation_drafts/`. They are not
official labels. Replace `UNREVIEWED_ROOM` with the correct room label, fix or
remove incorrect polygons, and then copy reviewed records into `annotations/`.
Dimensions, structures, table rows, and installer data must be entered from
the actual plan or installer worksheet.

## Installer data collection

Use [INSTALLER_PROJECT_TEMPLATE.md](INSTALLER_PROJECT_TEMPLATE.md) during the
site measure and installation review. It covers project details, every room,
roll allocation, joins, offcuts, waste, attachments, and installer sign-off.

For Excel, open [INSTALLER_PROJECT_TEMPLATE.xlsx](INSTALLER_PROJECT_TEMPLATE.xlsx).
It contains separate tabs for the project summary, rooms, product and rolls,
joins, offcuts, outcome and feedback, and the completion checklist. Enter one
room, roll, join, or offcut per row.

Use [installer_project_template.json](installer_project_template.json) as the
machine-readable version. Copy it into a project as `installer_data.json`,
replace the `CW-0000` ID, and fill confirmed values only:

```powershell
Copy-Item commercial_dataset/installer_project_template.json `
   commercial_dataset/projects/CW-0001/installer_data.json
```

The recommended order is: collect the PDF, annotate the plan, complete the
installer worksheet during the site visit, record the final layout and actual
joins after installation, then transfer the confirmed values into
`installer_data.json` and `metadata.json`.

## Build a polished training set

After official annotations are reviewed, build the training set with:

```powershell
python build_training_dataset.py --dataset-root commercial_dataset
```

This excludes empty templates and automatic drafts, validates page geometry,
creates masks, and splits whole projects rather than pages. The output is
`reviewed_training_dataset/`; inspect `quality_report.json` before training.

## Recommended statuses

`collected`, `annotated`, `reviewed`, `estimated`, `installed`, `verified`.

The strategy milestones are 50 projects for rule validation, 100-200 for an
OCR/extraction prototype, 500 for model training, and 1000-2000 for commercial
optimisation. Keep validation projects separate from training projects when
those milestones are reached.