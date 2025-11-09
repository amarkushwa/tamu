#!/usr/bin/env python3
"""
System Test Script

Verifies that all components are properly installed and configured.
Run this script before starting the main application.
"""
import sys
from pathlib import Path

def test_imports():
    """Test that all required packages can be imported"""
    print("Testing imports...")

    required_packages = [
        ('google.generativeai', 'Gemini API'),
        ('elevenlabs', 'ElevenLabs TTS'),
        ('solana', 'Solana SDK'),
        ('flask', 'Flask'),
        ('PIL', 'Pillow'),
        ('fitz', 'PyMuPDF'),
        ('PyPDF2', 'PyPDF2'),
        ('pytesseract', 'Tesseract Python'),
    ]

    failed = []
    for package, name in required_packages:
        try:
            __import__(package)
            print(f"  ✓ {name}")
        except ImportError as e:
            print(f"  ✗ {name} - FAILED: {e}")
            failed.append(name)

    if failed:
        print(f"\n❌ Missing packages: {', '.join(failed)}")
        print("Run: pip install -r requirements.txt")
        return False

    print("✅ All imports successful\n")
    return True

def test_tesseract():
    """Test Tesseract OCR installation"""
    print("Testing Tesseract OCR...")
    try:
        import pytesseract
        version = pytesseract.get_tesseract_version()
        print(f"  ✓ Tesseract version: {version}")
        print("✅ Tesseract OCR is installed\n")
        return True
    except Exception as e:
        print(f"  ✗ Tesseract not found: {e}")
        print("  Install Tesseract: https://github.com/tesseract-ocr/tesseract")
        return False

def test_config():
    """Test configuration and API keys"""
    print("Testing configuration...")
    try:
        sys.path.insert(0, str(Path(__file__).parent / 'src'))
        from src.config import Config

        checks = [
            ('GEMINI_API_KEY', Config.GEMINI_API_KEY),
            ('ELEVENLABS_API_KEY', Config.ELEVENLABS_API_KEY),
            ('SOLANA_CLUSTER_URL', Config.SOLANA_CLUSTER_URL),
        ]

        for name, value in checks:
            if value:
                masked = value[:8] + '...' if len(value) > 8 else '***'
                print(f"  ✓ {name}: {masked}")
            else:
                print(f"  ✗ {name}: NOT SET")
                return False

        print("✅ Configuration loaded successfully\n")
        return True
    except Exception as e:
        print(f"  ✗ Configuration error: {e}")
        return False

def test_directories():
    """Test that required directories exist"""
    print("Testing directories...")
    base_dir = Path(__file__).parent

    required_dirs = [
        'data/uploads',
        'data/cache',
        'data/audit_logs',
        'policies',
        'templates',
        'src',
    ]

    for dir_path in required_dirs:
        full_path = base_dir / dir_path
        if full_path.exists():
            print(f"  ✓ {dir_path}")
        else:
            print(f"  ✗ {dir_path} - MISSING")
            return False

    print("✅ All directories exist\n")
    return True

def test_policies():
    """Test that policy files exist"""
    print("Testing policy files...")
    base_dir = Path(__file__).parent

    policy_files = [
        'policies/categories.json',
        'policies/pii_patterns.json',
        'policies/few_shot_examples.json',
    ]

    for file_path in policy_files:
        full_path = base_dir / file_path
        if full_path.exists():
            print(f"  ✓ {file_path}")
        else:
            print(f"  ✗ {file_path} - MISSING")
            return False

    print("✅ All policy files exist\n")
    return True

def main():
    """Run all tests"""
    print("="*60)
    print("Gemini Document Classifier - System Test")
    print("="*60 + "\n")

    tests = [
        test_imports,
        test_tesseract,
        test_config,
        test_directories,
        test_policies,
    ]

    results = [test() for test in tests]

    print("="*60)
    if all(results):
        print("✅ ALL TESTS PASSED")
        print("="*60)
        print("\nYou can now start the application:")
        print("  python main.py")
        print("\nOr run the web server:")
        print("  python -m src.ui.app")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("="*60)
        print("\nPlease fix the errors above before running the application.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
