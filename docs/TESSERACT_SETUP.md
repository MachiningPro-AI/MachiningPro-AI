# Tesseract OCR Setup (P3-C)

MachiningPro AI includes an OCR extraction pipeline for raster PDF engineering
drawings. The pipeline is built and wired — it only requires the Tesseract
binary to be installed on the system running the backend.

**HARD RULES (unchanged):**
- OCR results are always tagged `source=OCR`, never `source=NATIVE_TEXT`.
- No OCR result is auto-confirmed as engineering data.
- An engineer must review and confirm every OCR-extracted value before it flows
  downstream to process planning.

---

## 1. Install the Python package (optional dependency)

```bash
pip install "machiningpro-ai[ocr]"
# or, if working from source:
pip install pytesseract>=0.3.13,<0.4
```

## 2. Install the Tesseract binary

### Windows (development)

Download the official Windows installer from:
https://github.com/UB-Mannheim/tesseract/wiki

Recommended version: **5.3.x** (64-bit).

Default install path: `C:\Program Files\Tesseract-OCR\tesseract.exe`

After installation, configure the path in the backend startup:

```python
# In your startup script or environment config:
from backend.interoperability.hybrid_pdf_drawing import configure_tesseract_path
configure_tesseract_path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
```

Or set the environment variable `TESSERACT_CMD` and configure it at startup.

### Linux / Docker (production / Render)

Install via the system package manager:

```bash
# Debian / Ubuntu
apt-get install -y tesseract-ocr tesseract-ocr-deu tesseract-ocr-tur

# Alpine
apk add tesseract-ocr
```

The binary is then at `/usr/bin/tesseract` (default path; no `configure_tesseract_path` call needed).

For Render.com deployments, add the following to your `render.yaml` build command:

```yaml
buildCommand: "apt-get install -y tesseract-ocr && pip install 'machiningpro-ai[ocr]'"
```

## 3. Verify installation

After installing, run:

```bash
python -c "
from backend.interoperability.hybrid_pdf_drawing import PYTESSERACT_AVAILABLE, get_tesseract_path
print('pytesseract available:', PYTESSERACT_AVAILABLE)
print('tesseract path:', get_tesseract_path() or '(system PATH)')
import pytesseract; print(pytesseract.get_tesseract_version())
"
```

Expected output:
```
pytesseract available: True
tesseract path: (system PATH)
5.3.x
```

## 4. What activates

When Tesseract is installed and `pytesseract` is importable:

- `PYTESSERACT_AVAILABLE = True`
- Stage 3 (OCR fallback) in `extract_hybrid_pdf()` becomes active for
  raster regions in PDF drawings.
- `FILES_DRAWING_INTELLIGENCE_READY` advances from 5 → 8 for the three
  real sample PDF files (PDF-01, PDF-02, PDF-03).

The OCR results appear in `HybridPdfExtractionResult.ocr_tokens`.
They are NOT auto-confirmed. The engineer must review them in the
OCR Review Panel before they flow to process planning.

## 5. OCR languages

Tesseract is configured to use English by default. For drawings with
German or Turkish annotations, install the language packs:

```bash
# Debian/Ubuntu
apt-get install -y tesseract-ocr-deu tesseract-ocr-tur
```

The pipeline will then apply multi-language OCR where the content type
indicates non-English annotation blocks.
