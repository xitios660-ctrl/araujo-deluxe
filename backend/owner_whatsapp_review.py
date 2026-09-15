"""Owner WhatsApp proof review helpers.

Critical approval stays in the backend: only OWNER_WHATSAPP may review a pending proof.
"""
import re


def owner_review_command(text: str):
    raw = (text or "").strip()
    normalized = raw.lower()
    approved = bool(re.search(r"\b(aprovar|aprova|aprovado|confirmar|confirma)\b", normalized))
    rejected = bool(re.search(r"\b(rejeitar|rejeita|recusar|recusa)\b", normalized))
    if approved == rejected:
        return None
    code_match = re.search(r"\bAD-[A-Z0-9-]{4,}\b", raw.upper())
    return {"approved": approved, "code": code_match.group(0) if code_match else None}


async def handle_owner_review(phone: str, text: str, server=None):
    if server is None:
        import server as server_module
        server = server_module
    if not server.phones_match(phone, server.OWNER_WA):
        return None
    command = owner_review_command(text)
    if not command:
        return None

    if not command["code"]:
        return "Para segurança, envie o código da reserva junto: *APROVAR AD-CÓDIGO* ou *REJEITAR AD-CÓDIGO*."

    booking = await server.db.bookings.find_one({"code": command["code"]}, {"_id": 0})
    if not booking or not booking.get("proof_id"):
        return "Não encontrei um comprovante pendente para esse código."

    proofs = await server.db.proofs.find(
        {"id": booking["proof_id"], "status": "em_analise"},
        {"_id": 0},
    ).to_list(2)
    if not proofs:
        return "Não encontrei comprovante aguardando análise para essa reserva."

    proof = proofs[0]
    booking = await server.db.bookings.find_one({"id": proof.get("booking_id")}, {"_id": 0})
    if not booking:
        return "A reserva desse comprovante não foi encontrada."

    actor = {"id": "owner-whatsapp", "email": "owner@whatsapp.local", "name": "Dona via WhatsApp", "role": "owner"}
    try:
        await server._review_proof(proof["id"], command["approved"], actor)
    except server.HTTPException as exc:
        return f"Não consegui revisar esse comprovante: {exc.detail}"

    action = "aprovado e a reserva foi confirmada" if command["approved"] else "rejeitado e a reserva continua pendente"
    return f"✅ Comprovante da reserva *{booking['code']}* {action}. O painel do site já foi atualizado."
