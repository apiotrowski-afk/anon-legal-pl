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
import sys

from anon_legal_pl.ocr import pdf_na_tekst


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
