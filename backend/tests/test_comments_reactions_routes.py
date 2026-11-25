"""Route-level tests for comments & reactions — friendship gates, ownership, unfriend behavior, public top10, blocks."""

from app.db.models import Profile

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
FRIENDS_REQ = "/api/v1/friends/request"
FRIENDS_ACC = "/api/v1/friends/accept"
FRIENDS_DEL = "/api/v1/friends"
FRIENDS_BLOCK = "/api/v1/friends/block"

ALICE = {"email": "alice@test.com", "password": "hunter22", "display_name": "Alice"}
BOB = {"email": "bob@test.com", "password": "hunter22", "display_name": "Bob"}
CHARLIE = {"email": "charlie@test.com", "password": "hunter22", "display_name": "Charlie"}


def _register_and_login(client, user):
    res = client.post(REGISTER, json=user)
    user_id = res.json()["id"]
    client.post(LOGIN, json={"email": user["email"], "password": user["password"]})
    return user_id


def _login(client, user):
    client.post(LOGIN, json={"email": user["email"], "password": user["password"]})


def _make_friends(client, user_a, user_b, id_a, id_b):
    """Login as A, send request to B, login as B, accept."""
    _login(client, user_a)
    client.post(f"{FRIENDS_REQ}/{id_b}")
    _login(client, user_b)
    client.post(f"{FRIENDS_ACC}/{id_a}")


def _set_top10_public(session, user_id, public=True):
    session.query(Profile).filter(Profile.user_id == user_id).update({"is_top10_public": public})
    session.commit()


def _comments_url(user_id):
    return f"/api/v1/profiles/{user_id}/comments"


def _reactions_url(user_id):
    return f"/api/v1/profiles/{user_id}/reactions"


# ── Comments — friendship required to add ────────────────────────────

def test_friend_can_add_comment(client):
    alice_id = _register_and_login(client, ALICE)
    bob_id = _register_and_login(client, BOB)
    _make_friends(client, ALICE, BOB, alice_id, bob_id)

    # Bob is logged in after _make_friends
    res = client.post(_comments_url(alice_id), json={"body": "Nice list!"})
    assert res.status_code == 200


def test_non_friend_cannot_add_comment_on_private_top10(client, session):
    alice_id = _register_and_login(client, ALICE)
    _set_top10_public(session, alice_id, False)
    _register_and_login(client, BOB)

    res = client.post(_comments_url(alice_id), json={"body": "Nice list!"})
    assert res.status_code == 422


# ── Comments — friendship required to edit ───────────────────────────

def test_friend_can_edit_own_comment(client):
    alice_id = _register_and_login(client, ALICE)
    bob_id = _register_and_login(client, BOB)
    _make_friends(client, ALICE, BOB, alice_id, bob_id)

    comment_id = client.post(_comments_url(alice_id), json={"body": "Nice list!"}).json()["id"]

    res = client.post(f"{_comments_url(alice_id)}/{comment_id}", json={"body": "Updated!"})
    assert res.status_code == 200
    assert res.json()["body"] == "Updated!"


def test_cannot_edit_comment_after_unfriending(client, session):
    alice_id = _register_and_login(client, ALICE)
    bob_id = _register_and_login(client, BOB)
    _make_friends(client, ALICE, BOB, alice_id, bob_id)

    comment_id = client.post(_comments_url(alice_id), json={"body": "Nice list!"}).json()["id"]

    # Alice unfriends Bob and her top10 is private
    _login(client, ALICE)
    client.delete(f"{FRIENDS_DEL}/{bob_id}")
    _set_top10_public(session, alice_id, False)

    # Bob tries to edit — should fail
    _login(client, BOB)
    res = client.post(f"{_comments_url(alice_id)}/{comment_id}", json={"body": "Hacked!"})
    assert res.status_code == 422


# ── Comments — delete: author always, owner can delete anyone's ──────

def test_author_can_delete_own_comment_even_after_unfriending(client):
    alice_id = _register_and_login(client, ALICE)
    bob_id = _register_and_login(client, BOB)
    _make_friends(client, ALICE, BOB, alice_id, bob_id)

    comment_id = client.post(_comments_url(alice_id), json={"body": "Nice list!"}).json()["id"]

    _login(client, ALICE)
    client.delete(f"{FRIENDS_DEL}/{bob_id}")

    _login(client, BOB)
    res = client.delete(f"{_comments_url(alice_id)}/{comment_id}")
    assert res.status_code == 200


def test_top10_owner_can_delete_others_comment(client):
    alice_id = _register_and_login(client, ALICE)
    bob_id = _register_and_login(client, BOB)
    _make_friends(client, ALICE, BOB, alice_id, bob_id)

    comment_id = client.post(_comments_url(alice_id), json={"body": "Nice list!"}).json()["id"]

    _login(client, ALICE)
    res = client.delete(f"{_comments_url(alice_id)}/{comment_id}")
    assert res.status_code == 200


def test_random_user_cannot_delete_others_comment(client):
    alice_id = _register_and_login(client, ALICE)
    bob_id = _register_and_login(client, BOB)
    _make_friends(client, ALICE, BOB, alice_id, bob_id)

    comment_id = client.post(_comments_url(alice_id), json={"body": "Nice list!"}).json()["id"]

    _register_and_login(client, CHARLIE)
    res = client.delete(f"{_comments_url(alice_id)}/{comment_id}")
    assert res.status_code == 404


# ── Reactions — friendship required to add ───────────────────────────

def test_friend_can_add_reaction(client):
    alice_id = _register_and_login(client, ALICE)
    bob_id = _register_and_login(client, BOB)
    _make_friends(client, ALICE, BOB, alice_id, bob_id)

    res = client.post(_reactions_url(alice_id), json={"reaction": "like"})
    assert res.status_code == 200


def test_non_friend_cannot_add_reaction_on_private_top10(client, session):
    alice_id = _register_and_login(client, ALICE)
    _set_top10_public(session, alice_id, False)
    _register_and_login(client, BOB)

    res = client.post(_reactions_url(alice_id), json={"reaction": "like"})
    assert res.status_code == 403


def test_friend_can_change_reaction(client):
    alice_id = _register_and_login(client, ALICE)
    bob_id = _register_and_login(client, BOB)
    _make_friends(client, ALICE, BOB, alice_id, bob_id)

    client.post(_reactions_url(alice_id), json={"reaction": "like"})
    res = client.post(_reactions_url(alice_id), json={"reaction": "dislike"})
    assert res.status_code == 200
    assert res.json()["reaction"] == "dislike"


# ── Reactions — only the author can delete their own reaction ────────

def test_reaction_author_can_delete_own_reaction(client):
    alice_id = _register_and_login(client, ALICE)
    bob_id = _register_and_login(client, BOB)
    _make_friends(client, ALICE, BOB, alice_id, bob_id)

    client.post(_reactions_url(alice_id), json={"reaction": "like"})

    res = client.delete(_reactions_url(alice_id))
    assert res.status_code == 200


def test_top10_owner_cannot_delete_others_reaction(client):
    alice_id = _register_and_login(client, ALICE)
    bob_id = _register_and_login(client, BOB)
    _make_friends(client, ALICE, BOB, alice_id, bob_id)

    client.post(_reactions_url(alice_id), json={"reaction": "like"})

    _login(client, ALICE)
    res = client.delete(_reactions_url(alice_id))
    assert res.status_code == 404


def test_non_friend_cannot_delete_reaction(client):
    alice_id = _register_and_login(client, ALICE)
    bob_id = _register_and_login(client, BOB)
    _make_friends(client, ALICE, BOB, alice_id, bob_id)

    client.post(_reactions_url(alice_id), json={"reaction": "like"})

    _login(client, ALICE)
    client.delete(f"{FRIENDS_DEL}/{bob_id}")

    _login(client, BOB)
    res = client.delete(_reactions_url(alice_id))
    assert res.status_code == 200


# ── Comments — read requires friendship or public ────────────────────

def test_friend_can_read_comments(client):
    alice_id = _register_and_login(client, ALICE)
    bob_id = _register_and_login(client, BOB)
    _make_friends(client, ALICE, BOB, alice_id, bob_id)

    client.post(_comments_url(alice_id), json={"body": "Nice list!"})
    res = client.get(_comments_url(alice_id))
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_non_friend_cannot_read_comments_on_private_top10(client, session):
    alice_id = _register_and_login(client, ALICE)
    bob_id = _register_and_login(client, BOB)
    _make_friends(client, ALICE, BOB, alice_id, bob_id)

    client.post(_comments_url(alice_id), json={"body": "Nice list!"})
    _set_top10_public(session, alice_id, False)

    _register_and_login(client, CHARLIE)
    res = client.get(_comments_url(alice_id))
    assert res.status_code == 403


# ── Reactions — read requires friendship or public ───────────────────

def test_non_friend_cannot_read_reactions_on_private_top10(client, session):
    alice_id = _register_and_login(client, ALICE)
    bob_id = _register_and_login(client, BOB)
    _make_friends(client, ALICE, BOB, alice_id, bob_id)

    client.post(_reactions_url(alice_id), json={"reaction": "like"})
    _set_top10_public(session, alice_id, False)

    _register_and_login(client, CHARLIE)
    res = client.get(_reactions_url(alice_id))
    assert res.status_code == 403


# ── Public top10 — non-friends can interact ──────────────────────────

def test_non_friend_can_comment_on_public_top10(client, session):
    alice_id = _register_and_login(client, ALICE)
    _set_top10_public(session, alice_id, True)
    _register_and_login(client, BOB)

    res = client.post(_comments_url(alice_id), json={"body": "Cool taste!"})
    assert res.status_code == 200


def test_non_friend_can_edit_comment_on_public_top10(client, session):
    alice_id = _register_and_login(client, ALICE)
    _set_top10_public(session, alice_id, True)
    _register_and_login(client, BOB)

    comment_id = client.post(_comments_url(alice_id), json={"body": "Cool taste!"}).json()["id"]
    res = client.post(f"{_comments_url(alice_id)}/{comment_id}", json={"body": "Even cooler!"})
    assert res.status_code == 200
    assert res.json()["body"] == "Even cooler!"


def test_non_friend_can_read_comments_on_public_top10(client, session):
    alice_id = _register_and_login(client, ALICE)
    _set_top10_public(session, alice_id, True)
    bob_id = _register_and_login(client, BOB)

    # Bob comments (public top10 allows it)
    client.post(_comments_url(alice_id), json={"body": "Cool taste!"})

    # Charlie reads (also non-friend, public top10)
    _register_and_login(client, CHARLIE)
    res = client.get(_comments_url(alice_id))
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_non_friend_can_react_to_public_top10(client, session):
    alice_id = _register_and_login(client, ALICE)
    _set_top10_public(session, alice_id, True)
    _register_and_login(client, BOB)

    res = client.post(_reactions_url(alice_id), json={"reaction": "like"})
    assert res.status_code == 200


def test_non_friend_can_read_reactions_on_public_top10(client, session):
    alice_id = _register_and_login(client, ALICE)
    _set_top10_public(session, alice_id, True)
    bob_id = _register_and_login(client, BOB)
    _make_friends(client, ALICE, BOB, alice_id, bob_id)

    # Bob reacts
    client.post(_reactions_url(alice_id), json={"reaction": "like"})
    _set_top10_public(session, alice_id, True)

    # Charlie reads reactions (non-friend, public top10)
    _register_and_login(client, CHARLIE)
    res = client.get(_reactions_url(alice_id))
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_edit_blocked_after_top10_goes_private(client, session):
    """Bob comments while public, Alice makes it private, Bob can no longer edit."""
    alice_id = _register_and_login(client, ALICE)
    _set_top10_public(session, alice_id, True)
    _register_and_login(client, BOB)

    comment_id = client.post(_comments_url(alice_id), json={"body": "Cool!"}).json()["id"]

    # Alice makes top10 private
    _set_top10_public(session, alice_id, False)

    res = client.post(f"{_comments_url(alice_id)}/{comment_id}", json={"body": "Hacked!"})
    assert res.status_code == 422


# ── Owner can interact with own comments/reactions ───────────────────

def test_owner_can_read_own_comments_on_private_top10(client, session):
    alice_id = _register_and_login(client, ALICE)
    bob_id = _register_and_login(client, BOB)
    _make_friends(client, ALICE, BOB, alice_id, bob_id)

    client.post(_comments_url(alice_id), json={"body": "Nice list!"})
    _set_top10_public(session, alice_id, False)

    _login(client, ALICE)
    res = client.get(_comments_url(alice_id))
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_owner_can_read_own_reactions_on_private_top10(client, session):
    alice_id = _register_and_login(client, ALICE)
    bob_id = _register_and_login(client, BOB)
    _make_friends(client, ALICE, BOB, alice_id, bob_id)

    client.post(_reactions_url(alice_id), json={"reaction": "like"})
    _set_top10_public(session, alice_id, False)

    _login(client, ALICE)
    res = client.get(_reactions_url(alice_id))
    assert res.status_code == 200
    assert len(res.json()) == 1


# ── Blocked users cannot interact ────────────────────────────────────

def test_blocked_user_cannot_comment_on_public_top10(client, session):
    alice_id = _register_and_login(client, ALICE)
    bob_id = _register_and_login(client, BOB)
    _set_top10_public(session, alice_id, True)

    # Alice blocks Bob
    _login(client, ALICE)
    client.post(f"{FRIENDS_BLOCK}/{bob_id}")

    _login(client, BOB)
    res = client.post(_comments_url(alice_id), json={"body": "Spam!"})
    assert res.status_code == 422


def test_blocked_user_cannot_react_to_public_top10(client, session):
    alice_id = _register_and_login(client, ALICE)
    bob_id = _register_and_login(client, BOB)
    _set_top10_public(session, alice_id, True)

    _login(client, ALICE)
    client.post(f"{FRIENDS_BLOCK}/{bob_id}")

    _login(client, BOB)
    res = client.post(_reactions_url(alice_id), json={"reaction": "like"})
    assert res.status_code == 403


def test_blocked_user_cannot_read_comments_on_public_top10(client, session):
    alice_id = _register_and_login(client, ALICE)
    bob_id = _register_and_login(client, BOB)
    _make_friends(client, ALICE, BOB, alice_id, bob_id)

    client.post(_comments_url(alice_id), json={"body": "Nice!"})
    _set_top10_public(session, alice_id, True)

    # Alice blocks Bob
    _login(client, ALICE)
    client.post(f"{FRIENDS_BLOCK}/{bob_id}")

    _login(client, BOB)
    res = client.get(_comments_url(alice_id))
    assert res.status_code == 403
