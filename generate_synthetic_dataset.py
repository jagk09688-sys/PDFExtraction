"""
Enhanced synthetic floorplan dataset generator.

Generates diverse, realistic floorplan images with matching binary masks.
Includes various room shapes, wall styles, doors, windows, and layouts.

Usage:
    python generate_synthetic_dataset.py --count 500 --output dataset/synthetic
    python generate_synthetic_dataset.py --count 1000 --output dataset/synthetic --variation-level high
"""

import os
import numpy as np
from PIL import Image, ImageDraw
import argparse
from typing import List, Tuple
import random


class FloorplanGenerator:
    """Generate diverse synthetic floorplans."""
    
    def __init__(self, width=800, height=600, seed=42):
        self.width = width
        self.height = height
        random.seed(seed)
        np.random.seed(seed)
    
    def generate_room_shape(self, x, y, min_w=80, max_w=200, min_h=80, max_h=150):
        """Generate a room polygon (rectangle or L-shape or trapezoid)."""
        shape_type = random.choice(['rectangle', 'l_shape', 'trapezoid', 'polygon'])
        
        w = random.randint(min_w, max_w)
        h = random.randint(min_h, max_h)
        
        if shape_type == 'rectangle':
            return [(x, y), (x+w, y), (x+w, y+h), (x, y+h)]
        
        elif shape_type == 'l_shape':
            # L-shaped room
            sub_w = w // 2
            sub_h = h // 2
            choice = random.choice(['normal', 'rotated'])
            if choice == 'normal':
                return [
                    (x, y), (x+w, y), (x+w, y+sub_h),
                    (x+sub_w, y+sub_h), (x+sub_w, y+h), (x, y+h)
                ]
            else:
                return [
                    (x, y), (x+sub_w, y), (x+sub_w, y+sub_h),
                    (x+w, y+sub_h), (x+w, y+h), (x, y+h)
                ]
        
        elif shape_type == 'trapezoid':
            # Trapezoid room
            offset = random.randint(10, w//4)
            return [(x, y), (x+w, y), (x+w-offset, y+h), (x+offset, y+h)]
        
        else:  # polygon
            # Irregular polygon
            points = [(x, y), (x+w, y)]
            points.append((x+w-random.randint(0, w//4), y+h//2))
            points.append((x+w, y+h))
            points.append((x+random.randint(0, w//4), y+h))
            return points
    
    def add_door(self, draw, polygon, wall_color=(0, 0, 0), door_width=20):
        """Add a door to a room polygon."""
        if len(polygon) < 2:
            return
        
        # Choose random wall (edge) to place door
        edge_idx = random.randint(0, len(polygon) - 1)
        p1 = polygon[edge_idx]
        p2 = polygon[(edge_idx + 1) % len(polygon)]
        
        # Door position along wall
        t = random.uniform(0.2, 0.8)
        door_x = int(p1[0] + t * (p2[0] - p1[0]))
        door_y = int(p1[1] + t * (p2[1] - p1[1]))
        
        # Door swing style
        door_type = random.choice(['single_swing', 'double_swing', 'sliding'])
        
        if door_type == 'single_swing':
            draw.rectangle([door_x, door_y, door_x+door_width, door_y+door_width], 
                          outline=(100, 100, 100), width=2)
        elif door_type == 'double_swing':
            mid = door_x + door_width // 2
            draw.rectangle([door_x, door_y, mid, door_y+door_width], 
                          outline=(100, 100, 100), width=2)
            draw.rectangle([mid, door_y, door_x+door_width, door_y+door_width], 
                          outline=(100, 100, 100), width=2)
        else:  # sliding
            draw.rectangle([door_x, door_y, door_x+door_width+10, door_y+door_width], 
                          outline=(80, 80, 80), width=2)
            draw.line([(door_x+door_width, door_y), (door_x+door_width, door_y+door_width)], 
                     fill=(80, 80, 80), width=1)
    
    def add_window(self, draw, polygon):
        """Add a window to a room polygon."""
        if len(polygon) < 2:
            return
        
        edge_idx = random.randint(0, len(polygon) - 1)
        p1 = polygon[edge_idx]
        p2 = polygon[(edge_idx + 1) % len(polygon)]
        
        t = random.uniform(0.2, 0.8)
        window_x = int(p1[0] + t * (p2[0] - p1[0]))
        window_y = int(p1[1] + t * (p2[1] - p1[1]))
        
        window_width = random.randint(15, 25)
        draw.rectangle([window_x, window_y, window_x+window_width, window_y+8], 
                      outline=(150, 150, 255), width=2)
    
    def add_furniture(self, draw, polygon):
        """Add simple furniture silhouettes."""
        # Get room centroid
        xs = [p[0] for p in polygon]
        ys = [p[1] for p in polygon]
        cx = sum(xs) // len(xs)
        cy = sum(ys) // len(ys)
        
        furniture_type = random.choice(['bed', 'desk', 'table', 'sofa'])
        
        if furniture_type == 'bed':
            draw.rectangle([cx-30, cy-40, cx+30, cy+40], 
                          outline=(200, 150, 100), width=2)
        elif furniture_type == 'desk':
            draw.rectangle([cx-25, cy-15, cx+25, cy+15], 
                          outline=(180, 100, 50), width=2)
        elif furniture_type == 'table':
            draw.ellipse([cx-20, cy-20, cx+20, cy+20], 
                        outline=(150, 100, 50), width=2)
        else:  # sofa
            draw.rectangle([cx-35, cy-10, cx+35, cy+20], 
                          outline=(100, 50, 50), width=2)
    
    def generate_floorplan(self, variation_level='medium'):
        """Generate a single floorplan with mask."""
        img = Image.new('RGB', (self.width, self.height), (255, 255, 255))
        mask = Image.new('L', (self.width, self.height), 0)
        
        draw = ImageDraw.Draw(img)
        draw_mask = ImageDraw.Draw(mask)
        
        # Number of rooms based on variation level
        if variation_level == 'low':
            num_rooms = random.randint(1, 2)
        elif variation_level == 'medium':
            num_rooms = random.randint(2, 4)
        else:  # high
            num_rooms = random.randint(3, 6)
        
        # Wall thickness varies
        wall_thickness = random.choice([2, 3, 4, 5, 6])
        
        # Wall color varies
        if random.random() < 0.7:
            wall_color = (0, 0, 0)  # Black walls (most common)
        elif random.random() < 0.5:
            wall_color = (50, 50, 50)  # Dark gray
        else:
            wall_color = (100, 100, 100)  # Medium gray
        
        # Generate room layout
        occupied = []
        rooms = []
        
        for _ in range(num_rooms):
            attempts = 0
            while attempts < 10:
                x = random.randint(20, self.width - 300)
                y = random.randint(20, self.height - 250)
                w = random.randint(80, 200)
                h = random.randint(80, 150)
                
                # Check collision
                overlap = False
                for ox, oy, ow, oh in occupied:
                    if not (x+w+20 < ox or x > ox+ow+20 or 
                            y+h+20 < oy or y > oy+oh+20):
                        overlap = True
                        break
                
                if not overlap:
                    occupied.append((x, y, w, h))
                    room_shape = self.generate_room_shape(x, y, min_w=w-20, max_w=w, 
                                                         min_h=h-20, max_h=h)
                    rooms.append(room_shape)
                    break
                
                attempts += 1
        
        # Draw rooms
        for room in rooms:
            # Draw walls
            draw.polygon(room, outline=wall_color, width=0)
            room_tuple = [tuple(p) for p in room]
            draw.line(room_tuple + [room_tuple[0]], fill=wall_color, width=wall_thickness)
            
            # Draw mask
            draw_mask.polygon(room, fill=255)
            
            # Add doors
            if random.random() < 0.7:
                self.add_door(draw, room, wall_color=wall_color)
            
            # Add windows
            if random.random() < 0.6:
                self.add_window(draw, room)
            
            # Add furniture
            if random.random() < 0.5 and variation_level != 'low':
                self.add_furniture(draw, room)
        
        # Random noise/artifacts
        if random.random() < 0.3:
            # Add some scan lines or artifacts
            for _ in range(random.randint(2, 5)):
                y = random.randint(0, self.height)
                opacity = random.randint(5, 15)
                for x in range(0, self.width, 5):
                    draw.point((x, y), fill=(200, 200, 200))
        
        return img, mask
    
    def generate_dataset(self, count, output_dir, variation_level='medium', 
                        split_ratio=0.8):
        """Generate complete dataset with train/val split."""
        os.makedirs(output_dir, exist_ok=True)
        
        train_count = int(count * split_ratio)
        val_count = count - train_count
        
        splits = [
            ('train', train_count),
            ('val', val_count)
        ]
        
        for split_name, split_count in splits:
            split_dir = os.path.join(output_dir, split_name)
            img_dir = os.path.join(split_dir, 'images')
            mask_dir = os.path.join(split_dir, 'masks')
            
            os.makedirs(img_dir, exist_ok=True)
            os.makedirs(mask_dir, exist_ok=True)
            
            for i in range(split_count):
                img, mask = self.generate_floorplan(variation_level)
                
                img_path = os.path.join(img_dir, f'floorplan_{i:05d}.png')
                mask_path = os.path.join(mask_dir, f'floorplan_{i:05d}.png')
                
                img.save(img_path)
                mask.save(mask_path)
                
                if (i + 1) % 50 == 0:
                    print(f'  [{split_name}] Generated {i+1}/{split_count} samples')
        
        print(f'✓ Dataset complete: {count} samples in {output_dir}')
        print(f'  Train: {train_count}, Val: {val_count}')


def main():
    parser = argparse.ArgumentParser(
        description='Generate synthetic floorplan dataset'
    )
    parser.add_argument('--count', type=int, default=500,
                       help='Total number of samples to generate (default: 500)')
    parser.add_argument('--output', type=str, default='dataset/synthetic',
                       help='Output directory (default: dataset/synthetic)')
    parser.add_argument('--variation-level', choices=['low', 'medium', 'high'],
                       default='medium',
                       help='Complexity level: low=1-2 rooms, medium=2-4, high=3-6')
    parser.add_argument('--width', type=int, default=800,
                       help='Image width (default: 800)')
    parser.add_argument('--height', type=int, default=600,
                       help='Image height (default: 600)')
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed for reproducibility')
    parser.add_argument('--train-split', type=float, default=0.8,
                       help='Train/val split ratio (default: 0.8)')
    
    args = parser.parse_args()
    
    print(f'Generating {args.count} synthetic floorplans...')
    print(f'  Output: {args.output}')
    print(f'  Variation: {args.variation_level}')
    print(f'  Image size: {args.width}x{args.height}')
    
    gen = FloorplanGenerator(width=args.width, height=args.height, seed=args.seed)
    gen.generate_dataset(
        count=args.count,
        output_dir=args.output,
        variation_level=args.variation_level,
        split_ratio=args.train_split
    )


if __name__ == '__main__':
    main()
