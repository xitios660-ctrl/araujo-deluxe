import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from owner_whatsapp_review import owner_review_command, handle_owner_review


class _Cursor:
    def __init__(self, items):
        self.items = items

    async def to_list(self, _limit):
        return self.items


class OwnerWhatsappReviewTests(unittest.IsolatedAsyncioTestCase):
    def test_command_parsing(self):
        self.assertEqual(
            owner_review_command("Aprovar AD-ABC12345"),
            {"approved": True, "code": "AD-ABC12345"},
        )
        self.assertEqual(
            owner_review_command("Rejeitar AD-ABC12345"),
            {"approved": False, "code": "AD-ABC12345"},
        )
        self.assertIsNone(owner_review_command("aprovar ou rejeitar depois"))

    async def test_non_owner_cannot_review(self):
        server = SimpleNamespace(
            OWNER_WA="5511888888888",
            phones_match=lambda a, b: a == b,
        )
        result = await handle_owner_review("5511999999999", "Aprovar AD-ABC12345", server)
        self.assertIsNone(result)

    async def test_owner_must_include_code(self):
        server = SimpleNamespace(
            OWNER_WA="5511888888888",
            phones_match=lambda a, b: a == b,
        )
        result = await handle_owner_review("5511888888888", "Aprovar", server)
        self.assertIn("código", result.lower())

    async def test_owner_approval_uses_backend_review_function(self):
        booking = {
            "id": "booking-1",
            "code": "AD-ABC12345",
            "proof_id": "proof-1",
            "proof_status": "em_analise",
            "status": "pendente",
        }
        proof = {"id": "proof-1", "booking_id": "booking-1", "status": "em_analise"}

        db = MagicMock()
        db.bookings.find_one = AsyncMock(side_effect=[booking, booking])
        db.proofs.find.return_value = _Cursor([proof])
        review = AsyncMock(return_value={"ok": True})

        server = SimpleNamespace(
            OWNER_WA="5511888888888",
            phones_match=lambda a, b: a == b,
            db=db,
            _review_proof=review,
            HTTPException=Exception,
        )

        result = await handle_owner_review("5511888888888", "Aprovar AD-ABC12345", server)

        review.assert_awaited_once()
        proof_id, approved, actor = review.await_args.args
        self.assertEqual(proof_id, "proof-1")
        self.assertTrue(approved)
        self.assertEqual(actor["id"], "owner-whatsapp")
        self.assertIn("painel do site já foi atualizado", result.lower())


if __name__ == "__main__":
    unittest.main()
