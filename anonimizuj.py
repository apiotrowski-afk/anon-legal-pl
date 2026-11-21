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
import argparse
import json
import sys
from pathlib import Path

from anon_legal_pl.anonimizuj import pseudonimizuj, zbuduj_analizator

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
    dodatkowe_osoby = bielik_dopnij(tekst, a.bielik) if a.bielik else ()
    wynik, mapa = pseudonimizuj(tekst, analyzer, a.prog, dodatkowe_osoby=dodatkowe_osoby)

    Path(a.wyjscie).write_text(wynik, encoding="utf-8")
    Path(a.mapa).write_text(json.dumps(mapa, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {a.wyjscie} | mapa: {a.mapa}")
    print(">>> PRZEJRZYJ wynik RĘCZNIE. Recall nigdy nie jest pełny (tajemnica zawodowa).")

if __name__ == "__main__":
    main()
