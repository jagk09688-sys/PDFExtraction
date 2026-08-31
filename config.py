"""Configuration management for the Flask app.

Supports reading from .env file and environment variables.
"""

import os
from pathlib import Path

# Load .env file if it exists
ENV_FILE = Path(__file__).parent / ".env"
if ENV_FILE.exists():
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


class Config:
    """Application configuration."""

    # Flask Settings
    DEBUG = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1")
    ENV = os.getenv("FLASK_ENV", "development")
    PORT = int(os.getenv("FLASK_PORT", 5000))
    HOST = os.getenv("FLASK_HOST", "127.0.0.1")

    # PDF Processing
    PDF_DPI = int(os.getenv("PDF_DPI", 200))
    MAX_PDF_SIZE = int(os.getenv("MAX_PDF_SIZE_MB", 10)) * 1024 * 1024
    PDF_TIMEOUT = int(os.getenv("PDF_TIMEOUT_SECONDS", 30))

    # Room Detection
    MIN_ROOM_AREA_PX = int(os.getenv("MIN_ROOM_AREA_PX", 2000))
    MORPHOLOGY_KERNEL_SIZE = int(os.getenv("MORPHOLOGY_KERNEL_SIZE", 5))
    CONTOUR_EPSILON = float(os.getenv("CONTOUR_APPROXIMATION_EPSILON", 0.01))

    # ML Segmentation
    ML_MODEL_PATH = os.getenv("ML_MODEL_PATH", "model.pth")
    ML_DEVICE = os.getenv("ML_INFERENCE_DEVICE", "cpu")
    ML_THRESHOLD = float(os.getenv("ML_SEGMENTATION_THRESHOLD", 0.5))

    # Default Calculations
    DEFAULT_PPM = float(os.getenv("DEFAULT_PIXELS_PER_METER", 100))
    DEFAULT_ROLL_WIDTH = float(os.getenv("DEFAULT_ROLL_WIDTH_M", 3.66))
    DEFAULT_WASTE_PCT = float(os.getenv("DEFAULT_WASTE_PERCENT", 10))

    # Output
    OUTPUT_DIR = os.getenv("OUTPUT_DIR", "static/output")
    OUTPUT_CLEANUP_DAYS = int(os.getenv("KEEP_OUTPUT_FILES_DAYS", 7))

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", None)
