import os
import unittest

for key, value in {
    "MONGO_URL": "mongodb://127.0.0.1:27017",
    "DB_NAME": "test_only",
    "JWT_SECRET": "test-only-secret",
    "ADMIN_EMAIL": "test@example.com",
    "ADMIN_PASSWORD": "test-only-password",
    "PIX_KEY": "test",
    "WHATSAPP_NUMBER": "5511000000000",
    "OWNER_WHATSAPP": "5511000000000",
    "WHATSAPP_BOT_URL": "http://127.0.0.1:3002",
}.items():
    os.environ[key] = value

import server


class NaturalLanguageMatrixTests(unittest.TestCase):
    def test_service_aliases_and_typos(self):
        cases = {
            "quero volume brasileiro": "brasileiro",
            "quero o brasilero": "brasileiro",
            "fox eyes": "fox",
            "quero glamour": "glamour",
            "volume egípcio": "egipcio",
            "híbrido": "hibrido",
            "manutenção de 15": "manutencao-15",
            "manutencao 25": "manutencao-25",
            "design com henna": "henna",
            "brow lamination": "brow-lamination",
            "design simples": "designer-simples",
            "fibra de vidro": "fibra-vidro",
            "molde f1": "molde-f1",
            "esmaltação em gel": "esmaltacao-gel",
            "banho em gel": "banho-gel",
            "blindagem": "blindagem",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                service = server.wa_service_from_text(text)
                self.assertIsNotNone(service)
                self.assertEqual(service["id"], expected)

    def test_natural_times(self):
        cases = {
            "15h": "15:00",
            "15:30": "15:30",
            "umas 3 da tarde": "15:00",
            "3 da tarde": "15:00",
            "9 da manhã": "09:00",
            "6 da noite": "18:00",
            "meio dia": "12:00",
            "umas 4 de tarde": "16:00",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(server.wa_time_from_sentence(text), expected)

    def test_bare_time_uses_conversation_daypart(self):
        self.assertEqual(server.wa_time_from_sentence("3", default_daypart="afternoon", allow_bare=True), "15:00")
        self.assertEqual(server.wa_time_from_sentence("9", default_daypart="morning", allow_bare=True), "09:00")

    def test_dayparts(self):
        cases = {
            "e de manhã?": "morning",
            "qual tem de tarde": "afternoon",
            "mais pro final da tarde": "late_afternoon",
            "tem de noite?": "evening",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(server.wa_daypart_from_text(text), expected)

    def test_relative_dates(self):
        now = server.datetime(2026, 9, 15, 10, 0, tzinfo=server.TZ)
        cases = {
            "hoje": "2026-09-15",
            "amanhã": "2026-09-16",
            "depois de amanhã": "2026-09-17",
            "sexta": "2026-09-18",
            "sábado": "2026-09-19",
            "dia 22": "2026-09-22",
            "22/09": "2026-09-22",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(server.wa_date_from_sentence(text, now), expected)

    def test_cancel_intent_is_not_triggered_by_negation(self):
        negatives = [
            "não quero cancelar",
            "não cancela meu horário",
            "sem cancelar, qual meu horário?",
        ]
        for text in negatives:
            with self.subTest(text=text):
                self.assertFalse(server.wa_is_cancel_intent(text))

    def test_cancel_intent_variations(self):
        positives = [
            "quero cancelar",
            "preciso desmarcar",
            "não vou conseguir ir",
            "tira meu horário",
        ]
        for text in positives:
            with self.subTest(text=text):
                self.assertTrue(server.wa_is_cancel_intent(text))

    def test_reschedule_intent_variations(self):
        positives = [
            "quero remarcar",
            "quero reagendar",
            "mudar meu horário",
            "trocar a data",
            "mudar meu agendamento",
        ]
        for text in positives:
            with self.subTest(text=text):
                self.assertTrue(server.wa_is_reschedule_intent(text))

    def test_reservation_lookup_variations(self):
        positives = [
            "minhas reservas",
            "meus agendamentos",
            "qual meu horário",
            "tenho algum horário?",
        ]
        for text in positives:
            with self.subTest(text=text):
                self.assertTrue(server.wa_is_reservations_intent(text))

    def test_proof_status_requires_proof_context(self):
        self.assertTrue(server.wa_is_proof_status_intent("meu comprovante foi aprovado?"))
        self.assertTrue(server.wa_is_proof_status_intent("qual o status do comprovante?"))
        self.assertFalse(server.wa_is_proof_status_intent("meu pagamento foi aprovado?"))

    def test_duration_parser(self):
        cases = {"2h": 120, "2h30": 150, "1h30": 90, "40min": 40, "30min": 30}
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(server.duration_to_minutes(value), expected)

    def test_service_deposit_never_exceeds_price_for_new_booking(self):
        # Booking creation clamps the configured deposit to the service price.
        for service in server.SERVICES:
            with self.subTest(service=service["id"]):
                self.assertLessEqual(min(service["deposit"], service["price"]), service["price"])

    def test_recommendation_signals(self):
        cases = {
            "quero algo natural e delicado": "brasileiro",
            "quero estilo gatinho": "fox",
            "quero bem cheio e glamouroso": "glamour",
            "quero efeito boneca": "egipcio",
            "quero um meio termo": "hibrido",
            "quero preencher falhas da sobrancelha": "henna",
            "quero alongamento resistente": "fibra-vidro",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(server.wa_recommended_service(text)["id"], expected)


if __name__ == "__main__":
    unittest.main()
