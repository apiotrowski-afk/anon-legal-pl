# anon-legal-pl

**Local-first PII anonymizer for Polish legal documents — built on [Microsoft Presidio](https://github.com/microsoft/presidio) + spaCy, with Polish-specific recognizers, an optional local-LLM pass, and built-in OCR. 100% offline.**

**Lokalna anonimizacja akt prawnych (PL) — na bazie [Microsoft Presidio](https://github.com/microsoft/presidio) + spaCy, z polskimi rozpoznawaczami, opcjonalnym dopięciem lokalnego LLM-a i wbudowanym OCR. 100% offline — żadne dane nie opuszczają Twojej maszyny.**

> ⚠️ Wynik **zawsze** wymaga przeglądu przez prawnika. Recall nigdy nie jest pełny — to narzędzie *pierwszego* przejścia, nie ostatniego.

---

## Co dokłada na bazie Presidio

Presidio daje framework wykrywania PII; tutaj jest **dostrojony pod polskie akta prawne**:

- ✅ **Polskie identyfikatory z sumą kontrolną** — PESEL / NIP / REGON (walidacja checksum → mniej fałszywych trafień niż goły regex).
- ⚖️ **Wzorce prawnicze** — sygnatura akt, numer umowy, IBAN, obok osób/adresów/podmiotów.
- 🧠 **spaCy NER** (`pl_core_news_lg`) — łapie nazwiska i adresy **w odmianie**.
- 🇵🇱 **Opcjonalny drugi przebieg LLM** — [Bielik](https://huggingface.co/speakleash) (polski model) lokalnie przez **Ollamę**, dopina osoby/adresy, których NER nie złapał.
- 📄 **OCR wbudowany** — PDF z warstwą tekstową czytany wprost (PyMuPDF), skany przez Tesseract (`pol`), z auto-korektą orientacji (OSD).
- 🔁 **Pseudonimizacja odwracalna** — spójne tagi (`[OSOBA_1]`, `[PESEL_1]`…) + mapa `tag → oryginał`, dzięki czemu odpowiedź modelu zmapujesz z powrotem na realne dane.

---

## Instalacja

```bash
pip install presidio-analyzer spacy python-docx
python -m spacy download pl_core_news_lg

# OCR (skany PDF) — opcjonalnie:
pip install pymupdf pytesseract pillow
#  + Tesseract z danymi 'pol' i 'osd' (Windows: build UB-Mannheim; Linux: apt install tesseract-ocr tesseract-ocr-pol)

# UI (opcjonalnie):
pip install streamlit

# Drugi przebieg LLM (opcjonalnie): zainstaluj Ollamę i pobierz model Bielik
```

Lub: `pip install -r requirements.txt`.

## Użycie

**CLI:**
```bash
python anonimizuj.py akta.docx wynik.txt
python anonimizuj.py akta.txt  wynik.txt --bielik SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M
python ocr.py skan.pdf akta.txt            # PDF/skan → tekst (OCR offline)
```
Flagi: `--mapa` (plik mapy do odwrócenia), `--model` (spaCy lg/md/sm), `--prog` (próg pewności recall vs szum), `--bielik` (model Ollama).

**UI (Streamlit, wsad wielu plików):**
```bash
streamlit run ui.py
```

> Ścieżka do Tesseracta: ustaw `TESSERACT_CMD` (env), albo zostaw domyślną (Windows). Na Linux/macOS `tesseract` w PATH wystarcza.

## Built on / Stack

[Microsoft Presidio](https://github.com/microsoft/presidio) · [spaCy](https://spacy.io) (`pl_core_news_lg`) · [Bielik / SpeakLeash](https://huggingface.co/speakleash) przez [Ollama](https://ollama.com) · [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) · [PyMuPDF](https://pymupdf.readthedocs.io).

## Ekosystem / Related

Część zestawu otwartych narzędzi LegalTech (PL):
- **[legal-cite-pl](https://github.com/apiotrowski-afk/legal-cite-pl)** — MCP: weryfikacja brzmienia przepisu PL/UE ze źródła.
- **[commercial-legal-pl](https://github.com/apiotrowski-afk/commercial-legal-pl)** — Claude skill: redakcja i analiza umów (PL).
- **[anon-legal-pl](https://github.com/apiotrowski-afk/anon-legal-pl)** — *(ten projekt)* lokalna anonimizacja akt prawnych (PL).
- **[kancelaria-dms](https://github.com/apiotrowski-afk/kancelaria-dms)** — DMS/CRM dla kancelarii (Google Workspace).

## Licencja

Apache License 2.0 — zob. [LICENSE](LICENSE). (Presidio: MIT; spaCy: MIT — zachowaj ich noty przy redystrybucji.)
