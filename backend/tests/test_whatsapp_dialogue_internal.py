import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

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


class AvailabilityLanguageTests(unittest.IsolatedAsyncioTestCase):
    def test_after_tomorrow_is_two_days_ahead(self):
        now = server.datetime(2026, 9, 14, 21, 38, tzinfo=server.TZ)
        self.assertEqual(server.wa_date_from_sentence("Para depois de amanhã tem horário?", now), "2026-09-16")

    def test_day_number_uses_current_month_when_future(self):
        now = server.datetime(2026, 9, 14, 21, 38, tzinfo=server.TZ)
        self.assertEqual(server.wa_date_from_sentence("E dia 16?", now), "2026-09-16")

    def test_day_number_rolls_to_next_month_if_needed(self):
        now = server.datetime(2026, 9, 30, 21, 38, tzinfo=server.TZ)
        self.assertEqual(server.wa_date_from_sentence("dia 2", now), "2026-10-02")

    async def test_specific_date_availability_without_service(self):
        day = {
            "date": "2026-09-16", "weekday_name": "Quarta-feira",
            "scheduled_open": True, "open": True, "day_blocked": False,
            "closed_reason": None,
            "slots": [
                {"time": "09:00", "available": True},
                {"time": "11:00", "available": False},
                {"time": "15:30", "available": True},
            ],
        }
        setter = AsyncMock()
        with patch.object(server, "get_day_availability", AsyncMock(return_value=day)):
            result = await server.wa_smart_action(
                "Para dia 16/09 tem horário", "menu", {}, "5511999999999", {}, setter
            )
        self.assertIn("16/09/2026", result["reply"])
        self.assertIn("qual procedimento", result["reply"].lower())
        self.assertNotIn("qual dia", result["reply"].lower())

    async def test_time_pick_after_availability_keeps_date(self):
        day = {
            "date": "2026-09-16", "weekday_name": "Quarta-feira",
            "scheduled_open": True, "open": True, "day_blocked": False,
            "closed_reason": None,
            "slots": [
                {"time": "09:00", "available": True},
                {"time": "15:30", "available": True},
            ],
        }
        fake = MagicMock()
        fake.wa_preferences.find_one = AsyncMock(return_value=None)
        fake.wa_preferences.update_one = AsyncMock()
        fake.wa_memories.find_one = AsyncMock(return_value={"history": [], "message_count": 0})
        fake.wa_memories.update_one = AsyncMock()
        fake.wa_sessions.find_one = AsyncMock(return_value={
            "state": "avail_pick",
            "data": {"date": "2026-09-16", "slots": ["09:00", "15:30"]},
        })
        fake.wa_sessions.update_one = AsyncMock()
        with patch.object(server, "db", fake), \
             patch.object(server, "get_day_availability", AsyncMock(return_value=day)):
            result = await server.whatsapp_incoming(
                server.WAIncoming(phone="5511999999999", text="15:30", push_name="Cliente"),
                auth={"test": True},
            )
        self.assertIn("procedimento", result["reply"].lower())
        update = fake.wa_sessions.update_one.await_args.args[1]["$set"]
        self.assertEqual(update["state"], "book_category")
        self.assertEqual(update["data"]["date"], "2026-09-16")
        self.assertEqual(update["data"]["time"], "15:30")

    async def test_category_preserves_preselected_date_and_time(self):
        fake = MagicMock()
        fake.wa_preferences.find_one = AsyncMock(return_value=None)
        fake.wa_preferences.update_one = AsyncMock()
        fake.wa_memories.find_one = AsyncMock(return_value={"history": [], "message_count": 0})
        fake.wa_memories.update_one = AsyncMock()
        fake.wa_sessions.find_one = AsyncMock(return_value={
            "state": "book_category",
            "data": {"date": "2026-09-16", "time": "15:30"},
        })
        fake.wa_sessions.update_one = AsyncMock()
        with patch.object(server, "db", fake):
            await server.whatsapp_incoming(
                server.WAIncoming(phone="5511999999999", text="Cílios", push_name="Cliente"),
                auth={"test": True},
            )
        update = fake.wa_sessions.update_one.await_args.args[1]["$set"]
        self.assertEqual(update["state"], "book_service")
        self.assertEqual(update["data"]["date"], "2026-09-16")
        self.assertEqual(update["data"]["time"], "15:30")
        self.assertEqual(update["data"]["category"], "cilios")

    async def test_service_uses_preselected_slot_without_asking_date_again(self):
        day = {
            "date": "2026-09-16", "weekday_name": "Quarta-feira",
            "scheduled_open": True, "open": True, "day_blocked": False,
            "closed_reason": None,
            "slots": [{"time": "15:30", "available": True}],
        }
        fake = MagicMock()
        fake.wa_preferences.find_one = AsyncMock(return_value=None)
        fake.wa_preferences.update_one = AsyncMock()
        fake.wa_memories.find_one = AsyncMock(return_value={"history": [], "message_count": 0})
        fake.wa_memories.update_one = AsyncMock()
        fake.wa_sessions.find_one = AsyncMock(return_value={
            "state": "book_service",
            "data": {"category": "cilios", "date": "2026-09-16", "time": "15:30"},
        })
        fake.wa_sessions.update_one = AsyncMock()
        with patch.object(server, "db", fake), \
             patch.object(server, "get_day_availability", AsyncMock(return_value=day)):
            result = await server.whatsapp_incoming(
                server.WAIncoming(phone="5511999999999", text="Volume Glamour", push_name="Cliente"),
                auth={"test": True},
            )
        self.assertIn("nome completo", result["reply"].lower())
        self.assertNotIn("para qual data", result["reply"].lower())
        update = fake.wa_sessions.update_one.await_args.args[1]["$set"]
        self.assertEqual(update["state"], "book_name")
        self.assertEqual(update["data"]["service_id"], "glamour")
        self.assertEqual(update["data"]["date"], "2026-09-16")
        self.assertEqual(update["data"]["time"], "15:30")

    async def test_followup_day_keeps_availability_context(self):
        day = {
            "date": "2026-09-16", "weekday_name": "Quarta-feira",
            "scheduled_open": True, "open": True, "day_blocked": False,
            "closed_reason": None,
            "slots": [{"time": "17:00", "available": True}],
        }
        memory = {"history": [{"role": "user", "text": "Para depois de amanhã tem horário?"}]}
        setter = AsyncMock()
        # The parser itself is covered with a fixed clock above. For the smart
        # follow-up, use an explicit date so the test is stable on any CI date.
        with patch.object(server, "get_day_availability", AsyncMock(return_value=day)):
            result = await server.wa_smart_action(
                "E dia 16/09?", "menu", {}, "5511999999999", memory, setter
            )
        self.assertIn("16/09/2026", result["reply"])
        self.assertIn("qual procedimento", result["reply"].lower())
        self.assertNotIn("menu", result["reply"].lower())


class DialogueRegressionTests(unittest.IsolatedAsyncioTestCase):
    def fake_db(self, state="book_category", history=None):
        fake = MagicMock()
        fake.wa_preferences.find_one = AsyncMock(return_value=None)
        fake.wa_preferences.update_one = AsyncMock(return_value=None)
        fake.wa_memories.find_one = AsyncMock(return_value={
            "history": history or [],
            "message_count": len(history or []),
        })
        fake.wa_memories.update_one = AsyncMock(return_value=None)
        fake.wa_sessions.find_one = AsyncMock(return_value={"state": state, "data": {}})
        fake.wa_sessions.update_one = AsyncMock(return_value=None)
        fake.bookings.find.return_value.to_list = AsyncMock(return_value=[])
        return fake

    async def call(self, text, state="book_category", history=None):
        fake = self.fake_db(state, history)
        with patch.object(server, "db", fake):
            result = await server.whatsapp_incoming(
                server.WAIncoming(phone="5511999999999", text=text, push_name="Cliente"),
                auth={"test": True},
            )
        return result, fake

    async def test_self_deprecation_does_not_loop_category_prompt(self):
        result, fake = await self.call("Sou burro")
        reply = result["reply"].lower()
        self.assertIn("não é burro", reply)
        self.assertNotIn("você quer fazer cílios, unhas ou sobrancelhas", reply)
        fake.wa_sessions.update_one.assert_not_awaited()

    async def test_apology_self_deprecation_is_conversation(self):
        result, fake = await self.call("Desculpa sou muito burro para isso")
        reply = result["reply"].lower()
        self.assertIn("não é burro", reply)
        self.assertNotIn("escolha uma categoria", reply)
        fake.wa_sessions.update_one.assert_not_awaited()

    async def test_what_do_you_think_uses_previous_context(self):
        history = [{"role": "user", "text": "Desculpa sou muito burro para isso"}]
        result, fake = await self.call("O que você acha", history=history)
        reply = result["reply"].lower()
        self.assertIn("não é burro", reply)
        self.assertIn("conversar normal", reply)
        fake.wa_sessions.update_one.assert_not_awaited()

    async def test_unhas_still_continues_booking_after_chat(self):
        result, fake = await self.call("Unhas")
        self.assertIn("serviço de", result["reply"].lower())
        self.assertEqual(result["ui"]["type"], "list")
        self.assertTrue(any("fibra" in row["title"].lower() for row in result["ui"]["sections"][0]["rows"]))
        fake.wa_sessions.update_one.assert_awaited()

    async def test_menu_always_resets_and_returns_options(self):
        result, fake = await self.call("Manda o menu porfavor", state="book_category")
        self.assertIn("voltamos pro começo", result["reply"].lower())
        self.assertEqual(result["ui"]["button_text"], "Abrir menu")
        fake.wa_sessions.update_one.assert_awaited()




class IntentPriorityTests(unittest.IsolatedAsyncioTestCase):
    def fake_db(self, state="menu", sdata=None, bookings=None):
        fake = MagicMock()
        fake.wa_preferences.find_one = AsyncMock(return_value=None)
        fake.wa_preferences.update_one = AsyncMock()
        fake.wa_memories.find_one = AsyncMock(return_value={"history": [], "message_count": 0})
        fake.wa_memories.update_one = AsyncMock()
        fake.wa_sessions.find_one = AsyncMock(return_value={"state": state, "data": sdata or {}})
        fake.wa_sessions.update_one = AsyncMock()
        fake.bookings.find.return_value.to_list = AsyncMock(return_value=bookings or [])
        fake.bookings.find_one = AsyncMock(side_effect=lambda q, *args, **kwargs: next(
            (b for b in (bookings or []) if b.get("id") == q.get("id")), None
        ))
        fake.bookings.update_one = AsyncMock()
        fake.proofs.update_one = AsyncMock()
        return fake

    def booking(self, booking_id, code, service="Volume Brasileiro", status="confirmada", date="2026-09-20", time="15:30", proof_status=None):
        return {
            "id": booking_id,
            "code": code,
            "service_id": "brasileiro",
            "service_name": service,
            "category": "cilios",
            "price": 100,
            "deposit": 50,
            "date": date,
            "time": time,
            "client_name": "Gustavo",
            "client_phone": "5511999999999",
            "status": status,
            "proof_status": proof_status,
            "created_at": "2026-09-15T00:00:00+00:00",
        }


    def test_cancel_negation_is_not_cancel_intent(self):
        self.assertFalse(server.wa_is_cancel_intent("Não quero cancelar, só queria saber meu horário"))

    async def test_exact_screenshot_cancel_all_never_starts_booking(self):
        bookings = [
            self.booking("b1", "AD-AAAA11", date="2026-09-20", time="15:30"),
            self.booking("b2", "AD-BBBB22", service="Volume Glamour", date="2026-09-22", time="17:00"),
        ]
        fake = self.fake_db(bookings=bookings)
        with patch.object(server, "db", fake), patch.object(server, "slot_in_past", return_value=False):
            result = await server.whatsapp_incoming(
                server.WAIncoming(phone="5511999999999", text="Quero cancelar todos os meus agendamentos", push_name="Gustavo"),
                auth={"test": True},
            )
        reply = result["reply"].lower()
        self.assertIn("nada foi cancelado ainda", reply)
        self.assertIn("sim, cancelar todos", reply)
        self.assertNotIn("bora marcar", reply)
        update = fake.wa_sessions.update_one.await_args.args[1]["$set"]
        self.assertEqual(update["state"], "cancel_confirm_all")
        self.assertEqual(set(update["data"]["booking_ids"]), {"b1", "b2"})

    async def test_cancel_all_requires_confirmation_and_releases_slots(self):
        bookings = [
            self.booking("b1", "AD-AAAA11", date="2026-09-20", time="15:30"),
            self.booking("b2", "AD-BBBB22", service="Volume Glamour", date="2026-09-22", time="17:00"),
        ]
        fake = self.fake_db(
            state="cancel_confirm_all",
            sdata={"booking_ids": ["b1", "b2"]},
            bookings=bookings,
        )
        release = AsyncMock()
        with patch.object(server, "db", fake), \
             patch.object(server, "slot_in_past", return_value=False), \
             patch.object(server, "release_booking_slot", release):
            result = await server.whatsapp_incoming(
                server.WAIncoming(phone="5511999999999", text="sim, cancelar todos", push_name="Gustavo"),
                auth={"test": True},
            )
        self.assertIn("cancelei *2*", result["reply"].lower())
        self.assertEqual(fake.bookings.update_one.await_count, 2)
        self.assertEqual(release.await_count, 2)

    async def test_cancel_confirmation_no_keeps_booking(self):
        bookings = [self.booking("b1", "AD-AAAA11")]
        fake = self.fake_db(
            state="cancel_confirm_one",
            sdata={"booking_id": "b1"},
            bookings=bookings,
        )
        release = AsyncMock()
        with patch.object(server, "db", fake), patch.object(server, "release_booking_slot", release):
            result = await server.whatsapp_incoming(
                server.WAIncoming(phone="5511999999999", text="não", push_name="Gustavo"),
                auth={"test": True},
            )
        self.assertIn("mantive", result["reply"].lower())
        fake.bookings.update_one.assert_not_awaited()
        release.assert_not_awaited()

    async def test_reschedule_is_not_interpreted_as_new_booking(self):
        bookings = [self.booking("b1", "AD-AAAA11")]
        fake = self.fake_db(bookings=bookings)
        with patch.object(server, "db", fake), patch.object(server, "slot_in_past", return_value=False):
            result = await server.whatsapp_incoming(
                server.WAIncoming(phone="5511999999999", text="Quero remarcar meu agendamento", push_name="Gustavo"),
                auth={"test": True},
            )
        self.assertIn("qual nova data", result["reply"].lower())
        self.assertNotIn("bora marcar", result["reply"].lower())
        update = fake.wa_sessions.update_one.await_args.args[1]["$set"]
        self.assertEqual(update["state"], "reschedule_date")
        self.assertEqual(update["data"]["booking_id"], "b1")

    async def test_proof_status_question_is_answered_before_booking_rules(self):
        booking = self.booking("b1", "AD-AAAA11", status="pendente", proof_status="em_analise")
        booking["proof_id"] = "p1"
        fake = self.fake_db(bookings=[booking])
        with patch.object(server, "db", fake):
            result = await server.whatsapp_incoming(
                server.WAIncoming(phone="5511999999999", text="Meu comprovante já foi aprovado?", push_name="Gustavo"),
                auth={"test": True},
            )
        self.assertIn("em análise", result["reply"].lower())

    async def test_reservations_query_lists_without_starting_booking(self):
        bookings = [self.booking("b1", "AD-AAAA11")]
        fake = self.fake_db(bookings=bookings)
        with patch.object(server, "db", fake):
            result = await server.whatsapp_incoming(
                server.WAIncoming(phone="5511999999999", text="Quais são meus agendamentos?", push_name="Gustavo"),
                auth={"test": True},
            )
        self.assertIn("volume brasileiro", result["reply"].lower())
        self.assertIn("ad-aaaa11", result["reply"].lower())
        self.assertNotIn("bora marcar", result["reply"].lower())

    async def test_business_hours_question_is_answered(self):
        fake = self.fake_db(bookings=[])
        with patch.object(server, "db", fake):
            result = await server.whatsapp_incoming(
                server.WAIncoming(phone="5511999999999", text="Vocês atendem domingo?", push_name="Gustavo"),
                auth={"test": True},
            )
        self.assertIn("domingo", result["reply"].lower())
        self.assertIn("fechado", result["reply"].lower())



class ConversationIntelligenceTests(unittest.IsolatedAsyncioTestCase):
    def fake_db(self, state="menu", sdata=None, memory=None, bookings=None):
        fake = MagicMock()
        fake.wa_preferences.find_one = AsyncMock(return_value=None)
        fake.wa_preferences.update_one = AsyncMock()
        fake.wa_memories.find_one = AsyncMock(return_value=memory or {"history": [], "message_count": 0})
        fake.wa_memories.update_one = AsyncMock()
        fake.wa_sessions.find_one = AsyncMock(return_value={"state": state, "data": sdata or {}})
        fake.wa_sessions.update_one = AsyncMock()
        fake.bookings.find.return_value.to_list = AsyncMock(return_value=bookings or [])
        return fake

    async def call(self, text, state="menu", sdata=None, memory=None):
        fake = self.fake_db(state=state, sdata=sdata, memory=memory)
        with patch.object(server, "db", fake):
            result = await server.whatsapp_incoming(
                server.WAIncoming(phone="5511999999999", text=text, push_name="Cliente"),
                auth={"test": True},
            )
        return result, fake

    async def test_returning_greeting_is_compact_and_site_is_not_repeated(self):
        memory = {
            "last_service_id": "brasileiro",
            "name": "Gustavo",
            "history": [],
            "message_count": 4,
        }
        result, _ = await self.call("oi", memory=memory)
        reply = result["reply"]
        self.assertIn("Bom te ver por aqui de novo", reply)
        self.assertIn("Volume Brasileiro", reply)
        self.assertNotIn("https://araujo-deluxe-studio.onrender.com", reply)
        self.assertEqual(len(result["ui"]["sections"][0]["rows"]), 5)

    async def test_site_can_be_requested_naturally(self):
        result, _ = await self.call("manda o site para eu reservar")
        self.assertIn("araujo-deluxe-studio.onrender.com", result["reply"])
        self.assertIn("site oficial", result["reply"].lower())

    async def test_menu_has_site_option(self):
        result, _ = await self.call("menu")
        self.assertTrue(any(
            row["id"] == "menu:site"
            for section in result["ui"]["sections"]
            for row in section["rows"]
        ))

    async def test_site_interactive_option_returns_link(self):
        result, _ = await self.call("menu:site")
        self.assertIn("araujo-deluxe-studio.onrender.com", result["reply"])

    async def test_followup_price_uses_remembered_service(self):
        memory = {
            "last_service_id": "glamour",
            "last_outgoing_text": "Se você gostar, eu já vejo um horário.",
            "history": [],
            "message_count": 3,
        }
        result, _ = await self.call("e quanto ele custa?", memory=memory)
        reply = result["reply"].lower()
        self.assertIn("volume glamour", reply)
        self.assertIn("r$ 140", reply)

    async def test_followup_deposit_uses_remembered_service(self):
        memory = {
            "last_service_id": "brasileiro",
            "last_outgoing_text": "Volume Brasileiro fica R$ 100.",
            "history": [],
            "message_count": 3,
        }
        result, _ = await self.call("e o sinal?", memory=memory)
        self.assertIn("r$ 50", result["reply"].lower())
        self.assertIn("volume brasileiro", result["reply"].lower())

    async def test_yes_after_recommendation_continues_booking(self):
        memory = {
            "last_service_id": "brasileiro",
            "last_outgoing_text": "Pelo que você me falou eu iria de Volume Brasileiro. Se você gostar, eu já vejo um horário.",
            "history": [],
            "message_count": 3,
        }
        result, fake = await self.call("sim", memory=memory)
        self.assertIn("qual dia", result["reply"].lower())
        update = fake.wa_sessions.update_one.await_args.args[1]["$set"]
        self.assertEqual(update["state"], "book_date")
        self.assertEqual(update["data"]["service_id"], "brasileiro")

    async def test_comparison_between_services_is_natural(self):
        result, _ = await self.call("qual a diferença entre brasileiro e glamour?")
        reply = result["reply"].lower()
        self.assertIn("volume brasileiro", reply)
        self.assertIn("volume glamour", reply)
        self.assertIn("r$ 100", reply)
        self.assertIn("r$ 140", reply)

    async def test_too_expensive_offers_same_category_alternatives(self):
        memory = {
            "last_service_id": "fox",
            "last_outgoing_text": "Fox Eyes fica R$ 150",
            "history": [],
            "message_count": 3,
        }
        result, _ = await self.call("ta caro kkk", memory=memory)
        reply = result["reply"].lower()
        self.assertIn("economizar", reply)
        self.assertIn("volume brasileiro", reply)
        self.assertNotIn("manutenção", reply)

    async def test_uncertain_lashes_asks_effect_not_menu_reset(self):
        result, _ = await self.call("quero cílios mas não sei qual escolher")
        reply = result["reply"].lower()
        self.assertIn("natural", reply)
        self.assertIn("alongado", reply)
        self.assertIn("mais cheio", reply)

    async def test_unknown_question_during_booking_keeps_context(self):
        memory = {
            "last_service_id": "brasileiro",
            "history": [],
            "message_count": 2,
        }
        result, fake = await self.call(
            "e quanto tempo demora?",
            state="book_date",
            sdata={"service_id": "brasileiro"},
            memory=memory,
        )
        self.assertIn("2h", result["reply"])
        self.assertIn("não perdi", result["reply"].lower())
        fake.wa_sessions.update_one.assert_not_awaited()




    def test_natural_time_variants_and_dayparts(self):
        self.assertEqual(server.wa_time_from_sentence("umas 3 da tarde"), "15:00")
        self.assertEqual(server.wa_time_from_sentence("3 da tarde"), "15:00")
        self.assertEqual(server.wa_time_from_sentence("15h"), "15:00")
        self.assertEqual(server.wa_time_from_sentence("15", allow_bare=True), "15:00")
        self.assertEqual(server.wa_time_from_sentence("3", default_daypart="afternoon", allow_bare=True), "15:00")
        self.assertEqual(server.wa_daypart_from_text("mais pro final da tarde"), "late_afternoon")

    def test_daypart_filter_and_same_hour_resolution(self):
        slots = ["09:00", "11:00", "15:30", "17:00"]
        self.assertEqual(server.filter_slots_by_daypart(slots, "morning"), ["09:00", "11:00"])
        self.assertEqual(server.filter_slots_by_daypart(slots, "afternoon"), ["15:30", "17:00"])
        self.assertEqual(server.resolve_requested_slot("quero o das 15", slots), "15:30")

    async def test_first_time_lashes_gets_safe_recommendation(self):
        result, _ = await self.call("é minha primeira vez com cílios")
        self.assertIn("Volume Brasileiro", result["reply"])
        self.assertIn("natural", result["reply"].lower())

    async def test_longest_procedure_question(self):
        result, _ = await self.call("qual procedimento dura mais?")
        self.assertIn("2h30", result["reply"])

    async def test_address_is_not_invented_when_unconfigured(self):
        with patch.object(server, "STUDIO_ADDRESS", ""):
            result, _ = await self.call("onde fica?")
        self.assertIn("não tenho o endereço cadastrado", result["reply"].lower())




    async def test_service_alias_keeps_previously_selected_date(self):
        day = {
            "date": "2026-09-16", "weekday_name": "Quarta-feira",
            "scheduled_open": True, "open": True, "day_blocked": False,
            "closed_reason": None,
            "slots": [
                {"time": "09:00", "available": True},
                {"time": "15:30", "available": True},
            ],
        }
        fake = self.fake_db(
            state="book_service",
            sdata={"category": "cilios", "date": "2026-09-16"},
            memory={"history": [], "message_count": 1},
        )
        with patch.object(server, "db", fake), patch.object(server, "get_day_availability", AsyncMock(return_value=day)):
            result = await server.whatsapp_incoming(
                server.WAIncoming(phone="5511999999999", text="brasileiro", push_name="Cliente"),
                auth={"test": True},
            )
        self.assertIn("16/09/2026", result["reply"])
        self.assertIn("15:30", result["reply"])
        update = fake.wa_sessions.update_one.await_args.args[1]["$set"]
        self.assertEqual(update["state"], "book_time")
        self.assertEqual(update["data"]["service_id"], "brasileiro")
        self.assertEqual(update["data"]["date"], "2026-09-16")


if __name__ == "__main__":
    unittest.main()
