# Commercial Carpet Floor Plan Installer Worksheet

Complete one copy of this worksheet for each floor-plan project. Use the same
`project_id` as the project folder. Do not estimate values that the installer
cannot confirm; write `Unknown` and add a note instead.

## 1. Project Details

| Field | Response |
|---|---|
| Project ID |  |
| Customer / site |  |
| Site address |  |
| Contact person |  |
| Installer / company |  |
| Installer contact |  |
| Date surveyed |  |
| Date installed |  |
| Floor-plan PDF |  |
| Plan revision / version |  |
| Annotator |  |
| Units used | metres / millimetres / feet / other: |
| General site notes |  |

## 2. Plan Review

| Field | Response |
|---|---|
| Number of PDF pages |  |
| Pages installed |  |
| Pages not installed and reason |  |
| Scale verified? | Yes / No |
| Pixels per metre, if known |  |
| Scale reference used |  |
| Existing floor removed? | Yes / No / Partial |
| Subfloor condition |  |
| Moisture or level issues |  |
| Access, stairs, lift, parking notes |  |

## 3. Room Register

Use one row per room or separately numbered area. Room IDs must match the
annotation JSON, for example `P01-R01`.

| Room ID | Page | Room label / number | Material | Length (m) | Width (m) | Area (m2) | Carpet required (LM) | Notes |
|---|---:|---|---|---:|---:|---:|---:|---|
| P01-R01 | 1 |  | Carpet / hard floor / other |  |  |  |  |  |
| P01-R02 | 1 |  | Carpet / hard floor / other |  |  |  |  |  |
| P02-R01 | 2 |  | Carpet / hard floor / other |  |  |  |  |  |

## 4. Carpet Product and Roll Plan

| Field | Response |
|---|---|
| Product / colour |  |
| Manufacturer |  |
| Batch / dye lot |  |
| Carpet width (m) |  |
| Roll width (m) |  |
| Pattern repeat |  |
| Pattern match required? | Yes / No |
| Pile direction required? | Yes / No |
| Direction notes |  |

| Roll ID | Source roll / batch | Length available (LM) | Length allocated (LM) | Rooms served | Remaining offcut (LM) |
|---|---|---:|---:|---|---:|
| R01 |  |  |  |  |  |
| R02 |  |  |  |  |  |
| R03 |  |  |  |  |  |

## 5. Join Schedule

Record every join, including joins that were moved on site.

| Join ID | Room ID | Page | Join location / description | Planned position | Actual position | Reason moved | Visible / accepted? |
|---|---|---:|---|---|---|---|---|
| J01 |  |  |  |  |  |  |  |
| J02 |  |  |  |  |  |  |  |

Attach a marked-up plan or photo for locations that cannot be described clearly.

## 6. Cutting and Offcut Reuse

| Offcut ID | Source roll | Size / length | Usable? | Reused for room / area | Reuse decision | Reason not reused |
|---|---|---|---|---|---|---|
| O01 |  |  | Yes / No |  | Used / discarded / reserved |  |
| O02 |  |  | Yes / No |  | Used / discarded / reserved |  |

## 7. Quantity and Waste Outcome

| Field | Response |
|---|---:|
| Total measured carpet area (m2) |  |
| Total carpet ordered (LM) |  |
| Total carpet installed (LM) |  |
| Waste / offcut produced (LM) |  |
| Waste percentage |  |
| Waste percentage formula used | `(ordered - installed) / ordered * 100` |
| Reusable offcut total (LM) |  |
| Material shortage? | Yes / No |
| Extra material ordered? | Yes / No; amount: |
| Final quantity notes |  |

## 8. Installer Feedback

| Question | Response |
|---|---|
| Were the room dimensions usable? | Yes / No; details: |
| Were the planned joins practical? | Yes / No; details: |
| Which join locations should change next time? |  |
| Which rooms were difficult to cut or install? |  |
| What caused extra waste? |  |
| Which offcuts could have been reused? |  |
| Did the plan omit any site condition? |  |
| What should the AI estimator learn from this project? |  |
| Installer confidence in final layout | 1 / 2 / 3 / 4 / 5 |
| Installer sign-off name |  |
| Sign-off date |  |

## 9. Attachments Checklist

- [ ] Original floor-plan PDF
- [ ] Annotated room plan
- [ ] Dimension / OCR review
- [ ] Final carpet layout or cutting plan
- [ ] Join-marked plan
- [ ] Site photos
- [ ] Delivery docket or roll details
- [ ] Installer sign-off
- [ ] Corrections or revised plan

## 10. Dataset Completion

| Field | Response |
|---|---|
| Metadata JSON updated | Yes / No |
| Official page annotations validated | Yes / No |
| Room masks regenerated | Yes / No |
| Project status | collected / annotated / reviewed / estimated / installed / verified |
| Reviewer |  |
| Review date |  |
| Remaining actions |  |
