from app.db.models import User, Profile, Friendship, Song, Top10Entry
from app.db import SessionLocal
from app.auth.passwords import hash_password

if __name__ == "__main__":
	with SessionLocal() as session:
		USERS = [
			User(email='victor@edwed.com', password_hash=hash_password('wefgvwervrevrevver')),
			User(email='wefew@gmail.com', password_hash=hash_password('wefwfew')),
			User(email='vic@gmail.com', password_hash=hash_password('wefewff')),
			User(email='vico@gmail.com', password_hash=hash_password('wfglowehjgre')),
			User(email='vicky@gmail.com', password_hash=hash_password('wklgr;kwerhfwer')),
			User(email='bonjour@gmail.com', password_hash=hash_password('kwjbfvw;kebfew')),
			User(email='hello@gmail.com', password_hash=hash_password('098650983')),
			User(email='info@gmail.com', password_hash=hash_password('123456')),
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
		session.flush()

		SONGS = [
			Song(
				provider="Unsure",
				provider_id="1",
				title="Envie",
				artist="Jonhy",
			)
		]

		session.add_all(SONGS)
		session.flush()

		print(SONGS[0].id)
		TOP10S = [
			Top10Entry(
				user_id=USERS[1].id,
				song_id=SONGS[0].id,
				rank=1,
			)
		]

		session.add_all(TOP10S)
		session.flush()

		session.commit()
