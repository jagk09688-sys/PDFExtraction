import os
from torch.utils.data import Dataset
import cv2
import numpy as np


class FloorplanDataset(Dataset):
    """Expect directory structure:
    dataset/
      images/
        img1.png
      masks/
        img1.png   # single-channel mask: 255 where room, 0 elsewhere
    """
    def __init__(self, images_dir, masks_dir, transform=None, allowed_files=None):
        self.images_dir = images_dir
        self.masks_dir = masks_dir
        self.transform = transform

        if not os.path.isdir(images_dir):
            raise FileNotFoundError(f"Images directory not found: {images_dir}")
        if not os.path.isdir(masks_dir):
            raise FileNotFoundError(f"Masks directory not found: {masks_dir}")

        if allowed_files is not None:
            allowed_set = set(allowed_files)
            self.ids = [
                f for f in os.listdir(images_dir)
                if os.path.isfile(os.path.join(images_dir, f)) and f in allowed_set
            ]
        else:
            self.ids = [
                f for f in os.listdir(images_dir)
                if os.path.isfile(os.path.join(images_dir, f))
            ]

        self.ids = sorted(self.ids)

    def __len__(self):
        return len(self.ids)

    def __getitem__(self, idx):
        fn = self.ids[idx]
        img_path = os.path.join(self.images_dir, fn)
        mask_path = os.path.join(self.masks_dir, fn)

        img = cv2.imread(img_path)
        if img is None:
            raise FileNotFoundError(f"Could not read image file: {img_path}")
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
        if mask is None:
            raise FileNotFoundError(f"Could not read mask file: {mask_path}")

        if img.shape[:2] != mask.shape[:2]:
            mask = cv2.resize(mask, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST)

        if self.transform:
            augmented = self.transform(image=img, mask=mask)
            img = augmented['image']
            mask = augmented['mask']

        # normalize image to 0-1 and transpose to CHW
        img = img.astype('float32') / 255.0
        img = np.transpose(img, (2, 0, 1))
        mask = (mask.astype('float32') / 255.0)[None, ...]
        return img, mask
