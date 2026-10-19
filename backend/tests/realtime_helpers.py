"""Server-originated transport probes; never reachable from a client frame."""

async def deliver_to_all(manager, text):
    event = {"type": "message", "data": {"text": text}}
    for user_id in list(manager.active_connections):
        await manager.send_to_user(user_id, event)
