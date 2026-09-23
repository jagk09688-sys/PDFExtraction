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

## Required collection workflow

1. Keep the original PDF in the project record.
2. Open each `pages/page_###.png` in LabelMe. Save room polygons with labels
   such as `Bed 1`, `Hallway`, `Living`, or `Balcony`. Keep the LabelMe JSON as
   a temporary authoring file if desired.
3. Complete the official `annotations/page_###.json` template. Add every room,
   OCR dimension, structural element, and Dunlop table row using the standard
   schema in `annotation_schema.json`.
4. Validate the completed page annotations:

   ```powershell
   python validate_annotations.py commercial_dataset/projects/CW-0001/annotations
   ```

5. Convert reviewed room polygons to masks only after checking the polygons:

    ```powershell
    python official_annotations_to_masks.py `
       commercial_dataset/projects/CW-0001/annotations `
       commercial_dataset/projects/CW-0001/masks
    ```
4. Fill `metadata.json` with room dimensions, material, roll width, linear metres
   ordered, waste percentage, join positions, and offcut reuse decisions.
5. Put the final carpet layout or marked-up plan in `final_layouts/`.
6. Add installer feedback after installation and update the project status.

## Annotation rules

- Coordinates are pixel coordinates in the original rendered page image.
- Room polygons are mandatory and should tightly follow the room interior.
- Record dimension text exactly as printed, plus numeric value and bounding box.
- Annotate doors, windows, walls, stairs, arrows, and notes with bounding boxes;
   walls also require polygons.
- Add `table_rows` for Dunlop sheets such as FP2 and FP3.
- Do not guess OCR values, room dimensions, joins, waste, or installer outcomes.

Unknown values must remain `null` or empty. Do not guess measurements, waste,
joins, or ordered length. That distinction is essential for reliable quantity
and waste prediction.

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

## Recommended statuses

`collected`, `annotated`, `reviewed`, `estimated`, `installed`, `verified`.

The strategy milestones are 50 projects for rule validation, 100-200 for an
OCR/extraction prototype, 500 for model training, and 1000-2000 for commercial
optimisation. Keep validation projects separate from training projects when
those milestones are reached.