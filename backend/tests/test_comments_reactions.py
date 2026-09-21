"""Ticket 06: comments and reactions on a Top 10, verified against real Postgres."""

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.db.models import Top10Comment, Top10Reaction, User


def make_user(session, email):
    user = User(email=email, password_hash="hash")
    session.add(user)
    session.flush()
    return user


def test_a_user_comments_on_another_users_top10(session):
    owner = make_user(session, "owner@myplaylist.test")
    author = make_user(session, "author@myplaylist.test")
    comment = Top10Comment(top10_owner_id=owner.id, author_id=author.id, body="Great number 3!")
    session.add(comment)
    session.flush()
    session.expire_all()

    stored = session.get(Top10Comment, comment.id)

    assert (stored.top10_owner_id, stored.author.email, stored.body) == (owner.id, "author@myplaylist.test", "Great number 3!")


@pytest.mark.parametrize("body", ["", "   "])
def test_a_blank_comment_is_rejected(session, body):
    owner = make_user(session, "owner@myplaylist.test")
    author = make_user(session, "author@myplaylist.test")

    session.add(Top10Comment(top10_owner_id=owner.id, author_id=author.id, body=body))

    with pytest.raises(IntegrityError):
        session.flush()


def test_changing_a_reaction_keeps_one_row(session):
    owner = make_user(session, "owner@myplaylist.test")
    author = make_user(session, "author@myplaylist.test")
    reaction = Top10Reaction(top10_owner_id=owner.id, author_id=author.id, reaction="like")
    session.add(reaction)
    session.flush()

    reaction.reaction = "dislike"
    session.flush()
    session.expire_all()

    rows = session.scalars(select(Top10Reaction)).all()
    assert [(r.author_id, r.reaction) for r in rows] == [(author.id, "dislike")]


def test_a_user_has_only_one_reaction_per_top10(session):
    owner = make_user(session, "owner@myplaylist.test")
    author = make_user(session, "author@myplaylist.test")
    session.add(Top10Reaction(top10_owner_id=owner.id, author_id=author.id, reaction="like"))
    session.flush()

    session.add(Top10Reaction(top10_owner_id=owner.id, author_id=author.id, reaction="dislike"))

    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize("value", ["lik", "Like", "love"])
def test_a_reaction_must_be_like_or_dislike(session, value):
    owner = make_user(session, "owner@myplaylist.test")
    author = make_user(session, "author@myplaylist.test")

    session.add(Top10Reaction(top10_owner_id=owner.id, author_id=author.id, reaction=value))

    with pytest.raises(IntegrityError):
        session.flush()


def test_a_user_cannot_react_to_their_own_top10(session):
    owner = make_user(session, "owner@myplaylist.test")

    session.add(Top10Reaction(top10_owner_id=owner.id, author_id=owner.id, reaction="like"))

    with pytest.raises(IntegrityError):
        session.flush()


def test_a_user_can_comment_on_their_own_top10(session):
    """Owners may reply to comments; only self-reactions are blocked."""
    owner = make_user(session, "owner@myplaylist.test")

    session.add(Top10Comment(top10_owner_id=owner.id, author_id=owner.id, body="Thanks!"))
    session.flush()


def comment_and_reaction(session, owner, author):
    comment = Top10Comment(top10_owner_id=owner.id, author_id=author.id, body="Nice list")
    reaction = Top10Reaction(top10_owner_id=owner.id, author_id=author.id, reaction="like")
    session.add_all([comment, reaction])
    session.flush()
    return comment.id, reaction.id


def delete_user(session, user):
    # Direct statement, not session.delete(), so the database's ON DELETE CASCADE
    # does the work rather than SQLAlchemy's in-Python cascade.
    session.execute(delete(User).where(User.id == user.id))
    session.expire_all()


def test_deleting_a_user_deletes_what_they_wrote(session):
    owner = make_user(session, "owner@myplaylist.test")
    author = make_user(session, "author@myplaylist.test")
    comment_id, reaction_id = comment_and_reaction(session, owner, author)

    delete_user(session, author)

    assert session.get(Top10Comment, comment_id) is None
    assert session.get(Top10Reaction, reaction_id) is None


def test_deleting_a_user_deletes_what_was_written_on_their_top10(session):
    owner = make_user(session, "owner@myplaylist.test")
    author = make_user(session, "author@myplaylist.test")
    comment_id, reaction_id = comment_and_reaction(session, owner, author)

    delete_user(session, owner)

    assert session.get(Top10Comment, comment_id) is None
    assert session.get(Top10Reaction, reaction_id) is None
