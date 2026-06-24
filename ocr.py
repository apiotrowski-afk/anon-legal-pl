#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ocr.py — LOKALNA ekstrakcja tekstu z PDF do .txt, oraz funkcja pdf_na_tekst()
do użycia z ui.py. 100% offline.

Strona z warstwą tekstową -> czytana wprost (sam PyMuPDF, bez Tesseractu).
Strona-skan               -> OCR przez Tesseract (język polski).
Skan obrócony             -> auto-wykrycie orientacji (OSD) i obrót przed OCR.

Zależności: pip install pymupdf            (PDF natywny — wystarczy)
            pip install pytesseract pillow  + Tesseract z danymi 'pol' i 'osd' (skany)

CLI:  python ocr.py akta.pdf akta.txt
"""
import os, io, sys

# Ścieżka do Tesseracta: env TESSERACT_CMD ma priorytet; w innym razie typowa
# instalacja na Windows (Linux/macOS zwykle mają `tesseract` w PATH — wtedy
# pytesseract znajdzie go sam i ta ścieżka nie jest używana).
_TESS_CMD = os.environ.get("TESSERACT_CMD") or r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def _ocr_strony(page, dpi):
    try:
        import pytesseract
        from PIL import Image
    except ImportError as e:
        raise RuntimeError(
            "Strona jest skanem i wymaga OCR, ale brakuje pytesseract/Pillow. "
            "Zainstaluj: pip install pytesseract pillow"
        ) from e
    if os.path.exists(_TESS_CMD):
        pytesseract.pytesseract.tesseract_cmd = _TESS_CMD

    try:
        pix = page.get_pixmap(dpi=dpi)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
    except Exception as e:
        raise RuntimeError(
            "OCR nie zadziałał — najpewniej brak silnika Tesseract lub danych 'pol'. "
            "Zainstaluj Tesseract (build UB-Mannheim) z polskim."
        ) from e

    # auto-korekta orientacji: obrócony skan psuje OCR. OSD wykrywa kąt, obracamy.
    try:
        osd = pytesseract.image_to_osd(img, output_type=pytesseract.Output.DICT)
        kat = int(osd.get("rotate", 0))
        if kat:
            img = img.rotate(-kat, expand=True)
    except Exception:
        pass  # OSD bywa zawodny przy małej ilości tekstu — wtedy OCR bez obracania

    try:
        return pytesseract.image_to_string(img, lang="pol")
    except Exception as e:
        raise RuntimeError(
            "OCR nie zadziałał — sprawdź instalację Tesseracta i danych języka 'pol'."
        ) from e

def pdf_na_tekst(path, dpi=300, prog_tekstu=30):
    """Zwraca tekst z PDF. Strony z warstwą tekstową wprost, skany przez OCR
    (z auto-korektą orientacji). Rzuca RuntimeError z czytelnym komunikatem,
    gdy skan wymaga OCR, a brak narzędzi."""
    import fitz  # PyMuPDF
    doc = fitz.open(path)
    czesci = []
    for i, page in enumerate(doc, 1):
        t = page.get_text().strip()
        if len(t) >= prog_tekstu:
            czesci.append(t)
            print(f"strona {i}/{len(doc)}: warstwa tekstowa", file=sys.stderr)
        else:
            czesci.append(_ocr_strony(page, dpi))
            print(f"strona {i}/{len(doc)}: OCR", file=sys.stderr)
    return "\n\n".join(czesci)

def main():
    if len(sys.argv) != 3:
        sys.exit("Użycie: python ocr.py wejscie.pdf wyjscie.txt")
    we, wy = sys.argv[1], sys.argv[2]
    tekst = pdf_na_tekst(we)
    with open(wy, "w", encoding="utf-8") as f:
        f.write(tekst)
    print(f"OK: {wy}")

if __name__ == "__main__":
    main()