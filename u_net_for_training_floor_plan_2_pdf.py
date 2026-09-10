"""
U-Net training script for floor plan room segmentation.

This script trains a U-Net model with a ResNet34 encoder using transfer learning.
It is designed for datasets prepared as:

    data/
      train/
        images/
        masks/
      val/
        images/
        masks/

The script expects masks to be single-channel PNG files where room pixels are 255
and background is 0.

Example:
    python u_net_for_training_floor_plan_2_pdf.py --data dataset --epochs 50 --bs 8
"""

import argparse
import os
import random
from pathlib import Path

import albumentations as A
import numpy as np
import segmentation_models_pytorch as smp
import torch
from torch.utils.data import DataLoader

from ml_dataset import FloorplanDataset


def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def get_train_transforms(size=512):
    """Return augmentation pipeline for training."""
    return A.Compose(
        [
            A.Resize(height=size, width=size),
            A.HorizontalFlip(p=0.5),
            A.VerticalFlip(p=0.5),
            A.RandomRotate90(p=0.5),
            A.Rotate(limit=20, p=0.4),
            A.RandomBrightnessContrast(brightness_limit=0.15, contrast_limit=0.15, p=0.4),
            A.GaussNoise(var_limit=(10.0, 50.0), p=0.2),
            A.GaussianBlur(blur_limit=(3, 5), p=0.15),
        ],
        is_check_shapes=False,
    )


def get_val_transforms(size=512):
    """Return minimal augmentation pipeline for validation."""
    return A.Compose(
        [A.Resize(height=size, width=size)],
        is_check_shapes=False,
    )


def build_model(encoder_name='resnet34', in_channels=3, classes=1):
    """Create the U-Net model with transfer learning."""
    return smp.Unet(
        encoder_name=encoder_name,
        encoder_weights='imagenet',
        in_channels=in_channels,
        classes=classes,
        activation=None,
    )


class EarlyStopping:
    """Stop training early when validation does not improve."""

    def __init__(self, patience=8, min_delta=1e-4):
        self.patience = patience
        self.min_delta = min_delta
        self.best_loss = float('inf')
        self.counter = 0

    def update(self, val_loss):
        if val_loss < self.best_loss - self.min_delta:
            self.best_loss = val_loss
            self.counter = 0
            return False
        self.counter += 1
        return self.counter >= self.patience


def validate_dataset_paths(data_root: Path):
    """Check for train/val folder structure and report missing files clearly."""
    train_images_dir = data_root / 'train' / 'images'
    train_masks_dir = data_root / 'train' / 'masks'
    val_images_dir = data_root / 'val' / 'images'
    val_masks_dir = data_root / 'val' / 'masks'

    missing = []
    for path in [train_images_dir, train_masks_dir, val_images_dir, val_masks_dir]:
        if not path.exists():
            missing.append(str(path))

    if missing:
        raise FileNotFoundError(
            "Missing dataset folders. Expected structure:\n"
            f"  {train_images_dir}\n"
            f"  {train_masks_dir}\n"
            f"  {val_images_dir}\n"
            f"  {val_masks_dir}\n"
            f"Missing: {', '.join(missing)}"
        )


def get_dataset_filenames(images_dir: Path, masks_dir: Path):
    image_files = sorted(p for p in images_dir.iterdir() if p.is_file())
    mask_files = {p.name for p in masks_dir.iterdir() if p.is_file()}

    valid_images = []
    missing_masks = []
    for image_file in image_files:
        if image_file.name not in mask_files:
            missing_masks.append(image_file.name)
        else:
            valid_images.append(image_file)

    if missing_masks:
        print(
            f"Warning: {len(missing_masks)} image(s) do not have matching masks. "
            f"These will be skipped: {', '.join(missing_masks[:10])}"
        )

    return valid_images


def save_checkpoint(model, optimizer, scheduler, epoch, best_val_loss, checkpoint_path, extra=None):
    checkpoint_path = Path(checkpoint_path)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        'epoch': epoch,
        'state_dict': model.state_dict(),
        'optimizer': optimizer.state_dict(),
        'best_val_loss': best_val_loss,
    }
    if scheduler is not None:
        payload['scheduler'] = scheduler.state_dict()
    if extra:
        payload.update(extra)

    torch.save(payload, checkpoint_path)


def train(args):
    set_seed(args.seed)

    device_name = args.device
    if device_name == 'auto':
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    else:
        device = torch.device(device_name)

    print(f"Using device: {device}")

    data_root = Path(args.data)
    validate_dataset_paths(data_root)

    train_images_dir = data_root / 'train' / 'images'
    train_masks_dir = data_root / 'train' / 'masks'
    val_images_dir = data_root / 'val' / 'images'
    val_masks_dir = data_root / 'val' / 'masks'

    train_image_files = get_dataset_filenames(train_images_dir, train_masks_dir)
    val_image_files = get_dataset_filenames(val_images_dir, val_masks_dir)

    if not train_image_files:
        raise FileNotFoundError(
            f"No valid training image/mask pairs found under {train_images_dir} and {train_masks_dir}"
        )
    if not val_image_files:
        raise FileNotFoundError(
            f"No valid validation image/mask pairs found under {val_images_dir} and {val_masks_dir}"
        )

    train_ds = FloorplanDataset(
        str(train_images_dir),
        str(train_masks_dir),
        transform=get_train_transforms(args.size),
        allowed_files=[f.name for f in train_image_files],
    )
    val_ds = FloorplanDataset(
        str(val_images_dir),
        str(val_masks_dir),
        transform=get_val_transforms(args.size),
        allowed_files=[f.name for f in val_image_files],
    )

    if len(train_ds) == 0 or len(val_ds) == 0:
        raise RuntimeError('Dataset is empty after filtering missing masks. Please check your image/mask pairs.')

    train_loader = DataLoader(
        train_ds,
        batch_size=args.bs,
        shuffle=True,
        num_workers=args.workers,
        pin_memory=torch.cuda.is_available(),
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=args.bs,
        shuffle=False,
        num_workers=max(1, args.workers // 2),
        pin_memory=torch.cuda.is_available(),
    )

    model = build_model(args.encoder, classes=1)
    model.to(device)

    if args.resume and os.path.exists(args.resume):
        state = torch.load(args.resume, map_location=device)
        if isinstance(state, dict) and 'state_dict' in state:
            model.load_state_dict(state['state_dict'])
            print(f"Resumed from checkpoint: {args.resume}")
        else:
            model.load_state_dict(state)
            print(f"Resumed from checkpoint: {args.resume}")

    loss_fn = smp.losses.DiceLoss(mode='binary') + torch.nn.BCEWithLogitsLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode='min',
        factor=0.5,
        patience=5,
        verbose=True,
    )

    use_amp = args.amp and device.type == 'cuda'
    scaler = torch.cuda.amp.GradScaler(enabled=use_amp)
    early_stopping = EarlyStopping(patience=args.patience, min_delta=args.min_delta)

    best_val_loss = float('inf')
    best_epoch = 0

    print(f"Train samples: {len(train_ds)}")
    print(f"Validation samples: {len(val_ds)}")
    print(f"Epochs: {args.epochs}")
    print(f"Batch size: {args.bs}")
    print(f"Learning rate: {args.lr}")
    print(f"Encoder: {args.encoder}")
    print(f"Automatic mixed precision: {use_amp}")

    for epoch in range(1, args.epochs + 1):
        model.train()
        train_loss_total = 0.0

        for imgs, masks in train_loader:
            imgs = imgs.float().to(device)
            masks = masks.float().to(device)

            optimizer.zero_grad(set_to_none=True)

            if use_amp:
                with torch.autocast(device_type=device.type, dtype=torch.float16):
                    preds = model(imgs)
                    loss = loss_fn(preds, masks)
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=args.max_norm)
                scaler.step(optimizer)
                scaler.update()
            else:
                preds = model(imgs)
                loss = loss_fn(preds, masks)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=args.max_norm)
                optimizer.step()

            train_loss_total += loss.item()

        avg_train_loss = train_loss_total / len(train_loader)

        model.eval()
        val_loss_total = 0.0
        with torch.no_grad():
            for imgs, masks in val_loader:
                imgs = imgs.float().to(device)
                masks = masks.float().to(device)

                if use_amp:
                    with torch.autocast(device_type=device.type, dtype=torch.float16):
                        preds = model(imgs)
                        loss = loss_fn(preds, masks)
                else:
                    preds = model(imgs)
                    loss = loss_fn(preds, masks)

                val_loss_total += loss.item()

        avg_val_loss = val_loss_total / len(val_loader)
        scheduler.step(avg_val_loss)

        print(
            f"Epoch {epoch:03d}/{args.epochs} | "
            f"train_loss={avg_train_loss:.4f} | "
            f"val_loss={avg_val_loss:.4f} | "
            f"lr={optimizer.param_groups[0]['lr']:.2e}"
        )

        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            best_epoch = epoch
            save_checkpoint(
                model=model,
                optimizer=optimizer,
                scheduler=scheduler,
                epoch=epoch,
                best_val_loss=best_val_loss,
                checkpoint_path=args.checkpoint,
            )
            print(f"  Saved best checkpoint to {args.checkpoint}")

        if early_stopping.update(avg_val_loss):
            print(
                f"Early stopping triggered at epoch {epoch} because validation loss did not improve for {args.patience} epochs."
            )
            break

    print(f"Training finished. Best validation loss: {best_val_loss:.4f} at epoch {best_epoch}")
    print(f"Best model saved to: {args.checkpoint}")


def main():
    parser = argparse.ArgumentParser(
        description='Train a U-Net with ResNet34 encoder for floorplan room segmentation.'
    )
    parser.add_argument(
        '--data',
        required=True,
        help='Root dataset folder containing train/ and val/ folders',
    )
    parser.add_argument(
        '--epochs',
        type=int,
        default=60,
        help='Number of training epochs (default: 60)',
    )
    parser.add_argument(
        '--bs',
        type=int,
        default=8,
        help='Batch size (default: 8)',
    )
    parser.add_argument(
        '--lr',
        type=float,
        default=1e-4,
        help='Learning rate (default: 1e-4)',
    )
    parser.add_argument(
        '--size',
        type=int,
        default=512,
        help='Image resize size for training and validation (default: 512)',
    )
    parser.add_argument(
        '--encoder',
        default='resnet34',
        choices=['resnet34', 'efficientnet-b0', 'efficientnet-b1', 'efficientnet-b3', 'se_resnext50_32x4d'],
        help='Encoder name for the U-Net. Default: resnet34',
    )
    parser.add_argument(
        '--checkpoint',
        default='model_best.pth',
        help='Checkpoint file path (default: model_best.pth)',
    )
    parser.add_argument(
        '--resume',
        default='',
        help='Optional checkpoint path to resume from',
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=4,
        help='Number of worker processes for DataLoader (default: 4)',
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='Random seed for reproducibility (default: 42)',
    )
    parser.add_argument(
        '--device',
        default='auto',
        choices=['auto', 'cpu', 'cuda'],
        help='Training device (default: auto)',
    )
    parser.add_argument(
        '--patience',
        type=int,
        default=8,
        help='Early stopping patience in epochs (default: 8)',
    )
    parser.add_argument(
        '--min-delta',
        type=float,
        default=1e-4,
        help='Minimum loss improvement to reset early stopping (default: 1e-4)',
    )
    parser.add_argument(
        '--max-norm',
        type=float,
        default=5.0,
        help='Gradient clipping norm (default: 5.0)',
    )
    parser.add_argument(
        '--amp',
        action='store_true',
        help='Enable automatic mixed precision on CUDA when available',
    )

    args = parser.parse_args()

    print('=' * 70)
    print('U-NET FLOORPLAN SEGMENTATION TRAINING')
    print('=' * 70)
    print(f"Dataset root: {args.data}")
    print(f"Encoder: {args.encoder}")
    print(f"Image size: {args.size}")
    print(f"Epochs: {args.epochs}")
    print(f"Batch size: {args.bs}")
    print(f"Learning rate: {args.lr}")
    print(f"Checkpoint: {args.checkpoint}")
    print(f"Device: {args.device}")
    print(f"Seed: {args.seed}")
    print('=' * 70)

    train(args)


if __name__ == '__main__':
    main()
