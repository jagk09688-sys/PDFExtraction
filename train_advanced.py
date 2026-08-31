"""
Advanced training script with enhanced augmentation for robust floorplan segmentation.

Features:
  - Geometric, perspective, and optical augmentations
  - Mixup and CutMix regularization
  - Early stopping and model checkpointing
  - Learning rate scheduling
  - Comprehensive logging

Usage:
    python train_advanced.py --data dataset --epochs 50 --bs 16 --checkpoint model_best.pth
    python train_advanced.py --data dataset --epochs 100 --bs 8 --lr 5e-5 --augment-level high
"""

import os
import argparse
import torch
from torch.utils.data import DataLoader
import segmentation_models_pytorch as smp
import albumentations as A
from albumentations.pytorch import ToTensorV2
from ml_dataset import FloorplanDataset
import numpy as np
from datetime import datetime


def get_augmentation(level='medium', size=512):
    """Get augmentation pipeline with configurable intensity.
    
    Args:
        level: 'low', 'medium', or 'high' augmentation intensity
        size: Target image size
    """
    
    if level == 'low':
        return A.Compose([
            A.Resize(size, size),
            A.HorizontalFlip(p=0.3),
            A.VerticalFlip(p=0.3),
            A.Rotate(limit=30, p=0.3),
            A.RandomBrightnessContrast(p=0.2),
            ToTensorV2()
        ], is_check_shapes=False)
    
    elif level == 'medium':
        return A.Compose([
            # Geometric transformations
            A.Resize(size, size),
            A.HorizontalFlip(p=0.5),
            A.VerticalFlip(p=0.5),
            A.Rotate(limit=45, p=0.5),
            A.ElasticTransform(alpha=1, sigma=50, alpha_affine=50, p=0.3),
            A.GridDistortion(p=0.3),
            
            # Perspective
            A.Perspective(scale=(0.05, 0.1), p=0.3),
            A.Affine(shear=(-15, 15), p=0.3),
            
            # Optical distortions
            A.GaussNoise(p=0.2),
            A.GaussianBlur(blur_limit=3, p=0.2),
            A.MotionBlur(blur_limit=3, p=0.2),
            
            # Brightness/contrast
            A.RandomBrightnessContrast(brightness_limit=0.2, contrast_limit=0.2, p=0.5),
            A.RandomGamma(p=0.2),
            A.CLAHE(p=0.2),
            
            # Dropout
            A.CoarseDropout(max_holes=8, max_height=8, max_width=8, p=0.2),
            
            ToTensorV2()
        ], is_check_shapes=False)
    
    else:  # high
        return A.Compose([
            # Aggressive geometric
            A.Resize(size, size),
            A.HorizontalFlip(p=0.5),
            A.VerticalFlip(p=0.5),
            A.Rotate(limit=60, p=0.7),
            A.ElasticTransform(alpha=2, sigma=100, alpha_affine=100, p=0.5),
            A.GridDistortion(p=0.5),
            A.OpticalDistortion(p=0.5),
            
            # Perspective variations
            A.Perspective(scale=(0.05, 0.15), p=0.5),
            A.Affine(shear=(-20, 20), rotate=(-30, 30), p=0.5),
            
            # Scan-like artifacts
            A.GaussNoise(var_limit=(10.0, 50.0), p=0.4),
            A.GaussianBlur(blur_limit=5, p=0.3),
            A.MotionBlur(blur_limit=5, p=0.3),
            
            # Intensity variations
            A.RandomBrightnessContrast(brightness_limit=0.3, contrast_limit=0.3, p=0.6),
            A.RandomGamma(gamma_limit=(80, 120), p=0.3),
            A.CLAHE(p=0.3),
            A.Posterize(p=0.2),
            
            # Heavy dropout
            A.CoarseDropout(max_holes=16, max_height=16, max_width=16, p=0.4),
            
            ToTensorV2()
        ], is_check_shapes=False)


def get_val_augmentation(size=512):
    """Validation augmentation (minimal)."""
    return A.Compose([
        A.Resize(size, size),
        ToTensorV2()
    ], is_check_shapes=False)


def mixup(images, masks, alpha=1.0):
    """Mixup augmentation: blend two samples."""
    if images.shape[0] < 2:
        return images, masks
    
    batch_size = images.shape[0]
    indices = torch.randperm(batch_size)
    
    weight = np.random.beta(alpha, alpha)
    mixed_images = weight * images + (1 - weight) * images[indices]
    mixed_masks = weight * masks + (1 - weight) * masks[indices]
    
    return mixed_images, mixed_masks


def cutmix(images, masks, alpha=1.0):
    """CutMix augmentation: cut and paste patches."""
    if images.shape[0] < 2:
        return images, masks
    
    batch_size = images.shape[0]
    indices = torch.randperm(batch_size)
    
    weight = np.random.beta(alpha, alpha)
    
    # Random patch coordinates
    _, _, h, w = images.shape
    cut_h = int(h * np.sqrt(1 - weight))
    cut_w = int(w * np.sqrt(1 - weight))
    
    cx = np.random.randint(0, w)
    cy = np.random.randint(0, h)
    
    bbx1 = np.clip(cx - cut_w // 2, 0, w)
    bbx2 = np.clip(cx + cut_w // 2, 0, w)
    bby1 = np.clip(cy - cut_h // 2, 0, h)
    bby2 = np.clip(cy + cut_h // 2, 0, h)
    
    mixed_images = images.clone()
    mixed_masks = masks.clone()
    
    mixed_images[:, :, bby1:bby2, bbx1:bbx2] = images[indices, :, bby1:bby2, bbx1:bbx2]
    mixed_masks[:, :, bby1:bby2, bbx1:bbx2] = masks[indices, :, bby1:bby2, bbx1:bbx2]
    
    return mixed_images, mixed_masks


class EarlyStopping:
    """Stop training if validation loss doesn't improve."""
    
    def __init__(self, patience=10, min_delta=0.001):
        self.patience = patience
        self.min_delta = min_delta
        self.counter = 0
        self.best_loss = None
        self.early_stop = False
    
    def __call__(self, val_loss):
        if self.best_loss is None:
            self.best_loss = val_loss
        elif val_loss < self.best_loss - self.min_delta:
            self.best_loss = val_loss
            self.counter = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.early_stop = True


def train_advanced(args):
    """Train segmentation model with advanced techniques."""
    
    # Device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f'Using device: {device}')
    
    # Model
    print(f'Loading model: {args.encoder}')
    model = smp.Unet(
        encoder_name=args.encoder,
        encoder_weights='imagenet',  # Transfer learning
        in_channels=3,
        classes=1
    )
    model.to(device)
    
    # Loss function
    loss_fn = (
        smp.losses.DiceLoss(mode='binary') + 
        torch.nn.BCEWithLogitsLoss()
    )
    
    # Optimizer with weight decay
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=args.lr,
        weight_decay=1e-4
    )
    
    # Learning rate scheduler
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode='min',
        factor=0.5,
        patience=5,
        verbose=True
    )
    
    # Dataset and dataloaders
    print(f'Loading dataset from {args.data}')
    train_ds = FloorplanDataset(
        os.path.join(args.data, 'train', 'images'),
        os.path.join(args.data, 'train', 'masks'),
        transform=get_augmentation(args.augment_level, args.size)
    )
    val_ds = FloorplanDataset(
        os.path.join(args.data, 'val', 'images'),
        os.path.join(args.data, 'val', 'masks'),
        transform=get_val_augmentation(args.size)
    )
    
    train_loader = DataLoader(
        train_ds,
        batch_size=args.bs,
        shuffle=True,
        num_workers=4,
        pin_memory=True
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=args.bs,
        shuffle=False,
        num_workers=2,
        pin_memory=True
    )
    
    print(f'Train: {len(train_ds)} samples, Val: {len(val_ds)} samples')
    
    # Early stopping
    early_stopping = EarlyStopping(patience=args.patience, min_delta=0.001)
    
    # Training loop
    best_loss = float('inf')
    start_time = datetime.now()
    
    for epoch in range(args.epochs):
        # Training
        model.train()
        train_loss = 0.0
        
        for batch_idx, (imgs, masks) in enumerate(train_loader):
            imgs = imgs.float().to(device)
            masks = masks.float().to(device)
            
            # Apply mixup
            if args.mixup and np.random.random() < 0.5:
                imgs, masks = mixup(imgs, masks, alpha=1.0)
            
            # Apply cutmix
            if args.cutmix and np.random.random() < 0.5:
                imgs, masks = cutmix(imgs, masks, alpha=1.0)
            
            preds = model(imgs)
            loss = loss_fn(preds, masks)
            
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
        
        avg_train_loss = train_loss / len(train_loader)
        
        # Validation
        model.eval()
        val_loss = 0.0
        
        with torch.no_grad():
            for imgs, masks in val_loader:
                imgs = imgs.float().to(device)
                masks = masks.float().to(device)
                preds = model(imgs)
                loss = loss_fn(preds, masks)
                val_loss += loss.item()
        
        avg_val_loss = val_loss / len(val_loader)
        
        # Learning rate scheduling
        scheduler.step(avg_val_loss)
        
        # Logging
        elapsed = (datetime.now() - start_time).total_seconds()
        print(
            f'Epoch {epoch+1:3d}/{args.epochs} | '
            f'train_loss={avg_train_loss:.4f} | '
            f'val_loss={avg_val_loss:.4f} | '
            f'lr={optimizer.param_groups[0]["lr"]:.2e} | '
            f't={int(elapsed)}s'
        )
        
        # Save best model
        if avg_val_loss < best_loss:
            best_loss = avg_val_loss
            torch.save(model.state_dict(), args.checkpoint)
            print(f'  ✓ Saved best model to {args.checkpoint}')
        
        # Early stopping
        early_stopping(avg_val_loss)
        if early_stopping.early_stop:
            print(f'Early stopping at epoch {epoch+1}')
            break
    
    print(f'\n✓ Training complete in {(datetime.now() - start_time).total_seconds():.0f}s')
    print(f'Best model: {args.checkpoint}')


def main():
    parser = argparse.ArgumentParser(
        description='Advanced training for floorplan segmentation'
    )
    parser.add_argument('--data', required=True,
                       help='Dataset root with train/val subfolders')
    parser.add_argument('--epochs', type=int, default=50,
                       help='Number of epochs (default: 50)')
    parser.add_argument('--bs', type=int, default=8,
                       help='Batch size (default: 8)')
    parser.add_argument('--lr', type=float, default=1e-4,
                       help='Learning rate (default: 1e-4)')
    parser.add_argument('--checkpoint', default='model_best.pth',
                       help='Checkpoint path (default: model_best.pth)')
    parser.add_argument('--encoder', choices=['resnet34', 'efficientnet-b1', 
                                              'efficientnet-b3', 'se_resnext50_32x4d',
                                              'timm-densenet121'],
                       default='resnet34',
                       help='Encoder architecture (default: resnet34)')
    parser.add_argument('--augment-level', choices=['low', 'medium', 'high'],
                       default='medium',
                       help='Augmentation intensity (default: medium)')
    parser.add_argument('--size', type=int, default=512,
                       help='Image size (default: 512)')
    parser.add_argument('--patience', type=int, default=10,
                       help='Early stopping patience (default: 10)')
    parser.add_argument('--mixup', action='store_true',
                       help='Enable mixup augmentation')
    parser.add_argument('--cutmix', action='store_true',
                       help='Enable cutmix augmentation')
    
    args = parser.parse_args()
    
    print('=' * 70)
    print('ADVANCED FLOORPLAN SEGMENTATION TRAINING')
    print('=' * 70)
    print(f'Epochs: {args.epochs}')
    print(f'Batch size: {args.bs}')
    print(f'Learning rate: {args.lr}')
    print(f'Encoder: {args.encoder}')
    print(f'Augmentation: {args.augment_level}')
    print(f'Image size: {args.size}x{args.size}')
    print(f'Mixup: {args.mixup}')
    print(f'CutMix: {args.cutmix}')
    print('=' * 70)
    
    train_advanced(args)


if __name__ == '__main__':
    main()
