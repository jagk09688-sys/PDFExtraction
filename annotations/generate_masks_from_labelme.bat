@echo off
setlocal
cd /d "%~dp0\.."
python labelme_to_masks.py --images annotations/images --annotations annotations/labelme_json --output annotations/masks
