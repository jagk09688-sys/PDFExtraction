"""Simple smoke tests to verify the app can start and basic functions work."""

import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(__file__))

def test_imports():
    """Test that all required modules can be imported."""
    try:
        import flask
        import cv2
        import numpy as np
        from PIL import Image
        from shapely.geometry import Polygon
        print("✓ All required imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False


def test_config():
    """Test that configuration loads."""
    try:
        from config import Config
        print(f"✓ Config loaded: PDF_DPI={Config.PDF_DPI}, PORT={Config.PORT}")
        return True
    except Exception as e:
        print(f"✗ Config error: {e}")
        return False


def test_app_creation():
    """Test that Flask app can be created."""
    try:
        from app import app
        assert app is not None
        print("✓ Flask app created successfully")
        return True
    except Exception as e:
        print(f"✗ App creation error: {e}")
        return False


def test_app_routes():
    """Test that basic routes exist."""
    try:
        from app import app
        
        # Check that routes are registered
        routes = [rule.rule for rule in app.url_map.iter_rules()]
        expected_routes = ['/', '/extract', '/save_corrections', '/optimize_orientations']
        
        missing = [r for r in expected_routes if r not in routes]
        if missing:
            print(f"✗ Missing routes: {missing}")
            return False
        
        print(f"✓ All expected routes registered: {expected_routes}")
        return True
    except Exception as e:
        print(f"✗ Route check error: {e}")
        return False


def test_directories():
    """Test that required directories exist."""
    try:
        required_dirs = ['templates', 'static/output']
        missing = [d for d in required_dirs if not os.path.isdir(d)]
        
        if missing:
            print(f"✗ Missing directories: {missing}")
            print("  Run setup.bat to create them")
            return False
        
        print(f"✓ All required directories exist: {required_dirs}")
        return True
    except Exception as e:
        print(f"✗ Directory check error: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "="*50)
    print("PDF Extraction App - Smoke Tests")
    print("="*50 + "\n")
    
    tests = [
        ("Imports", test_imports),
        ("Configuration", test_config),
        ("App Creation", test_app_creation),
        ("App Routes", test_app_routes),
        ("Directories", test_directories),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\nTesting {name}...")
        result = test_func()
        results.append(result)
    
    print("\n" + "="*50)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    print("="*50 + "\n")
    
    if all(results):
        print("✓ All checks passed! App is ready to run.")
        print("  Double-click run.bat to start the server.")
        return 0
    else:
        print("✗ Some checks failed. See above for details.")
        print("  Run setup.bat to fix issues.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
