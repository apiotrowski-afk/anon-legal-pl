import re
import unittest
from importlib.util import find_spec


@unittest.skipUnless(find_spec("pl_core_news_md"), "Test wymaga polskiego modelu z obrazu Docker")
class AnonymizationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from anon_legal_pl.anonimizuj import pseudonimizuj, zbuduj_analizator

        cls.analyzer = zbuduj_analizator("pl_core_news_md")
        cls.pseudonymize = staticmethod(pseudonimizuj)

    def mask(self, source):
        text, mapping = self.pseudonymize(source, self.analyzer)
        restored = re.sub(r"\[[A-Z_]+_\d+\]", lambda match: mapping[match[0]], text)
        self.assertEqual(restored, source)
        return text, mapping

    def test_contact_and_registration_fields_keep_labels_and_date(self):
        source = (
            "Odwołujący:\nPrzykładowa Firma sp. z o.o.\n"
            "ul. Nowe Ogrody 17A, 80-001 Gdańsk\n"
            "KRS: 0000123456, tel. +48 58 123 45 67, e-mail: kontakt@example.org\n"
            "Data wniesienia: 21.11.2026\nNr klienta\n987654\nnumer telefonu +48 58 123 45 67."
        )
        text, mapping = self.mask(source)

        for tag, value in {
            "PODMIOT": "Przykładowa Firma sp. z o.o.",
            "ULICA": "ul. Nowe Ogrody 17A",
            "KOD_POCZTOWY": "80-001",
            "KRS": "0000123456",
            "TELEFON": "+48 58 123 45 67",
            "EMAIL": "kontakt@example.org",
            "NR_KLIENTA": "987654",
        }.items():
            with self.subTest(tag=tag):
                self.assertEqual(mapping[f"[{tag}_1]"], value)
                self.assertNotIn(value, text)
        for label in ("Odwołujący:", "KRS:", "tel.", "e-mail:", "21.11.2026"):
            self.assertIn(label, text)
        self.assertEqual(text.count("[TELEFON_1]"), 2)

    def test_public_section_number_is_not_masked_as_ip_address(self):
        text, _ = self.mask("11.1.3.1\nTytuł ogłoszenia")
        self.assertIn("11.1.3.1", text)

    def test_transaction_number_uses_the_same_marker_in_both_fields(self):
        text, mapping = self.mask(
            "Tytuł\nOpłata skarbowa CEN2612345678901\n"
            "Numer referencyjny\nCEN2612345678901"
        )
        self.assertEqual(mapping["[NR_TRANSAKCJI_1]"], "CEN2612345678901")
        self.assertEqual(text.count("[NR_TRANSAKCJI_1]"), 2)
        self.assertIn("Numer referencyjny\n[NR_TRANSAKCJI_1]", text)

    def test_professional_registrations_are_masked(self):
        text, mapping = self.mask(
            "adw. Anna Kowalska (nr wpisu na listę: WA 12345)\n"
            "r. pr. Jan Nowak (numer wpisu na listę radców prawnych: GD-67890)"
        )
        self.assertEqual(mapping["[NR_WPISU_1]"], "WA 12345")
        self.assertEqual(mapping["[NR_WPISU_2]"], "GD-67890")
        self.assertIn("nr wpisu na listę: [NR_WPISU_1]", text)
        self.assertIn("numer wpisu na listę radców prawnych: [NR_WPISU_2]", text)

    def test_kio_address_is_masked(self):
        address = "ul. Postępu 17A\n02-676 Warszawa"
        text, mapping = self.mask(f"Prezes Krajowej Izby Odwoławczej\n{address}")
        self.assertIn("Prezes Krajowej Izby Odwoławczej", text)
        for tag, value in (
            ("[ULICA_1]", "ul. Postępu 17A"),
            ("[KOD_POCZTOWY_1]", "02-676"),
            ("[ADRES_1]", "Warszawa"),
        ):
            self.assertEqual(mapping[tag], value)
            self.assertNotIn(value, text)

    def test_procurement_fields_are_masked_at_each_occurrence(self):
        text, mapping = self.mask(
            "pn. „Dostawa usług\nserwisowania urządzeń” nr referencyjny sprawy: ABC.447.2026\n"
            "Numer ogłoszenia w Dzienniku Urzędowym UE: 999512-2026\n"
            "Powtórzenie: Dostawa usług serwisowania urządzeń; ABC.447.2026; 999512-2026."
        )
        self.assertEqual(text.count("[NR_SPRAWY_1]"), 2)
        self.assertEqual(text.count("[NR_TED_1]"), 2)
        self.assertEqual(
            [value for tag, value in mapping.items() if tag.startswith("[TYTUL_ZAMOWIENIA_")],
            ["Dostawa usług", "serwisowania urządzeń", "Dostawa usług serwisowania urządzeń"],
        )

    def test_notice_title_includes_its_continuation_and_stops_at_description_label(self):
        text, mapping = self.mask(
            'Tytuł: Naprawa urządzenia "Model X"\nw pracowni pomiarowej\n'
            'Opis: Przedmiotem jest naprawa urządzenia "Model X" w pracowni pomiarowej.'
        )
        self.assertIn("Opis: Przedmiotem jest [TYTUL_ZAMOWIENIA_3].", text)
        self.assertEqual(mapping["[TYTUL_ZAMOWIENIA_2]"], "w pracowni pomiarowej")

    def test_bank_accounts_without_prefix_and_across_lines(self):
        bare = "12111122223333444455556666"
        text, mapping = self.mask(
            f"Rachunek obciążany: {bare}\nRachunek beneficjenta:\n"
            "PL23 1234 5678 9012 3456 7890\n1234"
        )
        self.assertEqual(list(mapping.values()), [bare, "PL23 1234 5678 9012 3456 7890", "1234"])
        self.assertIn("Rachunek obciążany: [RACHUNEK_1]", text)
        self.assertIn("[RACHUNEK_2]\n[RACHUNEK_3]", text)

    def test_extended_notice_numbers_and_multiline_case_label(self):
        text, mapping = self.mask(
            "nr referencyjny\nsprawy: MCLM/ZP/07/2026\n"
            "Numer ogłoszenia TED: 2026/S\n111-999512\n"
            "Numer ogłoszenia BZP: 2026/BZP\n00999555/01\n"
            "W przetargu MCLM/ZP/07/2026 oraz DI.579.2026."
        )
        self.assertEqual(text.count("[NR_SPRAWY_1]"), 2)
        self.assertEqual(mapping["[NR_SPRAWY_2]"], "DI.579.2026")
        self.assertIn("[NR_TED_1]\n[NR_TED_2]", text)
        self.assertIn("[NR_BZP_1]\n[NR_BZP_2]", text)

    def test_protect_labels_and_distinguish_payment_title(self):
        text, mapping = self.mask(
            "Zamawiający:\nPrzykładowa Firma Spółka z ograniczoną\nodpowiedzialnością\n"
            "2.1. Treść\nTytuł: opłata skarbowa w przetargu DI.579.2026 CEN2612345678901\n"
            "Numer referencyjny\nCEN2612345678901"
        )
        self.assertIn("Zamawiający:\n[PODMIOT_1]\n2.1.", text)
        self.assertIn("2.1.", text)
        self.assertIn("Tytuł: opłata skarbowa w przetargu [NR_SPRAWY_1] [NR_TRANSAKCJI_1]", text)
        self.assertEqual(
            mapping["[PODMIOT_1]"], "Przykładowa Firma Spółka z ograniczoną\nodpowiedzialnością"
        )

    def test_wrapped_company_name_keeps_one_marker(self):
        examples = (
            ("adres do korespondencji: ", "Kancelaria Przykład Spółka z ograniczoną\nodpowiedzialnością"),
            ("Odwołujący:\n", "Przykładowe Biuro\nTechnologiczne Spółka Akcyjna"),
            ("Zamawiający:\n", "Wzorcowe Usługi sp. z\r\n  o.o."),
        )
        for label, name in examples:
            with self.subTest(label=label):
                text, mapping = self.mask(f"{label}{name}, ul. Pogodna 17, 65-001 Zielona Góra")
                self.assertIn(f"{label}[PODMIOT_1], [ULICA_1]", text)
                self.assertEqual(
                    [value for tag, value in mapping.items() if tag.startswith("[PODMIOT_")], [name]
                )

    def test_two_company_names_across_lines_get_separate_markers(self):
        first = "Przykładowa Firma Spółka z ograniczoną\nodpowiedzialnością"
        second = "Wzorcowe Usługi Spółka Akcyjna"
        text, mapping = self.mask(f"Zamawiający:\n{first}\nOdwołujący:\n{second}")
        self.assertEqual(text, "Zamawiający:\n[PODMIOT_1]\nOdwołujący:\n[PODMIOT_2]")
        self.assertEqual(mapping, {"[PODMIOT_1]": first, "[PODMIOT_2]": second})

    def test_document_titles_stay_visible_above_company_names(self):
        for heading in (
            "PEŁNOMOCNICTWO PROCESOWE",
            "Pełnomocnictwo",
            "Potwierdzenie wykonania przelewu",
            "ODWOŁANIE",
        ):
            with self.subTest(heading=heading):
                name = "Wzorcowe Usługi sp. z o.o."
                text, mapping = self.mask(f"{heading}\n{name}")
                self.assertEqual(text, f"{heading}\n[PODMIOT_1]")
                self.assertEqual(mapping, {"[PODMIOT_1]": name})

    def test_unlabelled_adjacent_entities_keep_separate_markers(self):
        for first in (
            "Gmina Przykładowa", "Fundacja Przykład", "Alpha Ogrody",
            "Szpital Miejski", "Bank Północny", "Uniwersytet Warszawski",
        ):
            with self.subTest(first=first):
                second = "Wzorcowe Usługi sp. z o.o."
                text, mapping = self.mask(f"Zamawiający:\n{first}\n{second}")
                self.assertEqual(text, "Zamawiający:\n[PODMIOT_1]\n[PODMIOT_2]")
                self.assertEqual(mapping, {"[PODMIOT_1]": first, "[PODMIOT_2]": second})

    def test_company_starting_with_matching_adjective_is_not_a_continuation(self):
        first = "Alfa Transport"
        second = "Technologiczny Serwis sp. z o.o."
        text, mapping = self.mask(f"Zamawiający:\n{first}\n{second}")
        self.assertEqual(text, "Zamawiający:\n[PODMIOT_1]\n[PODMIOT_2]")
        self.assertEqual(mapping, {"[PODMIOT_1]": first, "[PODMIOT_2]": second})

    def test_one_line_mention_confirms_name_wrapped_before_legal_form(self):
        wrapped = "Lunareth\nAutomatyka sp. z o.o."
        single_line = " ".join(wrapped.split())
        text, mapping = self.mask(f"Zamawiający:\n{wrapped}\nWniosek złożony przez {single_line}")
        self.assertIn("Zamawiający:\n[PODMIOT_1]\nWniosek", text)
        self.assertEqual(mapping, {"[PODMIOT_1]": wrapped, "[PODMIOT_2]": single_line})

    def test_legal_registration_and_tax_identifier_in_offer_table(self):
        text, mapping = self.mask(
            "nr wpisu na listę: KR/Adw/1987\n"
            "Poznań /\n0000000001\n201 999,00 PLN"
        )
        self.assertEqual(mapping["[NR_WPISU_1]"], "KR/Adw/1987")
        self.assertEqual(mapping["[NIP_1]"], "0000000001")
        self.assertIn("201 999,00 PLN", text)

    def test_public_entity_name_includes_patron_and_location(self):
        text, mapping = self.mask(
            "Zamawiający:\nSzpital Miejski im. dr. Jana Kowalskiego w Zielonej Górze\n"
            "ul. Pogodna 17, 65-001 Zielona Góra"
        )
        self.assertIn("Zamawiający:\n[PODMIOT_1]", text)
        self.assertEqual(mapping["[PODMIOT_1]"], "Szpital Miejski im. dr. Jana Kowalskiego w Zielonej Górze")

    def test_multiple_public_institutions_in_procurement_description(self):
        text, mapping = self.mask(
            "prowadzonym przez Państwowa Akademia Nauk Stosowanych w Zielonym Mieście "
            "oraz Szpital Miejski im. dr. Jana Kowalskiego w Zielonym Mieście, a w szczególności do:"
        )
        self.assertIn("przez [PODMIOT_1] oraz [PODMIOT_2],", text)
        self.assertEqual(mapping["[PODMIOT_1]"], "Państwowa Akademia Nauk Stosowanych w Zielonym Mieście")
        self.assertEqual(mapping["[PODMIOT_2]"], "Szpital Miejski im. dr. Jana Kowalskiego w Zielonym Mieście")

    def test_case_numbers_from_expected_fields(self):
        for source, value in (
            ("Numer wewnętrzny: ABC-042.11", "ABC-042.11"),
            ("Numer wewnętrzny:\nV.ROZ.2710.125.2025", "V.ROZ.2710.125.2025"),
            ("WPIS OD ODW., ZAM: ZESPÓŁ SZKÓŁ, ZSCKR/822/2025, BUDOWA DR. POŻAR.", "ZSCKR/822/2025"),
        ):
            with self.subTest(source=source):
                text, mapping = self.mask(source)
                self.assertIn("[NR_SPRAWY_1]", text)
                self.assertEqual(mapping["[NR_SPRAWY_1]"], value)
        text, mapping = self.mask("Dokumentacja: https://example.org/ARCH/822/2025")
        self.assertFalse(any(tag.startswith("[NR_SPRAWY_") for tag in mapping))

    def test_short_account_number_requires_a_label(self):
        number = "121111222233334444555566"
        text, mapping = self.mask(f"Rachunek źródłowy: {number}\nPowtórzenie: {number}")
        self.assertEqual(mapping, {"[RACHUNEK_1]": number})
        self.assertEqual(text.count("[RACHUNEK_1]"), 2)

        text, mapping = self.mask("Z rachunku:\n1211 1122 2233\n3344 4455 5566")
        self.assertIn("[RACHUNEK_1]\n[RACHUNEK_2]", text)
        self.assertEqual(mapping["[RACHUNEK_1]"], "1211 1122 2233")
        self.assertEqual(mapping["[RACHUNEK_2]"], "3344 4455 5566")

        _, mapping = self.mask(f"Ciąg kontrolny: {number}")
        self.assertFalse(any(tag.startswith("[RACHUNEK_") for tag in mapping))

    def test_labelled_transactions_outside_cen(self):
        for number in ("ABX-264021-45", "OP/2025/0054.v2", "12111122223333444455556666"):
            with self.subTest(number=number):
                text, mapping = self.mask(f"Tytuł przelewu: opłata {number}\nNumer transakcji:\n{number}")
                self.assertEqual(text.count("[NR_TRANSAKCJI_1]"), 2)
                self.assertEqual(mapping["[NR_TRANSAKCJI_1]"], number)

        text, mapping = self.mask("Identyfikator operacji: OPS.123/45")
        self.assertIn("Identyfikator operacji: [NR_TRANSAKCJI_1]", text)
        self.assertEqual(mapping["[NR_TRANSAKCJI_1]"], "OPS.123/45")

        _, mapping = self.mask("Numer transakcji: brak danych\nData transakcji: 2025-10-09")
        self.assertFalse(any(tag.startswith("[NR_TRANSAKCJI_") for tag in mapping))
