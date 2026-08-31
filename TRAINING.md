# Training floorplan segmentation

Dataset format

Place your dataset under a root folder, with `train` and `val` subfolders, each containing `images/` and `masks/`:

```
dataset/
  train/
    images/
      img001.png
    masks/
      img001.png   # single-channel mask: 255 for room, 0 elsewhere
  val/
    images/
    masks/
```

Masks must align with images and be binary (0/255). Filenames should match between images and masks.

Training

Install requirements (see `requirements.txt`) and then run:

```bash
python train_segmentation.py --data /path/to/dataset --epochs 30 --bs 8 --checkpoint model.pth
```

This will write `model.pth` (state_dict) in the current directory. Copy that file into the project root and enable "Use ML segmentation" in the web UI to try it.

Tips

- Start with `512x512` images for faster training. Adjust transforms in `train_segmentation.py`.
- If you have few samples, use heavy augmentation (rotations, flips, elastic transforms).
- If `segmentation-models-pytorch` isn't available, you can adapt the script to plain torchvision models, but SMP provides convenient losses and metrics.

Preparing training data from PDFs and LabelMe

- Convert PDF pages to images for annotation using `pdf_to_images.py`:

```bash
python pdf_to_images.py --input-dir path/to/pdfs --output-dir dataset/images --dpi 300
```

- Annotate images with LabelMe (or VIA) and save JSON annotations.

- Convert LabelMe JSONs to binary mask PNGs with `labelme_to_masks.py`:

```bash
python labelme_to_masks.py --images dataset/images --annotations labelme_json --output dataset/masks
```

Now organize the `dataset/` folder as described earlier and run `train_segmentation.py`.
