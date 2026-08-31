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
    def __init__(self, images_dir, masks_dir, transform=None):
        self.images_dir = images_dir
        self.masks_dir = masks_dir
        self.ids = [f for f in os.listdir(images_dir) if os.path.isfile(os.path.join(images_dir, f))]
        self.transform = transform

    def __len__(self):
        return len(self.ids)

    def __getitem__(self, idx):
        fn = self.ids[idx]
        img = cv2.imread(os.path.join(self.images_dir, fn))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        mpath = os.path.join(self.masks_dir, fn)
        mask = cv2.imread(mpath, cv2.IMREAD_GRAYSCALE)
        if mask is None:
            mask = np.zeros((img.shape[0], img.shape[1]), dtype=np.uint8)
        if self.transform:
            augmented = self.transform(image=img, mask=mask)
            img = augmented['image']; mask = augmented['mask']
        # normalize image to 0-1 and transpose to CHW
        img = img.astype('float32') / 255.0
        img = np.transpose(img, (2, 0, 1))
        mask = (mask.astype('float32') / 255.0)[None, ...]
        return img, mask
