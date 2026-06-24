#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
anonimizuj.py — LOKALNA anonimizacja akt (PL). 100% offline.

Warstwa 1 (zawsze): Presidio + polskie rozpoznawacze z sumą kontrolną
  (PESEL, NIP, REGON), IBAN/sygnatura/nr umowy po formacie, oraz spaCy NER
  (osoby, adresy, podmioty — łapie nazwiska w odmianie).
Warstwa 2 (opcja --bielik): lokalny LLM przez Ollamę dopina osoby/adresy,
  których NER nie złapał.

Pseudonimizacja: spójne tagi ([OSOBA_1], [PESEL_1] ...) + mapa do odwrócenia,
żebyś mógł zmapować odpowiedź modelu z powrotem na realne dane.

UWAGA: wynik ZAWSZE wymaga przeglądu przez prawnika. Recall nigdy nie jest
pełny — to narzędzie pierwszego przejścia, nie ostatniego.

Użycie:
  python anonimizuj.py akta.docx wynik.txt
  python anonimizuj.py akta.txt  wynik.txt --bielik SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M
"""
import re, sys, json, argparse
from pathlib import Path

# ───────────────────────── walidatory (zweryfikowane) ─────────────────────────
def _d(s): return re.sub(r"\D", "", s)

def pesel_ok(p):
    p = _d(p)
    if len(p) != 11 or len(set(p)) == 1:
        return False
    w = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]
    return (10 - sum(int(p[i]) * w[i] for i in range(10)) % 10) % 10 == int(p[10])

def nip_ok(n):
    n = _d(n)
    if len(n) != 10 or len(set(n)) == 1:
        return False
    w = [6, 5, 7, 2, 3, 4, 5, 6, 7]
    s = sum(int(n[i]) * w[i] for i in range(9)) % 11
    return s != 10 and s == int(n[9])

def regon_ok(r):
    r = _d(r)
    if len(r) not in (9, 14) or len(set(r)) == 1:
        return False
    if len(r) == 9:
        w = [8, 9, 2, 3, 4, 5, 6, 7]
        s = sum(int(r[i]) * w[i] for i in range(8)) % 11
        return (0 if s == 10 else s) == int(r[8])
    w = [2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8]
    s = sum(int(r[i]) * w[i] for i in range(13)) % 11
    return (0 if s == 10 else s) == int(r[13])

# ───────────────────────── Presidio: analizator PL ─────────────────────────
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_analyzer.nlp_engine import NlpEngineProvider

class Walidowany(PatternRecognizer):
    """Pattern + suma kontrolna. Poprawna suma -> wynik 1.0.
    Brak/zła suma -> zwracam None (zostawiam wynik wzorca; recall > precyzja)."""
    def __init__(self, entity, patterns, walidator, context=None):
        super().__init__(supported_entity=entity, patterns=patterns,
                         context=context, supported_language="pl")
        self._w = walidator
    def validate_result(self, pattern_text):
        return True if self._w(pattern_text) else None

def zbuduj_analizator(model="pl_core_news_lg"):
    # Polski spaCy używa etykiet persName/placeName/geogName/orgName/date — NIE
    # OntoNotes (PERSON/GPE). Bez tego mapowania NER nie zadziała. Gdyby Twoja
    # wersja Presidio różniła się składnią, sprawdź docs: "Customizing the NLP models".
    conf = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "pl", "model_name": model}],
        "ner_model_configuration": {
            "model_to_presidio_entity_mapping": {
                "persName": "PERSON",
                "placeName": "LOCATION",
                "geogName": "LOCATION",
                "orgName": "ORGANIZATION",
                
            },
        },
    }
    nlp = NlpEngineProvider(nlp_configuration=conf).create_engine()
    a = AnalyzerEngine(nlp_engine=nlp, supported_languages=["pl"])

    # 11 cyfr są na tyle charakterystyczne, że redaguję zawsze (też zepsute OCR-em).
    a.registry.add_recognizer(Walidowany(
        "PL_PESEL", [Pattern("pesel", r"\b\d{11}\b", 0.4)], pesel_ok,
        context=["pesel", "ur", "urodzon"]))
    # NIP/REGON: bare numer redaguję tylko przy poprawnej sumie LUB słowie-kontekście,
    # inaczej zalałoby Cię każdy 9/10-cyfrowy ciąg.
    a.registry.add_recognizer(Walidowany(
        "PL_NIP", [Pattern("nip", r"\b\d{3}-?\d{3}-?\d{2}-?\d{2}\b|\b\d{10}\b", 0.05)],
        nip_ok, context=["nip"]))
    a.registry.add_recognizer(Walidowany(
        "PL_REGON", [Pattern("regon", r"\b\d{14}\b|\b\d{9}\b", 0.05)],
        regon_ok, context=["regon"]))
    # IBAN i sygnatura — po formacie, bez sumy kontrolnej (dla redakcji to bezpieczniejsze).
    a.registry.add_recognizer(PatternRecognizer(
        supported_entity="PL_IBAN", supported_language="pl",
        patterns=[Pattern("iban", r"\bPL\d{2}(?:[ ]?\d{4}){6}\b|\bPL\d{26}\b", 0.6)],
        context=["rachunek", "konto", "iban", "nr rachunku"]))
    a.registry.add_recognizer(PatternRecognizer(
        supported_entity="PL_SYGN", supported_language="pl",
        patterns=[Pattern("sygn", r"\b[IVXLC]+\s+[A-Z][a-zA-Z]{0,3}\s+\d+/\d{2,4}\b", 0.45)],
        context=["sygn", "sygnatura", "akt"]))
    a.registry.add_recognizer(PatternRecognizer(
        supported_entity="PL_ADRES", supported_language="pl",
        patterns=[Pattern("ulica",
            r"\b(?:ul\.|ulica|al\.|aleja|pl\.|plac|os\.|osiedle)\s+"
            r"[A-ZĄĆĘŁŃÓŚŹŻ][\wąćęłńóśźż]+(?:\s+\d{1,4}[A-Za-z]?(?:/\d+)?)?", 0.6)]))
    # daty i telefony zostawiamy widoczne — zdejmujemy domyślne rozpoznawacze,
    # które je łapią (PhoneRecognizer strzela w polski format daty typu 03.06.2026)
    for _nazwa in ("DateRecognizer", "PhoneRecognizer"):
        try:
            a.registry.remove_recognizer(_nazwa)
        except Exception:
            pass
    return a
    

# ───────────────────────── warstwa LLM (Bielik / Ollama) ─────────────────────────
def bielik_dopnij(tekst, model, url="http://localhost:11434/api/generate"):
    import urllib.request
    prompt = (
        "Wypisz DOSŁOWNIE, każdą w osobnej linii, wszystkie dane osobowe z tekstu: "
        "imiona, nazwiska oraz pełne adresy (ulica, numer, miasto). Tylko te ciągi — "
        "bez numeracji, bez komentarza, dokładnie tak jak w tekście. Brak danych -> pusto.\n\n"
        "TEKST:\n" + tekst
    )
    body = json.dumps({"model": model, "prompt": prompt, "stream": False,
                       "options": {"temperature": 0}}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            odp = json.loads(r.read().decode("utf-8")).get("response", "")
    except Exception as e:
        print(f"[bielik] pominięto: {e}. Czy Ollama działa? Uruchom: ollama serve", file=sys.stderr)
        return []
    out = []
    for ln in odp.splitlines():
        s = ln.strip(" -•*\t")
        if len(s) >= 3 and s in tekst:
            out.append(s)
    return out

# ───────────────────────── wejście / wyjście ─────────────────────────
def wczytaj(p):
    p = Path(p)
    if p.suffix.lower() == ".docx":
        from docx import Document
        return "\n".join(par.text for par in Document(str(p)).paragraphs)
    return p.read_text(encoding="utf-8")

ETYK = {"PERSON": "OSOBA", "LOCATION": "ADRES", "ORGANIZATION": "PODMIOT",
        "PL_PESEL": "PESEL", "PL_NIP": "NIP", "PL_REGON": "REGON",
        "PL_IBAN": "RACHUNEK", "PL_SYGN": "SYGN", "PL_ADRES": "ULICA",
        "DATE_TIME": "DATA"}

def main():
    ap = argparse.ArgumentParser(description="Lokalna anonimizacja akt (PL).")
    ap.add_argument("wejscie", help="plik .txt lub .docx")
    ap.add_argument("wyjscie", help="plik wynikowy .txt")
    ap.add_argument("--mapa", default="mapa.json", help="plik z mapą tag->oryginał")
    ap.add_argument("--model", default="pl_core_news_lg", help="model spaCy (lg/md/sm)")
    ap.add_argument("--prog", type=float, default=0.4, help="próg pewności (recall vs szum)")
    ap.add_argument("--bielik", metavar="MODEL_OLLAMA", default=None,
                    help="np. SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M")
    a = ap.parse_args()

    tekst = wczytaj(a.wejscie)

    analyzer = zbuduj_analizator(a.model)
    wyniki = analyzer.analyze(text=tekst, language="pl", score_threshold=a.prog)
    spans = [(r.start, r.end, r.entity_type) for r in wyniki]

    if a.bielik:
        for frag in set(bielik_dopnij(tekst, a.bielik)):
            for m in re.finditer(re.escape(frag), tekst):
                spans.append((m.start(), m.end(), "PERSON"))

    # scalanie nakładek: dłuższy fragment wygrywa
    spans = sorted(set(spans), key=lambda x: (x[0], -(x[1] - x[0])))
    scalone, ostatni = [], -1
    for s, e, t in spans:
        if s >= ostatni:
            scalone.append((s, e, t)); ostatni = e

    # pseudonimizacja: ten sam tekst -> ten sam tag
    licznik, mapa, pseudo = {}, {}, {}
    def tag(txt, typ):
        if txt in pseudo:
            return pseudo[txt]
        licznik[typ] = licznik.get(typ, 0) + 1
        et = ETYK.get(typ, typ)
        t = f"[{et}_{licznik[typ]}]"
        pseudo[txt] = t; mapa[t] = txt
        return t

    # podmiana OD KOŃCA — offsety się nie psują
    wynik = tekst
    for s, e, typ in sorted(scalone, key=lambda x: -x[0]):
        wynik = wynik[:s] + tag(tekst[s:e], typ) + wynik[e:]

    Path(a.wyjscie).write_text(wynik, encoding="utf-8")
    Path(a.mapa).write_text(json.dumps(mapa, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {a.wyjscie} | mapa: {a.mapa} | wykryto fragmentów: {len(scalone)}")
    print(">>> PRZEJRZYJ wynik RĘCZNIE. Recall nigdy nie jest pełny (tajemnica zawodowa).")

if __name__ == "__main__":
    main()
