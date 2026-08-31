# Development Guide

This guide is for developers who want to modify, extend, or contribute to the project.

## Project Structure

```
├── app.py                      # Main Flask application
├── config.py                   # Configuration management (uses .env)
├── sample_data.py              # Generate sample training data
├── train_segmentation.py       # Train U-Net model
├── ml_dataset.py               # Dataset loader for training
├── pdf_to_images.py            # Convert PDFs to images
├── labelme_to_masks.py         # Convert LabelMe JSON to masks
│
├── templates/
│   ├── index.html              # Upload form
│   └── result.html             # Results with interactive editor
│
├── static/
│   └── output/                 # Generated images and CSVs
│
├── requirements.txt            # Python dependencies
├── .env.example                # Configuration template
├── setup.bat                   # Windows setup script
├── run.bat                     # Windows run script
├── README.md                   # User guide
├── SETUP.md                    # Setup instructions
├── TRAINING.md                 # ML training guide
└── DEVELOPMENT.md              # This file
```

## Setting up Development Environment

1. Run the setup script:
   ```bash
   setup.bat
   ```

2. Activate the virtual environment:
   ```bash
   venv\Scripts\activate.bat
   ```

3. Install development dependencies:
   ```bash
   pip install pytest black flake8
   ```

## Configuration

The app uses a `config.py` file that reads from `.env`. To customize settings:

1. Copy `.env.example` to `.env`
2. Edit values as needed
3. Restart the app

Common configurations:
- `FLASK_DEBUG=True/False` - Enable/disable debug mode
- `PDF_DPI=200` - DPI for PDF to image conversion (higher = better quality, slower)
- `MIN_ROOM_AREA_PX=2000` - Minimum room size in pixels
- `LOG_LEVEL=DEBUG/INFO/WARNING` - Logging verbosity

## Code Organization

### app.py Structure
- **Imports & Config** - Dependencies and configuration loading
- **Logging Setup** - Logger initialization
- **Helper Functions**:
  - `detect_rooms()` - Heuristic room detection
  - `ml_segment()` - ML-based segmentation
  - `draw_rooms()` - Visualization
- **Routes**:
  - `GET /` - Index page
  - `POST /extract` - PDF processing and room detection
  - `POST /save_corrections` - Save user corrections
  - `POST /optimize_orientations` - Optimize carpet orientation

### Key Dependencies

- **Flask** - Web framework
- **OpenCV (cv2)** - Image processing
- **NumPy** - Numerical operations
- **Pillow** - Image handling
- **Shapely** - Polygon geometry
- **pdf2image** - PDF conversion (requires Poppler)
- **PyTorch + segmentation-models-pytorch** - ML (optional)

## Common Tasks

### Adding a New Configuration Option

1. Add to `.env.example`:
   ```ini
   NEW_OPTION=default_value
   ```

2. Add to `config.py`:
   ```python
   NEW_OPTION = os.getenv("NEW_OPTION", "default_value")
   ```

3. Use in `app.py`:
   ```python
   from config import Config
   value = Config.NEW_OPTION
   ```

### Modifying Room Detection

Edit the `detect_rooms()` function in `app.py`:
- Adjust `GaussianBlur` kernel size for different smoothing
- Adjust `morphologyEx` iterations for gap filling
- Adjust `approxPolyDP` epsilon for polygon simplification

### Adding New Routes

Example:
```python
@app.route("/new-endpoint", methods=["POST"])
def new_endpoint():
    try:
        data = request.get_json()
        # Process data
        return jsonify({'result': 'success'})
    except Exception as e:
        logger.exception('Error: %s', e)
        return jsonify({'error': str(e)}), 500
```

### ML Model Integration

To use a custom ML model:

1. Train and save your model (PyTorch format)
2. Place it as `model.pth` in project root
3. Check `ml_segment()` function to ensure architecture compatibility
4. Enable in web UI

## Testing

Create tests in a `tests/` folder:

```python
# tests/test_app.py
import pytest
from app import app

def test_index():
    client = app.test_client()
    response = client.get('/')
    assert response.status_code == 200
```

Run tests:
```bash
pytest tests/
```

## Debugging

### Enable Debug Mode

1. Edit `.env`:
   ```ini
   FLASK_DEBUG=True
   LOG_LEVEL=DEBUG
   ```

2. Restart the app - it will reload on file changes

### View Logs

Logs appear in console by default. To save to file, update `.env`:
```ini
LOG_FILE=logs/app.log
```

### Browser DevTools

- Press `F12` to open DevTools
- Check "Network" tab to see API calls
- Check "Console" tab for JavaScript errors

## Performance Optimization

### Image Processing
- Reduce `PDF_DPI` for faster PDF conversion
- Increase `MIN_ROOM_AREA_PX` to skip small noise
- Use smaller input images if possible

### ML Inference
- Use GPU: Update `config.py` to set device to 'cuda'
- Quantize model to reduce size
- Batch process multiple images

### Web Performance
- Compress static assets
- Add image caching headers
- Use CDN for large files

## Contributing

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make changes and test thoroughly
3. Follow PEP 8 style guide: `black app.py`
4. Lint code: `flake8 app.py`
5. Write/update tests
6. Submit pull request with description

## Common Issues & Solutions

### Import Errors
- Ensure virtual environment is activated
- Run `pip install -r requirements.txt`

### PDF Processing Hangs
- Reduce `PDF_DPI`
- Check if file is corrupted
- Set `PDF_TIMEOUT` in config

### ML Model Not Loading
- Check model path in `.env` or code
- Verify model format (PyTorch state_dict)
- Check device availability (CPU vs GPU)

### Memory Issues
- Reduce image DPI
- Process one image at a time
- Monitor with `Task Manager` (Windows)

## Resources

- [Flask Docs](https://flask.palletsprojects.com/)
- [OpenCV Tutorials](https://docs.opencv.org/)
- [PyTorch Docs](https://pytorch.org/docs/)
- [segmentation-models-pytorch](https://github.com/qubvel-org/segmentation_models.pytorch)

## Questions?

Check the README.md, SETUP.md, or TRAINING.md files first. For issues, see the troubleshooting section in SETUP.md.
