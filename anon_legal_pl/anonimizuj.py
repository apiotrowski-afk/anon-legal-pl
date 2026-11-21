# Modified for Odwołania2JSON. Upstream: anon-legal-pl, Apache-2.0.
"""Polish Presidio recognizers from anon-legal-pl."""

import re
from bisect import bisect_right
from collections.abc import Iterable

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

_ODSTEP = r"[^\S\r\n]*(?:\r?\n[^\S\r\n]*)?"
_DYZYWIZ = r"[-‐‑–]"
_ETYKIETA_RACHUNKU = (
    r"(?:(?:nr\.?|numer)\s+(?:rachunku|konta)|z\s+rachunku|na\s+rachunek|rachunek(?:\s+(?:źródłowy|docelowy|bankowy|"
    r"nadawcy|odbiorcy|płatnika|beneficjenta|zleceniodawcy|obciążany|uznawany))?)"
)
_IBAN_PL = (
    rf"(?<!\w)(?:PL{_ODSTEP})?\d{{2}}(?:{_ODSTEP}\d{{4}}){{6}}(?!\w)"
    rf"|(?<=\b{_ETYKIETA_RACHUNKU}{_ODSTEP}:?{_ODSTEP})(?:PL{_ODSTEP})?"
    rf"\d(?:{_ODSTEP}\d){{23}}(?!\w|{_ODSTEP}\d)"
)
_TED = rf"(?<![\w/-])(?:\d{{6,8}}{_DYZYWIZ}20\d{{2}}|20\d{{2}}\s*/\s*S\s*\d{{1,3}}\s*{_DYZYWIZ}\s*\d{{6,8}})(?![\w/-])"
_BZP = r"(?<![\w/-])20\d{2}\s*/\s*BZP\s*\d{8}(?:\s*/\s*\d{2}(?:\s*/\s*P)?)?(?![\w/-])"
_KOD_SPRAWY = r"(?=[A-Z0-9./-]*\d)[A-Z][A-Z0-9]*(?:[./-][A-Z0-9]+)+"
_ETYKIETA_SPRAWY = (
    r"(?:(?:nr\.?|numer)\s+(?:referencyjny(?:\s+sprawy)?|wewnętrzny|postępowania)"
    r"|(?:postępowani[eu]|przetargu)\s+nr\.?|w\s+przetargu|wewnętrzny\s+identyfikator|identyfikator\s+postępowania)"
)
_NUMER_SPRAWY = (
    r"(?<![\w./@-])(?:[A-Z]{1,10}\.){1,3}\d{1,5}(?:\.\d{1,5}){0,3}\.20\d{2}"
    r"(?:\.[A-Z]{1,6})?(?![\w/@-]|\.[A-Z0-9])"
    r"|(?<![\w./@-])(?-i:[A-Z]{2,12}(?:/[A-Z]{1,10}){0,2})/\d{1,8}/20\d{2}"
    r"(?![\w/@-]|\.[A-Z0-9])"
    rf"|(?<=\b{_ETYKIETA_SPRAWY}\s*:?\s*){_KOD_SPRAWY}(?![\w/-])"
)
_ETYKIETA_TRANSAKCJI = r"(?:nr\.?|numer|identyfikator)\s+(?:transakcji(?:\s+operacji)?|operacji(?:\s+bankowej)?)"
_NUMER_TRANSAKCJI = (
    r"\bCEN\d{13}\b"
    rf"|(?<=\b{_ETYKIETA_TRANSAKCJI}{_ODSTEP}:?{_ODSTEP})"
    r"(?!(?:\d{4}[./-]\d{2}[./-]\d{2}|\d{2}[./-]\d{2}[./-]\d{4})(?![\w/-]))"
    r"(?=[A-Z0-9._/-]*\d)[A-Z0-9]+(?:[._/-][A-Z0-9]+)*(?![\w/-])"
)
_SLOWO_PROPRIUM = r"(?-i:[A-ZĄĆĘŁŃÓŚŹŻ][^\W\d_]*(?:[-’'][A-ZĄĆĘŁŃÓŚŹŻ][^\W\d_]*)*)"
_MIASTO = rf"{_SLOWO_PROPRIUM}(?:[ \t]+(?:nad|pod|w|{_SLOWO_PROPRIUM})){{0,3}}"
_FORMA_PRAWNA = (
    r"\b(?:sp\.\s*(?:z\s+o\.\s*o\.?(?:\s+sp\.\s*k\.?)?|[kjp]\.?)|s\.\s*a\.?"
    r"|spółk[aiąę]\s+(?:z\s+ograniczoną\s+odpowiedzialnością|akcyjn[ąa]|komandytow[ąa]|jawn[ąa]))"
    r"(?!\w)"
)
# Nagłówki powinny pozostać czytelne także wtedy, gdy model rozpozna tylko ich część.
_ROLE = r"zamawiający|odwołujący|mocodawc[ay]|nadawca|adresat przelewu|płatnik|beneficjent|wykonawca|odbiorca|zleceniodawca"
_SLOWO_FIRMY = rf"(?!(?:{_ROLE}|adres|KRS|NIP|REGON|nr|numer|tytuł|zakres)\b){_SLOWO_PROPRIUM}"
_LACZNIK_FIRMY = r"(?-i:i|w|we|im\.|dr\.|prof\.)"
_CZESC_NAZWY = rf"(?:{_LACZNIK_FIRMY}|{_SLOWO_FIRMY})"
_NAZWA_FIRMY = rf"{_SLOWO_FIRMY}(?:\s+{_CZESC_NAZWY}){{0,9}}\s+{_FORMA_PRAWNA}"
_NAZWA_URZEDU = (
    rf"(?-i:Gmina|Powiat|Miasto|Centrum|Szpital|Zarząd|Zakład|Urząd|(?:Państwowa\s+)?Akademia|Uniwersytet|Politechnika)"
    rf"(?:\s+{_CZESC_NAZWY}){{0,9}}\s+{_SLOWO_FIRMY}"
)
_NAZWA_JDG = (
    rf"(?-i:[A-ZĄĆĘŁŃÓŚŹŻ]{{2,}}(?:-[A-ZĄĆĘŁŃÓŚŹŻ]{{2,}})+)"
    rf"\s+{_SLOWO_PROPRIUM}\s+{_SLOWO_PROPRIUM}"
)
_FIRMA = (
    rf"(?m)(?<=^[ \t]*|\b(?:{_ROLE}|oficjalna nazwa|nazwa)[ \t]*[:\r\n]\s*"
    r"|\b(?:przez|prowadzi|dla|oraz|mocodawcą\s+jest|w\s+imieniu(?:\s+wykonawcy)?|pod\s+firmą)\s+"
    r"|\b\d{1,2}\)[ \t]+)"
    rf"(?:{_NAZWA_FIRMY}|{_NAZWA_URZEDU}|{_NAZWA_JDG})"
    r"|(?<=\badres\s+do\s+korespondencji\s*:\s*)"
    rf"(?:{_NAZWA_FIRMY}|Kancelaria[^\r\n,:]{{2,90}}(?=,|\r?$))"
)
_TYTUL_ZAMOWIENIA = (
    r"(?m)(?<=\b(?:pn\.|pod\s+nazwą|postępowani[aeu]|zamówieni[aeu]|tytuł\s+zamówienia)"
    r"\s*:?\s*[„«])[^”»]{1,500}(?=[”»])"
    r"|(?<=^[ \t]*tytuł[ \t]*:[ \t]*)[^\r\n]+"
    r"(?:\r?\n(?![ \t]*[^\r\n:]{1,45}:)[^\r\n]+){0,3}?(?=\r?\n[ \t]*opis[ \t]*:)"
    r"|(?<=^[ \t]*tytuł zamówienia[ \t]*:[ \t]*)[^\r\n]+"
    r"(?:\r?\n(?![ \t]*(?:nr\b|numer\b|[^\r\n:]{1,45}:|$))[^\r\n]+){0,3}"
    r"|(?<=^[ \t]*postępowanie[ \t]*\r?\n)(?-i:[A-ZĄĆĘŁŃÓŚŹŻ])[^\r\n]+"
    r"(?:\r?\n(?![ \t]*(?:nr\b|numer\b|[^\r\n:]{1,45}:|$))[^\r\n]+){0,3}?"
    r"(?=\r?\n[ \t]*(?:nr\.?|numer)[ \t]+[A-Z0-9])"
)

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
        patterns=[Pattern("iban", _IBAN_PL, 1.0)],
        context=["rachunek", "konto", "iban", "nr rachunku"]))
    a.registry.add_recognizer(PatternRecognizer(
        supported_entity="PL_SYGN", supported_language="pl",
        patterns=[Pattern("sygn", r"\b[IVXLC]+\s+[A-Z][a-zA-Z]{0,3}\s+\d+/\d{2,4}\b", 0.45)],
        context=["sygn", "sygnatura", "akt"]))
    a.registry.add_recognizer(PatternRecognizer(
        supported_entity="PL_ADRES", supported_language="pl",
        patterns=[Pattern("ulica",
            r"\b(?:ul\.|ulica|al\.|aleja|pl\.|plac|os\.|osiedle)\s+"
            r"[^\W\d_][^\W\d_’-]*(?:(?:[ \t]+[^\W\d_][^\W\d_’-]*){0,4}"
            r"[ \t]+\d{1,4}[A-Za-z]?(?:/\d+)?(?![\w/-]))?", 0.6)]))
    # W polskich pismach etykieta rozróżnia telefon od daty i KRS od NIP-u.
    for typ, wzorzec in (
        ("PL_EMAIL", r"[\w.%+-]+@(?:[a-z0-9-]+\.)+[a-z]{2,}\b"),
        ("PL_TELEFON",
         r"(?<=\b(?:tel\.?|telefonu?|fax|faks)(?:[ \t]*/[ \t]*(?:fax|faks))?[ \t]*:?[ \t]*)"
         r"(?:\+\d(?:[ \t()-]*\d){7,14}|\(?\d{2}\)?(?:[ \t-]*\d){7})(?![ \t-]*\d)"),
        ("PL_KRS", r"(?<=\bKRS[ \t]*[:.]?[ \t]*(?:\n[ \t]*)?)\d{10}\b"),
        ("PL_KOD_POCZTOWY", r"(?<![\w-])\d{2}-\d{3}(?![\w-])"),
        ("PL_KLIENT", r"(?<=\b(?:nr|numer)[ \t]+klienta[ \t]*:?[ \t]*(?:\n[ \t]*)?)\d+\b"),
        ("PL_TRANSAKCJA", _NUMER_TRANSAKCJI),
        ("PL_NUMER_SPRAWY", _NUMER_SPRAWY),
        ("PL_TED", _TED),
        ("PL_BZP", _BZP),
        ("PL_NIP", rf"(?m)(?<=^[ \t]*{_MIASTO}\s*/\s*|\bNIP\s*:?\s*)\d{{10}}\b"),
        ("PL_MIEJSCOWOSC",
         rf"(?m)(?<=^[ \t]*miejscowość[ \t]*:[ \t]*|\b\d{{2}}-\d{{3}}\s+)"
         rf"{_MIASTO}(?=[ \t]*(?:[,;/]|$))"
         rf"|(?<=^[ \t]*){_MIASTO}(?=[ \t]*,[ \t]*(?:dnia\s+)?\d)"
         rf"|(?<=^[ \t]*){_MIASTO}(?=\s*/\s*\d{{10}}\b)"),
        ("PL_TYTUL_ZAMOWIENIA", _TYTUL_ZAMOWIENIA),
        ("PL_PODPIS",
         rf"(?m)(?<=^[ \t]*){_SLOWO_PROPRIUM}(?:[ \t]+{_SLOWO_PROPRIUM}){{1,2}}"
         r"(?=\s*\r?\n[ \t]*(?:(?:wice)?prezes|członek)[ \t]+zarządu\b|\s*\r?\n[ \t]*prokurent\b)"),
        ("PL_WPIS_ZAWODOWY",
         r"(?<=\b(?:nr\.?|numer)[ \t]+wpisu(?:[ \t]+na[ \t]+list[ęy]"
         r"(?:[ \t]+(?:adwokatów|radców[ \t]+prawnych))?)?[ \t]*:?[ \t]*(?:\n[ \t]*)?)"
         r"(?:[A-Z]{1,5}(?:[/-][A-Z]{1,5})*[ \t/-]*)?\d{2,}(?:[/-]\d+)?\b"),
        ("PL_FIRMA", _FIRMA),
    ):
        a.registry.add_recognizer(PatternRecognizer(
            supported_entity=typ, supported_language="pl", patterns=[Pattern(typ, wzorzec, 1.0)]
        ))
    # Ogólne rozpoznawacze Presidio brały daty w polskiej pisowni za telefony.
    for _nazwa in ("DateRecognizer", "PhoneRecognizer"):
        try:
            a.registry.remove_recognizer(_nazwa)
        except Exception:
            pass
    return a

ETYK = {"PERSON": "OSOBA", "LOCATION": "ADRES", "ORGANIZATION": "PODMIOT",
        "PL_PESEL": "PESEL", "PL_NIP": "NIP", "PL_REGON": "REGON",
        "PL_IBAN": "RACHUNEK", "PL_SYGN": "SYGN", "PL_ADRES": "ULICA",
        "PL_EMAIL": "EMAIL", "PL_TELEFON": "TELEFON", "PL_KRS": "KRS",
        "PL_KOD_POCZTOWY": "KOD_POCZTOWY", "PL_KLIENT": "NR_KLIENTA",
        "PL_TRANSAKCJA": "NR_TRANSAKCJI", "PL_WPIS_ZAWODOWY": "NR_WPISU",
        "PL_FIRMA": "PODMIOT", "PL_MIEJSCOWOSC": "ADRES",
        "PL_NUMER_SPRAWY": "NR_SPRAWY", "PL_TED": "NR_TED",
        "PL_TYTUL_ZAMOWIENIA": "TYTUL_ZAMOWIENIA", "PL_BZP": "NR_BZP", "PL_PODPIS": "OSOBA"}

_TYPY_NER = {"PERSON", "LOCATION", "ORGANIZATION"}
_FORMY_PRAWNE = re.compile(_FORMA_PRAWNA, re.IGNORECASE)
_POWTARZANE_POLA = {"PL_NUMER_SPRAWY", "PL_TYTUL_ZAMOWIENIA", "PL_FIRMA", "PL_NIP", "PL_TRANSAKCJA", "PL_IBAN"}
_FORMATY_JEDNOZNACZNE = {"PL_IBAN", "PL_TED", "PL_BZP", "PL_TRANSAKCJA", "PL_WPIS_ZAWODOWY"}
_NAGLOWKI = re.compile(
    rf"^[ \t]*(?:pełnomocnictwo[ \t]+)?(?P<chronione>{_ROLE}|pełnomocnik|tytuł(?: zamówienia)?"
    r"|kwota|identyfikator procedury|wewnętrzny identyfikator|nr klienta|data transakcji"
    rf"|{_ETYKIETA_SPRAWY}|{_ETYKIETA_TRANSAKCJI}|{_ETYKIETA_RACHUNKU}"
    r"|numer (?:publikacji )?ogłoszenia|KRS|NIP|REGON|miejscowość)(?=[ \t]*:|[ \t]*$)"
    r"|^[ \t]*(?P<numeracja>\d{1,2}(?:\.\d{1,2}){1,5}\.?)(?=[ \t]|$)",
    re.IGNORECASE | re.MULTILINE,
)

_ETYKIETY_DOKUMENTU = {
    "adw", "adwokat", "adres", "bank", "e-mail", "email", "fax", "kio", "krs",
    "mocodawca", "mocodawcy", "nip", "numer", "odwołujący", "odwołującego", "odwołującemu",
    "pełnomocnik", "pełnomocnicy", "radca prawny", "regon", "sp", "tel", "telefon",
    "ue", "ul", "wykonawca", "wykonawcy", "z o.o", "zamawiający", "zamawiającego",
    "zamawiającemu", "krajowa izba odwoławcza", "krajowej izby odwoławczej",
    "krajową izbą odwoławczą",
}


def _rozlaczne(zakresy):
    """Wybierz najdłuższy zakres przy wspólnym początku."""
    scalone, ostatni = [], -1
    # Jawna etykieta transakcji rozstrzyga również zgodność formatu z numerem rachunku.
    kolejnosc = sorted(
        set(zakresy),
        key=lambda x: (x[0], x[0] - x[1], x[2] != "PL_TRANSAKCJA", x[2] not in _FORMATY_JEDNOZNACZNE, x[2]),
    )
    for start, koniec, typ in kolejnosc:
        if start >= ostatni:
            scalone.append((start, koniec, typ))
            ostatni = koniec
    return scalone


def _wykluczenia_nlp(tekst, dokladne):
    chronione = [m.span(m.lastgroup) for m in _NAGLOWKI.finditer(tekst)]
    chronione.extend((start, koniec) for start, koniec, _ in dokladne)
    polaczone = []
    for start, koniec in sorted(chronione):
        if polaczone and start <= polaczone[-1][1]:
            polaczone[-1] = (polaczone[-1][0], max(koniec, polaczone[-1][1]))
        else:
            polaczone.append((start, koniec))
    return polaczone


def _poza_zakresami(start, koniec, typ, wykluczenia, konce):
    for i in range(bisect_right(konce, start), len(wykluczenia)):
        poczatek, kres = wykluczenia[i]
        if poczatek >= koniec:
            break
        if start < poczatek:
            yield start, poczatek, typ
        start = kres
    if start < koniec:
        yield start, koniec, typ


def _zakresy_nlp(tekst, start, koniec, typ, wykluczenia, konce):
    if typ == "ORGANIZATION":
        for forma in _FORMY_PRAWNE.finditer(tekst, start, min(len(tekst), koniec + 24)):
            if start < forma.start() <= koniec or tekst[koniec:forma.start()].isspace():
                koniec = max(koniec, forma.end())
                break

    # Dopasowanie modelu nie może przeciąć numeru lub ulicy wykrytych przez regułę.
    yield from _poza_zakresami(start, koniec, typ, wykluczenia, konce)


def _czyste_zakresy(tekst, zakresy, *, nlp=False):
    for start, koniec, typ in zakresy:
        wartosc = tekst[start:koniec]
        etykieta = " ".join(wartosc.casefold().split()).strip(".,:")
        if nlp and (etykieta in _ETYKIETY_DOKUMENTU or _FORMY_PRAWNE.fullmatch(wartosc.strip())):
            continue
        # Znacznik na każdą linię pozwala zachować łamanie tekstu i odtworzyć go z mapy.
        for linia in re.finditer(r"[^\r\n]+", wartosc):
            segment = linia[0]
            if segment.strip():
                lewy = start + linia.start() + len(segment) - len(segment.lstrip())
                prawy = start + linia.start() + len(segment.rstrip())
                yield lewy, prawy, typ


def _powtorzenia_pol(tekst, zakresy):
    """Rozpoznaj powtórzone wartości również wtedy, gdy PDF łamie je inaczej."""
    pola = {
        (typ, tuple(tekst[start:koniec].split()))
        for start, koniec, typ in zakresy if typ in _POWTARZANE_POLA
    }
    for typ, slowa in pola:
        wzorzec = r"\s+".join(map(re.escape, slowa))
        for trafienie in re.finditer(rf"(?<!\w){wzorzec}(?!\w)", tekst, re.IGNORECASE):
            yield trafienie.start(), trafienie.end(), typ


def pseudonimizuj(
    tekst: str, analyzer: AnalyzerEngine, prog: float = 0.4, *, dodatkowe_osoby: Iterable[str] = (),
) -> tuple[str, dict[str, str]]:
    """Return the full text with markers and the original value for each marker."""
    model = analyzer.nlp_engine.nlp["pl"]
    model.max_length = max(model.max_length, len(tekst) + 1)
    wyniki = analyzer.analyze(text=tekst, language="pl", entities=list(ETYK), score_threshold=prog)
    zakresy_regul = [(r.start, r.end, r.entity_type) for r in wyniki if r.entity_type not in _TYPY_NER]
    dokladne = _rozlaczne([*zakresy_regul, *_powtorzenia_pol(tekst, zakresy_regul)])
    wykluczenia = _wykluczenia_nlp(tekst, dokladne)
    konce = [koniec for _, koniec in wykluczenia]
    zakresy_nlp = [(r.start, r.end, r.entity_type) for r in wyniki if r.entity_type in _TYPY_NER]
    for osoba in set(dodatkowe_osoby):
        if osoba:
            zakresy_nlp.extend(
                (trafienie.start(), trafienie.end(), "PERSON")
                for trafienie in re.finditer(re.escape(osoba), tekst)
            )
    nlp = (
        zakres for start, koniec, typ in zakresy_nlp
        for zakres in _zakresy_nlp(tekst, start, koniec, typ, wykluczenia, konce)
    )
    scalone = sorted([
        *_czyste_zakresy(tekst, dokladne),
        *_rozlaczne(_czyste_zakresy(tekst, nlp, nlp=True)),
    ])

    licznik, mapa, pseudo = {}, {}, {}

    def tag(txt, typ):
        et = ETYK[typ]
        if (et, txt) in pseudo:
            return pseudo[et, txt]
        licznik[et] = licznik.get(et, 0) + 1
        t = f"[{et}_{licznik[et]}]"
        pseudo[et, txt] = t
        mapa[t] = txt
        return t

    fragmenty, ostatni = [], 0
    for start, koniec, typ in scalone:
        fragmenty.extend((tekst[ostatni:start], tag(tekst[start:koniec], typ)))
        ostatni = koniec
    fragmenty.append(tekst[ostatni:])
    return "".join(fragmenty), mapa
