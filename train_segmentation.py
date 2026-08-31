import os
import argparse
import torch
from torch.utils.data import DataLoader
import segmentation_models_pytorch as smp
import albumentations as A
from albumentations.pytorch import ToTensorV2
from ml_dataset import FloorplanDataset
import numpy as np


def get_transforms(split='train'):
    if split == 'train':
        return A.Compose([
            A.Resize(512, 512),
            A.HorizontalFlip(p=0.5),
            A.VerticalFlip(p=0.5),
            A.RandomRotate90(p=0.5),
        ])
    else:
        return A.Compose([A.Resize(512, 512)])


def train(args):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = smp.Unet(encoder_name='resnet34', encoder_weights='imagenet', in_channels=3, classes=1)
    model.to(device)

    loss_fn = smp.losses.DiceLoss(mode='binary') + torch.nn.BCEWithLogitsLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    train_ds = FloorplanDataset(os.path.join(args.data, 'train', 'images'), os.path.join(args.data, 'train', 'masks'), transform=get_transforms('train'))
    val_ds = FloorplanDataset(os.path.join(args.data, 'val', 'images'), os.path.join(args.data, 'val', 'masks'), transform=get_transforms('val'))

    train_loader = DataLoader(train_ds, batch_size=args.bs, shuffle=True, num_workers=4)
    val_loader = DataLoader(val_ds, batch_size=args.bs, shuffle=False, num_workers=2)

    best_loss = 1e9
    for epoch in range(args.epochs):
        model.train()
        running = 0.0
        for imgs, masks in train_loader:
            imgs = torch.tensor(imgs, dtype=torch.float32).to(device)
            masks = torch.tensor(masks, dtype=torch.float32).to(device)
            preds = model(imgs)
            loss = loss_fn(preds, masks)
            optimizer.zero_grad(); loss.backward(); optimizer.step()
            running += loss.item()
        avg_train = running / len(train_loader)

        # validation
        model.eval()
        running_val = 0.0
        with torch.no_grad():
            for imgs, masks in val_loader:
                imgs = torch.tensor(imgs, dtype=torch.float32).to(device)
                masks = torch.tensor(masks, dtype=torch.float32).to(device)
                preds = model(imgs)
                loss = loss_fn(preds, masks)
                running_val += loss.item()
        avg_val = running_val / len(val_loader)
        print(f'Epoch {epoch+1}/{args.epochs} train_loss={avg_train:.4f} val_loss={avg_val:.4f}')
        if avg_val < best_loss:
            best_loss = avg_val
            torch.save(model.state_dict(), args.checkpoint)
            print('Saved best model to', args.checkpoint)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--data', required=True, help='dataset root with train/val subfolders')
    p.add_argument('--epochs', type=int, default=30)
    p.add_argument('--bs', type=int, default=8)
    p.add_argument('--lr', type=float, default=1e-4)
    p.add_argument('--checkpoint', default='model.pth')
    args = p.parse_args()
    train(args)
