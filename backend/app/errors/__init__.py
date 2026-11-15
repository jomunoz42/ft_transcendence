from fastapi import HTTPException, status

HTTP_400_BAD_REQUEST				= HTTPException(status.HTTP_400_BAD_REQUEST, "Bad request")
HTTP_401_UNAUTHORIZED				= HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")
HTTP_401_INVALID_CREDENTIALS		= HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
HTTP_401_USER_DELETED				= HTTPException(status.HTTP_401_UNAUTHORIZED, "User was deleted")
HTTP_403_NOT_FRIEND					= HTTPException(status.HTTP_403_FORBIDDEN, "Not friend")
HTTP_404_NOT_FOUND					= HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
HTTP_404_USER_NOT_FOUND				= HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
HTTP_404_PROFILE_NOT_FOUND			= HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
HTTP_409_CONFLICT					= HTTPException(status.HTTP_409_CONFLICT, "Conflict")
HTTP_409_CONFLICT_UNBLOCK_FIRST		= HTTPException(status.HTTP_409_CONFLICT, "unblock first")
HTTP_409_CONFLICT_ONLY_BLOCKER_CAN	= HTTPException(status.HTTP_409_CONFLICT, "declined; only the person who said no can ask again")
HTTP_409_EMAIL_TAKEN				= HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
HTTP_422_UNPROCESSABLE_CONTENT		= HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Cannot act on yourself")
HTTP_422_MUST_BE_FRIEND_TO_COMMENT	= HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "You must be friend to comment a top10")

def http_422_registration(field: str, reason: str):
	return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"field": field, "reason": reason})
