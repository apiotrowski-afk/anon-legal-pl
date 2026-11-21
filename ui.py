#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui.py — lokalny UI do anonimizacji akt (Streamlit). 100% offline.

Wsad wielu plików naraz, zapis wyników (.txt) do wskazanego folderu.
Używa tej samej funkcji pseudonimizacji i czytnika PDF co CLI.

Uruchomienie (w aktywnym venv, w folderze ze skryptami):
  pip install streamlit
  streamlit run ui.py
"""
import os, re, json, tempfile
import streamlit as st
from anon_legal_pl.anonimizuj import pseudonimizuj, zbuduj_analizator
from anonimizuj import bielik_dopnij, wczytaj

try:
    from ocr import pdf_na_tekst
    PDF_OK = True
except Exception:
    PDF_OK = False

st.set_page_config(page_title="Anonimizacja akt", layout="wide")

@st.cache_resource(show_spinner=False)
def analizator(model):
    return zbuduj_analizator(model)

def anonimizuj_tekst(tekst, analyzer, prog, bielik_model=None):
    dodatkowe_osoby = bielik_dopnij(tekst, bielik_model) if bielik_model else ()
    wynik, mapa = pseudonimizuj(tekst, analyzer, prog, dodatkowe_osoby=dodatkowe_osoby)
    liczba = sum(1 for tag in re.findall(r"\[[A-Z_]+_\d+\]", wynik) if tag in mapa)
    return wynik, mapa, liczba

st.title("Anonimizacja akt — lokalnie")
st.caption("Wszystko liczy się na tym komputerze. Wynik to pierwsze przejście — "
           "przejrzyj go, zanim użyjesz.")

with st.sidebar:
    st.header("Ustawienia")
    model = st.text_input("Model spaCy", "pl_core_news_lg")
    prog = st.slider("Próg pewności (recall ↔ szum)", 0.0, 1.0, 0.4, 0.05)
    out_dir = st.text_input("Folder na wyniki", os.path.join(os.getcwd(), "wyniki"))
    zapisz_mape = st.checkbox("Zapisz też mapę  (UWAGA: zawiera PRAWDZIWE dane)", value=False)
    uzyj_bielika = st.checkbox("Dołóż Bielika (wymaga Ollamy)", value=False)
    bielik_model = None
    if uzyj_bielika:
        bielik_model = st.text_input("Model Ollama",
                                     "SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M")
    if not PDF_OK:
        st.info("PDF wyłączony — brak PyMuPDF. Włącz: pip install pymupdf")

typy = ["txt", "docx"] + (["pdf"] if PDF_OK else [])
pliki = st.file_uploader("Wrzuć pliki (" + ", ".join("." + t for t in typy) + ")",
                         type=typy, accept_multiple_files=True)

if pliki and st.button("Anonimizuj", type="primary"):
    try:
        os.makedirs(out_dir, exist_ok=True)
    except Exception as e:
        st.error(f"Nie mogę utworzyć folderu wyjściowego: {e}"); st.stop()

    analyzer = analizator(model)
    podsumowanie = []
    for i, plik in enumerate(pliki):
        suf = os.path.splitext(plik.name)[1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suf) as tf:
            tf.write(plik.getvalue()); tmp = tf.name
        tekst, blad = None, None
        try:
            with st.spinner(f"Czytam: {plik.name}…"):
                tekst = pdf_na_tekst(tmp) if suf == ".pdf" else wczytaj(tmp)
        except RuntimeError as e:
            blad = str(e)
        finally:
            os.unlink(tmp)  # nie zostawiamy kopii danych klienta na dysku

        if blad:
            podsumowanie.append({"plik": plik.name, "status": "BŁĄD",
                                 "fragmentów": "-", "zapisano": blad})
            continue

        with st.spinner(f"Anonimizuję: {plik.name}…"):
            wynik, mapa, n = anonimizuj_tekst(tekst, analyzer, prog, bielik_model)

        stem = os.path.splitext(plik.name)[0]
        sciezka_txt = os.path.join(out_dir, f"{stem}_anon.txt")
        with open(sciezka_txt, "w", encoding="utf-8") as f:
            f.write(wynik)
        if zapisz_mape:
            with open(os.path.join(out_dir, f"{stem}_mapa.json"), "w", encoding="utf-8") as f:
                json.dump(mapa, f, ensure_ascii=False, indent=2)

        podsumowanie.append({"plik": plik.name, "status": "OK",
                             "fragmentów": n, "zapisano": sciezka_txt})
        with st.expander(f"Podgląd: {plik.name}  —  wykryto {n}"):
            c1, c2 = st.columns(2)
            c1.text_area("o", tekst, height=320, label_visibility="collapsed", key=f"o{i}")
            c2.text_area("w", wynik, height=320, label_visibility="collapsed", key=f"w{i}")

    st.success(f"Gotowe. Zapisano do: {out_dir}")
    st.dataframe(podsumowanie, width="stretch")
    if zapisz_mape:
        st.warning("Pliki *_mapa.json zawierają PRAWDZIWE dane (odwzorowanie tagów). "
                   "Trzymaj je jak oryginalne akta albo skasuj po użyciu.")
    st.warning("Przejrzyj wyniki ręcznie — recall nigdy nie jest pełny (tajemnica zawodowa).")
