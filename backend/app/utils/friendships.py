from . import *

def are_friends(
		session: Session,
		current_user_id: int,
		user_id: int
):
	friendship = session.query(Friendship).filter(
		Friendship.status == "accepted",
		or_(
			and_(
				Friendship.addressee_id == current_user_id,
				Friendship.requester_id == user_id,
			),
			and_(
				Friendship.addressee_id == user_id,
				Friendship.requester_id == current_user_id,
			),
		)
	).first()
	return (friendship is not None)
