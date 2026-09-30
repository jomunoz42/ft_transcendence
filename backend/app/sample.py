from app.db.models import User
from app.db import SessionLocal

session = SessionLocal()

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

for user in USERS:
	session.add(user)
session.commit()
