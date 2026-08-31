from flask import Flask, request, render_template, send_from_directory, jsonify, send_file
from pdf2image import convert_from_bytes
import os
import io
import cv2
import numpy as np
from shapely.geometry import Polygon
from PIL import Image
import logging
import os.path as osp
from werkzeug.utils import secure_filename
from config import Config

# Configure logging
log_handlers = [logging.StreamHandler()]
if Config.LOG_FILE:
    os.makedirs(os.path.dirname(Config.LOG_FILE) or ".", exist_ok=True)
    log_handlers.append(logging.FileHandler(Config.LOG_FILE))

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=log_handlers
)
logger = logging.getLogger(__name__)

# Optional ML dependencies
try:
    import torch
    import segmentation_models_pytorch as smp
    import albumentations as A
    ML_AVAILABLE = True
except ImportError:
    torch = None
    smp = None
    A = None
    ML_AVAILABLE = False
    logger.warning('ML libraries not available; ML segmentation will be disabled')

app = Flask(__name__)

# Security: configuration
MAX_PDF_SIZE = Config.MAX_PDF_SIZE
ALLOWED_EXTENSIONS = {'.pdf'}

# Ensure directories exist
BASE_DIR = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(BASE_DIR, Config.OUTPUT_DIR)
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

logger.info(f'Output directory: {OUTPUT_DIR}')
logger.info(f'Configuration: PDF_DPI={Config.PDF_DPI}, MIN_AREA_PX={Config.MIN_ROOM_AREA_PX}')


def detect_rooms(pil_img: Image.Image, min_area_px: int = None) -> tuple:
    """Detect rooms in a floorplan image using OpenCV contour detection.
    
    Args:
        pil_img: PIL Image object in RGB format
        min_area_px: Minimum contour area in pixels to consider as a room
        
    Returns:
        Tuple of (img_rgb, rooms) where rooms is a list of detected room dicts
    """
    if min_area_px is None:
        min_area_px = Config.MIN_ROOM_AREA_PX
    
    try:
        img = np.array(pil_img.convert("RGB"))
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # Invert if background is dark
        if np.mean(th) < 127:
            th = 255 - th
        # Morphology to close gaps
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (Config.MORPHOLOGY_KERNEL_SIZE, Config.MORPHOLOGY_KERNEL_SIZE))
        closed = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        rooms = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area_px:
                continue
            eps = Config.CONTOUR_EPSILON * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, eps, True)
            poly = [(int(p[0][0]), int(p[0][1])) for p in approx]
            # Ensure polygon valid
            if len(poly) >= 3:
                rooms.append({"polygon": poly, "area_px": area, "contour": cnt})
        
        logger.info(f'Detected {len(rooms)} rooms')
        return img, rooms
    except Exception as e:
        logger.exception('Room detection failed: %s', e)
        raise


def ml_segment(pil_img: Image.Image, model_path: str = 'model.pth', threshold: float = 0.5):
    """Run a segmentation model (if available) and return binary mask (uint8 0/255) same size as image.
    
    Args:
        pil_img: PIL Image object
        model_path: Path to model weights file
        threshold: Threshold for binary mask (0-1)
        
    Returns:
        Binary mask as numpy array or None if model not available
    """
    if not ML_AVAILABLE:
        logger.warning('ML libs not available; falling back to heuristic')
        return None
    if not osp.exists(model_path):
        logger.warning('Model file not found: %s', model_path)
        return None
    # load model
    try:
        device = torch.device('cpu')
        model = smp.Unet(encoder_name='resnet34', encoder_weights=None, in_channels=3, classes=1)
        state = torch.load(model_path, map_location=device)
        if 'state_dict' in state:
            model.load_state_dict(state['state_dict'])
        else:
            model.load_state_dict(state)
        model.to(device)
        model.eval()
        logger.info('ML model loaded successfully')
    except Exception as e:
        logger.exception('Failed loading model: %s', e)
        return None

    img = np.array(pil_img.convert('RGB'))
    # prepare: normalize to 0-1
    inp = img.astype(np.float32) / 255.0
    # resize to model expected size (keep same for simplicity)
    # convert HWC->CHW
    inp = np.transpose(inp, (2, 0, 1))[None, ...]
    tensor = torch.from_numpy(inp).to(device)
    with torch.no_grad():
        out = model(tensor)
        out = torch.sigmoid(out)
        out_np = out[0, 0].cpu().numpy()
    mask = (out_np >= threshold).astype(np.uint8) * 255
    mask = cv2.resize(mask, (pil_img.width, pil_img.height), interpolation=cv2.INTER_NEAREST)
    return mask


def draw_rooms(img_rgb: np.ndarray, rooms: list) -> np.ndarray:
    """Draw detected rooms as polygons on image.
    
    Args:
        img_rgb: RGB image as numpy array
        rooms: List of room dictionaries with 'polygon' key
        
    Returns:
        Image with drawn polygons
    """
    try:
        out = img_rgb.copy()
        for i, r in enumerate(rooms, start=1):
            pts = np.array(r["polygon"], np.int32)
            cv2.polylines(out, [pts], True, (0, 0, 255), 3)
            # label
            x, y = pts[0][0]
            cv2.putText(out, str(i), (x + 5, y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        return out
    except Exception as e:
        logger.exception('Failed to draw rooms: %s', e)
        raise


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/extract", methods=["POST"])
def extract():
    """Extract rooms from uploaded floorplan PDF."""
    try:
        f = request.files.get("pdf")
        if not f:
            logger.warning('No PDF file uploaded')
            return jsonify({'error': 'No PDF uploaded'}), 400
        
        # Security: check file size and extension
        if f.content_length and f.content_length > MAX_PDF_SIZE:
            logger.warning(f'PDF file too large: {f.content_length} bytes')
            return jsonify({'error': f'File too large (max {MAX_PDF_SIZE / 1024 / 1024}MB)'}), 413
        
        # Read optional inputs with validation
        try:
            pixels_per_meter = float(request.form.get("pixels_per_meter", str(Config.DEFAULT_PPM)))
            if pixels_per_meter <= 0:
                pixels_per_meter = Config.DEFAULT_PPM
        except (ValueError, TypeError):
            pixels_per_meter = Config.DEFAULT_PPM
        
        try:
            roll_width = float(request.form.get("roll_width", str(Config.DEFAULT_ROLL_WIDTH)))
            if roll_width <= 0:
                roll_width = Config.DEFAULT_ROLL_WIDTH
        except (ValueError, TypeError):
            roll_width = Config.DEFAULT_ROLL_WIDTH
        
        try:
            waste_pct = float(request.form.get("waste_pct", str(Config.DEFAULT_WASTE_PCT))) / 100.0
            if waste_pct < 0:
                waste_pct = Config.DEFAULT_WASTE_PCT / 100.0
        except (ValueError, TypeError):
            waste_pct = Config.DEFAULT_WASTE_PCT / 100.0
        
        try:
            tile_w = float(request.form.get("tile_w", "0"))
            tile_h = float(request.form.get("tile_h", "0"))
            tile_area = tile_w * tile_h if tile_w > 0 and tile_h > 0 else None
        except (ValueError, TypeError):
            tile_area = None

        pdf_bytes = f.read()
        # Convert first page to image
        try:
            images = convert_from_bytes(pdf_bytes, dpi=Config.PDF_DPI)
        except Exception as e:
            error_msg = str(e).lower()
            if 'poppler' in error_msg or 'pdftoimage' in error_msg:
                logger.error('Poppler not found: %s', e)
                return jsonify({
                    'error': 'Poppler not installed. PDF conversion requires Poppler. '
                             'Run setup.bat or download from https://github.com/oschwartz10612/poppler-windows/releases/'
                }), 500
            elif 'pdf' in error_msg or 'corrupt' in error_msg:
                logger.error('Invalid PDF file: %s', e)
                return jsonify({'error': 'Invalid or corrupted PDF file'}), 400
            else:
                logger.exception('PDF conversion failed: %s', e)
                return jsonify({'error': f'PDF conversion failed: {str(e)}'}), 500
        
        if len(images) == 0:
            logger.warning('No images extracted from PDF')
            return jsonify({'error': 'PDF conversion produced no images'}), 500
        
        pil_img = images[0]
        logger.info(f'Extracted image: {pil_img.size}')

        # Optionally use ML segmentation if requested and model available
        use_ml = bool(request.form.get('use_ml'))
        rooms = None
        if use_ml:
            logger.info('Attempting ML segmentation')
            mask = ml_segment(pil_img, model_path=os.path.join(BASE_DIR, 'model.pth'))
            if mask is not None:
                # Extract contours from mask
                try:
                    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    rooms = []
                    for cnt in contours:
                        area = cv2.contourArea(cnt)
                        if area < 2000:
                            continue
                        approx = cv2.approxPolyDP(cnt, 0.01 * cv2.arcLength(cnt, True), True)
                        poly = [(int(p[0][0]), int(p[0][1])) for p in approx]
                        if len(poly) >= 3:
                            rooms.append({'polygon': poly, 'area_px': area, 'contour': cnt})
                    logger.info(f'ML segmentation found {len(rooms)} rooms')
                except Exception as e:
                    logger.exception('ML contour extraction failed: %s', e)
                    rooms = None
            else:
                logger.info('ML segmentation unavailable, using heuristic')
        
        if rooms is None:
            logger.info('Using heuristic room detection')
            img_rgb, rooms = detect_rooms(pil_img)
        else:
            img_rgb = np.array(pil_img.convert('RGB'))

        # Compute room dimensions using min-area-rect and plan carpet strips
        ROLL_WIDTH_M = roll_width
        results = []
        for i, r in enumerate(rooms, start=1):
            area_px = r["area_px"]
            # Get min area rect from contour
            try:
                rect = cv2.minAreaRect(r["contour"])
                (cx, cy), (w_px, h_px), ang = rect
                # length = longer side, width = shorter side
                length_px = max(w_px, h_px)
                width_px = min(w_px, h_px)
            except Exception as e:
                # Fallback to bbox from polygon
                logger.debug(f'minAreaRect failed for room {i}, using bbox: {e}')
                xs = [p[0] for p in r["polygon"]]
                ys = [p[1] for p in r["polygon"]]
                length_px = max(xs) - min(xs)
                width_px = max(ys) - min(ys)

            area_m2 = area_px / (pixels_per_meter ** 2)
            length_m = length_px / pixels_per_meter
            width_m = width_px / pixels_per_meter

            # Two orientation choices: strips run along length (so strip_length=length_m, strips=ceil(width/roll_w))
            strips_a = int(np.ceil(width_m / ROLL_WIDTH_M))
            strip_len_a = length_m
            total_len_a = strips_a * strip_len_a

            # Alt orientation
            strips_b = int(np.ceil(length_m / ROLL_WIDTH_M))
            strip_len_b = width_m
            total_len_b = strips_b * strip_len_b

            # Choose orientation minimizing total length, then fewer seams
            if total_len_a < total_len_b or (total_len_a == total_len_b and (strips_a <= strips_b)):
                chosen = 'A'
                strips = strips_a
                strip_len = strip_len_a
                total_len = total_len_a
            else:
                chosen = 'B'
                strips = strips_b
                strip_len = strip_len_b
                total_len = total_len_b

            carpet_required = total_len  # meters of roll length
            # Waste area in m2 (area of used carpet minus room area)
            waste_area = (strips * strip_len * ROLL_WIDTH_M) - area_m2 if pixels_per_meter else None
            seams = max(0, strips - 1)

            tiles_needed = None
            if tile_area:
                tiles_needed = int(np.ceil(area_m2 / tile_area))

            results.append({
                "id": i,
                "area_m2": round(float(area_m2), 3),
                "length_m": round(float(length_m), 3),
                "width_m": round(float(width_m), 3),
                "chosen_orientation": chosen,
                "strips": strips,
                "strip_length_m": round(float(strip_len), 3),
                "carpet_required_m": round(float(carpet_required), 3),
                "waste_m2": round(float(waste_area), 3) if waste_area is not None else None,
                "seams": seams,
                "tiles_needed": tiles_needed,
                "polygon": r["polygon"],
            })

        out_img = draw_rooms(img_rgb, rooms)
        out_path = os.path.join(OUTPUT_DIR, "annotated.png")
        try:
            cv2.imwrite(out_path, cv2.cvtColor(out_img, cv2.COLOR_RGB2BGR))
            logger.info(f'Saved annotated image to {out_path}')
        except Exception as e:
            logger.exception(f'Failed to save annotated image: {e}')

        return render_template("result.html", results=results, image_path="static/output/annotated.png", pixels_per_meter=pixels_per_meter, roll_width=ROLL_WIDTH_M)
    
    except Exception as e:
        logger.exception(f'Extract failed: {e}')
        return jsonify({'error': 'Processing failed'}), 500



@app.route('/save_corrections', methods=['POST'])
def save_corrections():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'missing json'}), 400
    results_in = data.get('results')
    ppm = data.get('pixels_per_meter')
    try:
        ppm = float(ppm) if ppm is not None else None
    except Exception:
        ppm = None
    waste_pct = data.get('waste_pct', 0.10)
    try:
        waste_pct = float(waste_pct)
    except Exception:
        waste_pct = 0.1
    tile_w = data.get('tile_w')
    tile_h = data.get('tile_h')
    try:
        tile_w = float(tile_w) if tile_w not in (None, '') else None
        tile_h = float(tile_h) if tile_h not in (None, '') else None
        tile_area = tile_w * tile_h if tile_w and tile_h else None
    except Exception:
        tile_area = None
    # roll width from client (meters)
    roll_width = data.get('roll_width')
    try:
        roll_width = float(roll_width) if roll_width not in (None, '') else 3.66
    except Exception:
        roll_width = 3.66

    out_results = []
    csv_lines = ["room_id,area_m2,carpet_m2_including_waste,tiles_needed"]
    from shapely.geometry import Polygon as ShapelyPoly
    for r in results_in:
        rid = r.get('id')
        poly = r.get('polygon')
        if not poly or len(poly) < 3:
            continue
        try:
            shp = ShapelyPoly(poly)
            area_px = float(abs(shp.area))
        except Exception:
            # fallback: 0
            area_px = 0.0
        area_m2 = None
        carpet = None
        tiles_needed = None
        if ppm:
            area_m2 = area_px / (ppm * ppm)
            # compute strips similarly to extract logic
            try:
                # compute bounding box approximate
                xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
                length_px = max(xs) - min(xs)
                width_px = max(ys) - min(ys)
                length_m = max(length_px, width_px)/ppm
                width_m = min(length_px, width_px)/ppm
            except Exception:
                length_m = 0; width_m = 0
            strips = int(np.ceil(width_m / roll_width))
            total_len = strips * length_m
            carpet = total_len
            if tile_area:
                tiles_needed = int(np.ceil(area_m2 / tile_area))

        out_results.append({'id': rid, 'area_m2': round(area_m2, 3) if area_m2 is not None else None,
                            'carpet_m2_including_waste': round(carpet, 3) if carpet is not None else None,
                            'tiles_needed': tiles_needed,
                            'polygon': poly})
        csv_lines.append(f"{rid},{area_m2 if area_m2 is not None else ''},{carpet if carpet is not None else ''},{tiles_needed if tiles_needed is not None else ''}")

    # save CSV
    out_csv = os.path.join(OUTPUT_DIR, 'corrections.csv')
    try:
        with open(out_csv, 'w', encoding='utf-8') as fh:
            fh.write('\n'.join(csv_lines))
        csv_url = os.path.join('static', 'output', 'corrections.csv')
    except Exception:
        csv_url = None

    return jsonify({'results': out_results, 'csv': csv_url})


@app.route('/optimize_orientations', methods=['POST'])
def optimize_orientations():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'missing json'}), 400
    rooms = data.get('rooms', [])
    # rooms: list of {id, length_m, width_m, roll_width}
    N = len(rooms)
    if N == 0:
        return jsonify({'rooms': []})

    # compute per-room options
    options = []
    for r in rooms:
        lid = r.get('id')
        length = float(r.get('length_m') or 0)
        width = float(r.get('width_m') or 0)
        roll = float(r.get('roll_width') or 3.66)
        # orientation A: strips = ceil(width/roll), strip_len = length
        strips_a = int(np.ceil(width / roll)) if roll > 0 else 0
        total_a = strips_a * length
        seams_a = max(0, strips_a - 1)
        # orientation B: strips = ceil(length/roll), strip_len = width
        strips_b = int(np.ceil(length / roll)) if roll > 0 else 0
        total_b = strips_b * width
        seams_b = max(0, strips_b - 1)
        options.append({'id': lid, 'length': length, 'width': width, 'roll': roll,
                        'A': {'strips': strips_a, 'strip_len': length, 'total_len': total_a, 'seams': seams_a},
                        'B': {'strips': strips_b, 'strip_len': width, 'total_len': total_b, 'seams': seams_b}})

    # brute force for small N
    best = None
    if N <= 16:
        # try all combinations
        for mask in range(1 << N):
            total_len = 0.0
            total_seams = 0
            for i in range(N):
                opt = options[i]
                chooseB = (mask >> i) & 1
                sel = opt['B'] if chooseB else opt['A']
                total_len += sel['total_len']
                total_seams += sel['seams']
            cand = (total_len, total_seams, mask)
            if best is None or (cand[0] < best[0]) or (cand[0] == best[0] and cand[1] < best[1]):
                best = cand
        chosen_mask = best[2]
    else:
        # greedy: choose per-room minimal total_len, break ties by seams
        chosen_mask = 0
        for i, opt in enumerate(options):
            a = opt['A']; b = opt['B']
            pickB = False
            if b['total_len'] < a['total_len'] or (b['total_len'] == a['total_len'] and b['seams'] < a['seams']):
                pickB = True
            if pickB:
                chosen_mask |= (1 << i)

    out_rooms = []
    for i, opt in enumerate(options):
        pickB = (chosen_mask >> i) & 1
        sel = opt['B'] if pickB else opt['A']
        out_rooms.append({'id': opt['id'], 'chosen': 'B' if pickB else 'A', 'strips': sel['strips'], 'strip_len': sel['strip_len'], 'total_len': sel['total_len'], 'seams': sel['seams']})

    total_len = sum(r['total_len'] for r in out_rooms)
    total_seams = sum(r['seams'] for r in out_rooms)
    return jsonify({'rooms': out_rooms, 'total_len': total_len, 'total_seams': total_seams})


if __name__ == "__main__":
    logger.info('Starting Flask app...')
    logger.info(f'Access at http://{Config.HOST}:{Config.PORT}/')
    app.run(debug=Config.DEBUG, host=Config.HOST, port=Config.PORT)
