from app.db.models import User, Profile, Friendship
from app.db import SessionLocal

with SessionLocal() as session:
	USERS = [
		User(email='victor@edwed.com', password_hash='wefgvwervrevrevver'),
		User(email='wefew@gmail.com', password_hash='wefwfew'),
		User(email='vic@gmail.com', password_hash='wefewff'),
		User(email='vico@gmail.com', password_hash='wfglowehjgre'),
		User(email='vicky@gmail.com', password_hash='wklgr;kwerhfwer'),
		User(email='bonjour@gmail.com', password_hash='kwjbfvw;kebfew'),
		User(email='hello@gmail.com', password_hash='098650983'),
		User(email='info@gmail.com', password_hash='123456'),
	]

	session.add_all(USERS)
	session.flush()  # Inserts users and populates their IDs before committing.

	PROFILES = [
		Profile(
			user_id=USERS[0].id,
			display_name='Victor',
			bio='Coffee enthusiast and weekend explorer.',
			is_top10_public=True,
		),
		Profile(
			user_id=USERS[1].id,
			display_name='Luna',
			bio='Collecting books, playlists, and good memories.',
			is_top10_public=False,
		),
		Profile(
			user_id=USERS[2].id,
			display_name='Vic',
			bio='Learning to code, one bug at a time.',
			is_top10_public=True,
		),
		Profile(
			user_id=USERS[3].id,
			display_name='Vico',
			bio='Always looking for a new hiking trail.',
			is_top10_public=False,
		),
		Profile(
			user_id=USERS[4].id,
			display_name='Vicky',
			bio='Design, music, and a little bit of chaos.',
			is_top10_public=True,
		),
		Profile(
			user_id=USERS[5].id,
			display_name='Camille',
			bio='Fresh croissants and old movies.',
			is_top10_public=False,
		),
		Profile(
			user_id=USERS[6].id,
			display_name='Alex',
			bio='Here to discover new favorites.',
			is_top10_public=True,
		),
		Profile(
			user_id=USERS[7].id,
			display_name='Robin',
			bio=None,
			is_top10_public=False,
		),
	]

	session.add_all(PROFILES)
	session.flush()

	FRIENDSHIPS = [
		Friendship(requester_id=USERS[0].id, addressee_id=USERS[1].id, status="accepted"),
		Friendship(requester_id=USERS[2].id, addressee_id=USERS[0].id, status="accepted"),
		Friendship(requester_id=USERS[0].id, addressee_id=USERS[4].id, status="accepted"),
		Friendship(requester_id=USERS[3].id, addressee_id=USERS[0].id, status="pending"),
		Friendship(requester_id=USERS[0].id, addressee_id=USERS[5].id, status="declined"),
		Friendship(requester_id=USERS[0].id, addressee_id=USERS[6].id, status="blocked"),
		Friendship(requester_id=USERS[1].id, addressee_id=USERS[7].id, status="accepted"),
	]

	session.add_all(FRIENDSHIPS)

	session.commit()
