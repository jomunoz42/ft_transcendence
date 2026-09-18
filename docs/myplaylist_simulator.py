#!/usr/bin/env python3
"""MyPlaylist — an executable product map, not a production application.

Run with: python3 docs/myplaylist_simulator.py

All data below is deliberately small, local, fictional and disposable.  Teammates
should feel free to edit a dictionary or a screen while discussing the product.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime


# ---------------------------------------------------------------------------
# PRODUCT SEED DATA — edit these structures to change the demo story.
# A song id is used instead of a real provider id because the provider is TBD.
# ---------------------------------------------------------------------------

USERS = {
    "joao": {"name": "João", "avatar": "[J]", "bio": "Late-night electronic music and songs with a pulse.", "online": True, "last_seen": "now", "privacy": "Friends can see my Top 10", "genres": ["Electronic", "Indie", "Ambient"]},
    "pedro": {"name": "Pedro", "avatar": "[P]", "bio": "Guitar riffs, rainy afternoons, no skips.", "online": True, "last_seen": "now", "privacy": "Public Top 10", "genres": ["Alternative", "Rock", "Indie"]},
    "victor": {"name": "Victor", "avatar": "[V]", "bio": "A database of memories disguised as playlists.", "online": False, "last_seen": "18 min ago", "privacy": "Public Top 10", "genres": ["Hip-hop", "Jazz", "Electronic"]},
    "andre": {"name": "André", "avatar": "[A]", "bio": "The social side of a very specific musical universe.", "online": True, "last_seen": "now", "privacy": "Friends can see my Top 10", "genres": ["R&B", "Soul", "Pop"]},
    "lina": {"name": "Lina", "avatar": "[L]", "bio": "Looking for new voices and excellent album openers.", "online": False, "last_seen": "yesterday", "privacy": "Public Top 10", "genres": ["Indie", "Folk", "Dream pop"]},
    "sam": {"name": "Sam", "avatar": "[S]", "bio": "Jazz, post-rock, and the occasional seven-minute song.", "online": True, "last_seen": "now", "privacy": "Public Top 10", "genres": ["Jazz", "Post-rock", "Ambient"]},
}

SONGS = {
    "s1": ("Midnight City", "M83", "Hurry Up, We're Dreaming", "Electronic"),
    "s2": ("Teardrop", "Massive Attack", "Mezzanine", "Trip-hop"),
    "s3": ("The Less I Know the Better", "Tame Impala", "Currents", "Alternative"),
    "s4": ("Nights", "Frank Ocean", "Blonde", "R&B"),
    "s5": ("Everything In Its Right Place", "Radiohead", "Kid A", "Alternative"),
    "s6": ("Motion Sickness", "Phoebe Bridgers", "Stranger in the Alps", "Indie"),
    "s7": ("Archangel", "Burial", "Untrue", "Electronic"),
    "s8": ("So What", "Miles Davis", "Kind of Blue", "Jazz"),
    "s9": ("Space Song", "Beach House", "Depression Cherry", "Dream pop"),
    "s10": ("Alright", "Kendrick Lamar", "To Pimp a Butterfly", "Hip-hop"),
    "s11": ("Myth", "Beach House", "Bloom", "Dream pop"),
    "s12": ("Little Wing", "Jimi Hendrix", "Axis: Bold as Love", "Rock"),
    "s13": ("Roads", "Portishead", "Dummy", "Trip-hop"),
    "s14": ("How to Disappear Completely", "Radiohead", "Kid A", "Alternative"),
    "s15": ("Cranes in the Sky", "Solange", "A Seat at the Table", "Soul"),
    "s16": ("Svefn-g-englar", "Sigur Rós", "Ágætis byrjun", "Post-rock"),
    "s17": ("Pink + White", "Frank Ocean", "Blonde", "R&B"),
    "s18": ("Harvest Moon", "Neil Young", "Harvest Moon", "Folk"),
    "s19": ("Everything Is Embarrassing", "Sky Ferreira", "Ghost", "Pop"),
    "s20": ("An Ending (Ascent)", "Brian Eno", "Apollo", "Ambient"),
    "s21": ("Windowlicker", "Aphex Twin", "Windowlicker", "Electronic"),
    "s22": ("Both Sides Now", "Joni Mitchell", "Clouds", "Folk"),
}

# Exactly ten entries per user.  Replace/swap is the intended editing model.
TOP10S = {
    "joao": ["s1", "s7", "s5", "s2", "s3", "s20", "s4", "s9", "s14", "s21"],
    "pedro": ["s3", "s5", "s12", "s6", "s14", "s1", "s11", "s18", "s2", "s9"],
    "victor": ["s10", "s8", "s2", "s4", "s7", "s5", "s13", "s1", "s16", "s20"],
    "andre": ["s4", "s15", "s17", "s19", "s9", "s1", "s6", "s3", "s22", "s2"],
    "lina": ["s6", "s9", "s11", "s18", "s22", "s3", "s19", "s14", "s15", "s1"],
    "sam": ["s8", "s16", "s20", "s5", "s2", "s13", "s7", "s14", "s12", "s10"],
}

# Relationship data is intentionally plain: sets are easiest to inspect/edit.
FRIENDS = {
    "joao": {"pedro", "andre"}, "pedro": {"joao", "lina"},
    "victor": {"sam"}, "andre": {"joao"}, "lina": {"pedro"}, "sam": {"victor"},
}
INCOMING_REQUESTS = {key: [] for key in USERS}
INCOMING_REQUESTS["joao"] = ["victor"]
INCOMING_REQUESTS["andre"] = ["lina"]

COMMENTS = [
    {"owner": "joao", "author": "pedro", "text": "That top three is a very convincing late-night set.", "when": "today"},
    {"owner": "pedro", "author": "joao", "text": "Kid A twice in spirit. Respect.", "when": "yesterday"},
    {"owner": "andre", "author": "joao", "text": "Cranes in the Sky at #2 is flawless.", "when": "2 days ago"},
]
# Current visualization: reactions belong to a whole Top 10.  This is open.
REACTIONS = {"joao": {"pedro": "like", "andre": "like"}, "pedro": {"joao": "like", "lina": "like"}, "andre": {"joao": "like"}}

NOTIFICATIONS = {
    "joao": [
        {"text": "Victor sent you a friend request.", "read": False},
        {"text": "Pedro commented on your Top 10.", "read": False},
        {"text": "André is online now.", "read": True},
    ],
    "pedro": [{"text": "Lina liked your Top 10.", "read": False}],
    "victor": [{"text": "Sam accepted your friend request.", "read": True}],
    "andre": [{"text": "Lina sent you a friend request.", "read": False}],
    "lina": [], "sam": [],
}

CONVERSATIONS = {
    ("joao", "pedro"): [("pedro", "Have you heard the new album opener?"), ("joao", "Not yet — sending it to the queue.")],
    ("joao", "andre"): [("andre", "Your #1 is back in my head."), ("joao", "The ranking did its job then.")],
    ("victor", "sam"): [("sam", "That Miles Davis pick is essential.")],
}

CURRENT_USER = "joao"


# ---------------------------------------------------------------------------
# SMALL DISPLAY / INPUT HELPERS.  No terminal package or persistence needed.
# ---------------------------------------------------------------------------

def key_for(a, b):
    return tuple(sorted((a, b)))


def song_text(song_id):
    title, artist, album, genre = SONGS[song_id]
    return f"{title} — {artist}  [{album}; {genre}]"


def person(user_id):
    return USERS[user_id]["name"]


def status(user_id):
    return "● online" if USERS[user_id]["online"] else f"○ offline ({USERS[user_id]['last_seen']})"


def divider():
    print("-" * 72)


def header(title, subtitle=""):
    print("\n" + "=" * 72)
    print(f" MYPLAYLIST  /  {title.upper()}")
    print(f" Logged in as: {person(CURRENT_USER)} {USERS[CURRENT_USER]['avatar']}  |  {status(CURRENT_USER)}")
    if subtitle:
        print(f" {subtitle}")
    print("=" * 72)


def pause():
    input("\nPress Enter to continue... ")


def choice(prompt="Choose: "):
    return input(prompt).strip().lower()


def choose_user(exclude_current=False):
    header("Choose a profile")
    options = [uid for uid in USERS if not (exclude_current and uid == CURRENT_USER)]
    for index, uid in enumerate(options, 1):
        print(f" {index}. {USERS[uid]['avatar']} {person(uid):<8} {status(uid)} — {USERS[uid]['bio']}")
    print(" B. Back")
    answer = choice()
    if answer == "b":
        return None
    if answer.isdigit() and 1 <= int(answer) <= len(options):
        return options[int(answer) - 1]
    print("Please choose one of the listed profiles.")
    pause()
    return None


def relationship(viewed):
    if viewed == CURRENT_USER:
        return "This is your profile."
    if viewed in FRIENDS[CURRENT_USER]:
        return "Friends"
    if viewed in INCOMING_REQUESTS[CURRENT_USER]:
        return "Incoming friend request"
    if CURRENT_USER in INCOMING_REQUESTS[viewed]:
        return "Friend request sent"
    return "Not connected"


def add_notification(user_id, text):
    NOTIFICATIONS[user_id].insert(0, {"text": text, "read": False})


def show_top10_list(user_id, limit=None):
    entries = TOP10S[user_id][:limit]
    for rank, song_id in enumerate(entries, 1):
        print(f" {rank:>2}. {song_text(song_id)}")


def show_profile(viewed=None):
    """The profile is the central visual summary of a musical identity."""
    while True:
        if viewed is None:
            viewed = CURRENT_USER
        user = USERS[viewed]
        header(f"{user['name']}'s profile", f"{user['avatar']}  {status(viewed)}  |  {relationship(viewed)}")
        print(user["bio"])
        print(f"Music identity: {', '.join(user['genres'])}")
        print(f"Privacy concept: {user['privacy']}")
        divider()
        print("TOP 10 PREVIEW")
        show_top10_list(viewed, 3)
        likes = sum(1 for reaction in REACTIONS.get(viewed, {}).values() if reaction == "like")
        print(f"  ♥ {likes} Top 10 likes  |  {len([c for c in COMMENTS if c['owner'] == viewed])} comments")
        divider()
        print(" 1. View full Top 10 and its social activity")
        print(" 2. View music compatibility")
        if viewed != CURRENT_USER:
            print(" 3. Send/accept/cancel/remove friend request")
            print(" 4. Send a message")
        print(" 5. Choose another profile")
        print(" I. Info / implementation considerations")
        print(" B. Back to main menu")
        answer = choice()
        if answer == "1":
            show_top10(viewed)
        elif answer == "2":
            show_compatibility(viewed)
        elif answer == "3" and viewed != CURRENT_USER:
            change_relationship(viewed)
        elif answer == "4" and viewed != CURRENT_USER:
            show_conversation(viewed)
        elif answer == "5":
            selected = choose_user()
            if selected:
                viewed = selected
        elif answer == "i":
            developer_reference("profile")
        elif answer == "b":
            return
        else:
            print("That option is not available here.")
            pause()


def change_relationship(other):
    state = relationship(other)
    header("Friendship action", f"{person(other)} — {state}")
    if state == "Friends":
        print(" 1. Remove friend")
        answer = choice()
        if answer == "1":
            FRIENDS[CURRENT_USER].discard(other)
            FRIENDS[other].discard(CURRENT_USER)
            print(f"You and {person(other)} are no longer friends in this demo.")
    elif state == "Incoming friend request":
        print(" 1. Accept request\n 2. Decline request")
        answer = choice()
        if answer == "1":
            INCOMING_REQUESTS[CURRENT_USER].remove(other)
            FRIENDS[CURRENT_USER].add(other)
            FRIENDS[other].add(CURRENT_USER)
            add_notification(other, f"{person(CURRENT_USER)} accepted your friend request.")
            print(f"You and {person(other)} are now friends.")
        elif answer == "2":
            INCOMING_REQUESTS[CURRENT_USER].remove(other)
            print("Request declined.")
    elif state == "Friend request sent":
        print(" 1. Cancel sent request")
        if choice() == "1":
            INCOMING_REQUESTS[other].remove(CURRENT_USER)
            print("Sent request cancelled.")
    else:
        print(" 1. Send friend request")
        if choice() == "1":
            INCOMING_REQUESTS[other].append(CURRENT_USER)
            add_notification(other, f"{person(CURRENT_USER)} sent you a friend request.")
            print(f"Friend request sent to {person(other)}.")
    pause()


def show_top10(owner=None):
    """One list per user is the product's defining object, not a generic playlist."""
    owner = owner or CURRENT_USER
    while True:
        header(f"{person(owner)}'s Top 10", "CORE — a ranked expression of musical identity")
        show_top10_list(owner)
        reactions = REACTIONS.setdefault(owner, {})
        likes = sum(1 for value in reactions.values() if value == "like")
        dislikes = sum(1 for value in reactions.values() if value == "dislike")
        divider()
        print(f"Community response: ♥ {likes} likes  |  ◇ {dislikes} dislikes")
        print(" 1. View comments")
        print(" 2. Like / dislike this Top 10")
        if owner == CURRENT_USER:
            print(" 3. Swap two rankings")
            print(" 4. Replace one song (keeps exactly 10 entries)")
        print(" 5. Song detail")
        print(" I. Info / implementation considerations")
        print(" B. Back")
        answer = choice()
        if answer == "1":
            show_comments(owner)
        elif answer == "2":
            react_to_top10(owner)
        elif answer == "3" and owner == CURRENT_USER:
            swap_rankings(owner)
        elif answer == "4" and owner == CURRENT_USER:
            replace_song(owner)
        elif answer == "5":
            show_song_from_list(owner)
        elif answer == "i":
            developer_reference("top10")
        elif answer == "b":
            return
        else:
            print("Please choose an available option.")
            pause()


def swap_rankings(owner):
    header("Reorder Top 10", "Temporary in-memory edit")
    print("Enter two ranks from 1 to 10 (for example: 1 then 4).")
    first, second = choice("First rank: "), choice("Second rank: ")
    if first.isdigit() and second.isdigit() and 1 <= int(first) <= 10 and 1 <= int(second) <= 10:
        a, b = int(first) - 1, int(second) - 1
        TOP10S[owner][a], TOP10S[owner][b] = TOP10S[owner][b], TOP10S[owner][a]
        print("Ranks swapped. A real app could notify friends who opt into Top 10 updates.")
    else:
        print("No change: ranks must be numbers from 1 to 10.")
    pause()


def replace_song(owner):
    header("Replace a Top 10 song", "The list remains ten ranked entries")
    rank = choice("Rank to replace (1–10, or B): ")
    if rank == "b":
        return
    if not rank.isdigit() or not 1 <= int(rank) <= 10:
        print("No change: choose a rank from 1 to 10.")
        pause()
        return
    browse_song_catalog(compact=True)
    song_id = choice("Song id to put in that rank (or B): ")
    if song_id in SONGS:
        old = TOP10S[owner][int(rank) - 1]
        TOP10S[owner][int(rank) - 1] = song_id
        print(f"#{rank} changed from {song_text(old)} to {song_text(song_id)}.")
    else:
        print("No change: use one of the listed song ids.")
    pause()


def react_to_top10(owner):
    header("React to Top 10", "Temporary concept: one reaction per person per entire list")
    current = REACTIONS.setdefault(owner, {}).get(CURRENT_USER)
    print(f"Your current reaction: {current or 'none'}")
    print(" 1. Like\n 2. Dislike\n 3. Remove reaction\n B. Back")
    answer = choice()
    if answer == "1":
        REACTIONS[owner][CURRENT_USER] = "like"
    elif answer == "2":
        REACTIONS[owner][CURRENT_USER] = "dislike"
    elif answer == "3":
        REACTIONS[owner].pop(CURRENT_USER, None)
    elif answer == "b":
        return
    else:
        print("No change.")
        pause()
        return
    if owner != CURRENT_USER:
        add_notification(owner, f"{person(CURRENT_USER)} reacted to your Top 10.")
    print("Reaction updated.")
    pause()


def show_comments(owner):
    while True:
        header(f"Comments on {person(owner)}'s Top 10")
        comments = [comment for comment in COMMENTS if comment["owner"] == owner]
        if comments:
            for index, comment in enumerate(comments, 1):
                print(f" {index}. {person(comment['author'])}: {comment['text']}  ({comment['when']})")
        else:
            print("No comments yet — an intentionally quiet social space.")
        divider()
        print(" 1. Add a comment\n I. Info / implementation considerations\n B. Back")
        answer = choice()
        if answer == "1":
            text = input("Comment (leave blank to cancel): ").strip()
            if text:
                COMMENTS.append({"owner": owner, "author": CURRENT_USER, "text": text, "when": "just now"})
                if owner != CURRENT_USER:
                    add_notification(owner, f"{person(CURRENT_USER)} commented on your Top 10.")
                print("Comment added for this session.")
                pause()
        elif answer == "i":
            developer_reference("social")
        elif answer == "b":
            return
        else:
            print("Please choose 1, I, or B.")
            pause()


def show_song_from_list(owner):
    answer = choice("Enter a Top 10 rank (1–10, or B): ")
    if answer.isdigit() and 1 <= int(answer) <= 10:
        show_song_detail(TOP10S[owner][int(answer) - 1])
    elif answer != "b":
        print("Use a rank from 1 to 10.")
        pause()


def browse_song_catalog(compact=False):
    if not compact:
        header("Song catalogue", "Provider-neutral sample music data")
    for song_id, (title, artist, album, genre) in SONGS.items():
        print(f" {song_id:<3} {title:<34.34} — {artist:<18.18} [{genre}]")


def show_music():
    while True:
        browse_song_catalog()
        divider()
        print(" 1. Open song detail by id\n 2. Search songs/artists\n I. Info / implementation considerations\n B. Back")
        answer = choice()
        if answer == "1":
            song_id = choice("Song id (e.g. s1): ")
            if song_id in SONGS:
                show_song_detail(song_id)
            else:
                print("Unknown song id.")
                pause()
        elif answer == "2":
            show_search(start_kind="music")
        elif answer == "i":
            developer_reference("music")
        elif answer == "b":
            return
        else:
            print("Please choose an available option.")
            pause()


def show_song_detail(song_id):
    title, artist, album, genre = SONGS[song_id]
    header(f"Song: {title}", "A song is discoverable beyond the list it appears in")
    print(f"Artist: {artist}\nAlbum: {album}\nGenre concept: {genre}")
    print("External link: [music provider to be chosen — open song / artist / album]")
    ranked = []
    for user_id, entries in TOP10S.items():
        if song_id in entries:
            ranked.append((entries.index(song_id) + 1, user_id))
    divider()
    print("APPEARS IN THESE TOP 10s")
    if ranked:
        for rank, user_id in sorted(ranked):
            print(f" #{rank:<2} {person(user_id):<8} ({'friend' if user_id in FRIENDS[CURRENT_USER] else 'community'})")
    else:
        print("No one in the demo ranks this song yet.")
    print("\nDiscovery paths: similar users • artist page • songs loved by friends")
    print(" I. Info / implementation considerations\n B. Back")
    while True:
        answer = choice()
        if answer == "i":
            developer_reference("music")
            return
        if answer == "b":
            return
        print("Press I or B.")


def show_friends():
    while True:
        header("Friends & social graph", "CORE — connections unlock social context")
        friends = sorted(FRIENDS[CURRENT_USER], key=person)
        print("FRIENDS")
        for user_id in friends or []:
            print(f" {USERS[user_id]['avatar']} {person(user_id):<8} {status(user_id)}")
        if not friends:
            print(" No friends yet.")
        print("\nINCOMING REQUESTS")
        for user_id in INCOMING_REQUESTS[CURRENT_USER] or []:
            print(f" {USERS[user_id]['avatar']} {person(user_id)} — {USERS[user_id]['bio']}")
        if not INCOMING_REQUESTS[CURRENT_USER]:
            print(" None")
        outgoing = [uid for uid in USERS if CURRENT_USER in INCOMING_REQUESTS[uid]]
        print("\nOUTGOING REQUESTS: " + (", ".join(person(uid) for uid in outgoing) or "None"))
        divider()
        print(" 1. View a profile\n 2. Manage an incoming request\n 3. Find people / send request\n I. Info / implementation considerations\n B. Back")
        answer = choice()
        if answer == "1":
            selected = choose_user(exclude_current=True)
            if selected:
                show_profile(selected)
        elif answer == "2":
            manage_incoming_request()
        elif answer == "3":
            selected = choose_user(exclude_current=True)
            if selected:
                change_relationship(selected)
        elif answer == "i":
            developer_reference("friends")
        elif answer == "b":
            return
        else:
            print("Please choose an available option.")
            pause()


def manage_incoming_request():
    requests = INCOMING_REQUESTS[CURRENT_USER]
    if not requests:
        print("There are no incoming requests to manage.")
        pause()
        return
    header("Manage friend request")
    for index, user_id in enumerate(requests, 1):
        print(f" {index}. {person(user_id)}")
    answer = choice("Request number (or B): ")
    if answer.isdigit() and 1 <= int(answer) <= len(requests):
        change_relationship(requests[int(answer) - 1])


def compatibility_data(other):
    mine, theirs = set(TOP10S[CURRENT_USER]), set(TOP10S[other])
    common_songs = mine & theirs
    my_artists = {SONGS[song_id][1] for song_id in mine}
    their_artists = {SONGS[song_id][1] for song_id in theirs}
    common_artists = my_artists & their_artists
    # Illustrative, transparent calculation — deliberately not a recommendation model.
    score = min(100, len(common_songs) * 8 + len(common_artists) * 6 + len(set(USERS[CURRENT_USER]["genres"]) & set(USERS[other]["genres"])) * 5 + 20)
    return score, common_songs, common_artists


def show_compatibility(other=None):
    if other is None or other == CURRENT_USER:
        selected = choose_user(exclude_current=True)
        if not selected:
            return
        other = selected
    score, common_songs, common_artists = compatibility_data(other)
    header("Music compatibility", f"EXPERIMENTAL — {person(CURRENT_USER)} × {person(other)}")
    print(f"\n                 {score}% compatible\n")
    print("COMMON SONGS")
    for song_id in common_songs:
        print(f" • {song_text(song_id)}")
    if not common_songs:
        print(" • No shared Top 10 songs — difference can be interesting too.")
    print("\nCOMMON ARTISTS: " + (", ".join(sorted(common_artists)) or "None yet"))
    print("DIFFERENT TASTES")
    print(f" • {person(CURRENT_USER)}: {', '.join(USERS[CURRENT_USER]['genres'])}")
    print(f" • {person(other)}: {', '.join(USERS[other]['genres'])}")
    print("\n I. Info / implementation considerations\n B. Back")
    answer = choice()
    if answer == "i":
        developer_reference("compatibility")


def show_discover():
    while True:
        header("Discover", "PLANNED — people and music through musical identity")
        mine = set(TOP10S[CURRENT_USER])
        candidates = [uid for uid in USERS if uid != CURRENT_USER]
        compatible = sorted(candidates, key=lambda uid: compatibility_data(uid)[0], reverse=True)
        print("PEOPLE WITH SIMILAR TASTE")
        for user_id in compatible[:3]:
            score, shared, _ = compatibility_data(user_id)
            print(f" {person(user_id):<8} {score:>3}%  |  {len(shared)} shared Top 10 songs  |  {USERS[user_id]['bio']}")
        counts = Counter(song_id for entries in TOP10S.values() for song_id in entries)
        print("\nTRENDING IN THIS SMALL COMMUNITY")
        for song_id, count in counts.most_common(4):
            print(f" {song_text(song_id)} — in {count} Top 10s")
        friend_songs = Counter(song_id for friend in FRIENDS[CURRENT_USER] for song_id in TOP10S[friend] if song_id not in mine)
        print("\nSONGS YOUR FRIENDS LOVE (not in your Top 10)")
        for song_id, count in friend_songs.most_common(3):
            print(f" {song_text(song_id)} — {count} friend(s)")
        divider()
        print(" 1. Open a suggested profile\n 2. Open a trending song\n 3. Random profile discovery\n I. Info / implementation considerations\n B. Back")
        answer = choice()
        if answer == "1":
            selected = choose_user(exclude_current=True)
            if selected:
                show_profile(selected)
        elif answer == "2":
            song_id = choice("Trending song id (e.g. s1): ")
            if song_id in SONGS:
                show_song_detail(song_id)
            else:
                print("Unknown song id.")
                pause()
        elif answer == "3":
            # Deterministic "random" option lets a demo run remain repeatable.
            selected = next(uid for uid in USERS if uid not in {CURRENT_USER, *FRIENDS[CURRENT_USER]})
            print(f"Today's discovery card: {person(selected)}")
            pause()
            show_profile(selected)
        elif answer == "i":
            developer_reference("discover")
        elif answer == "b":
            return
        else:
            print("Please choose an available option.")
            pause()


def show_search(start_kind=None):
    while True:
        header("Search", "PLANNED — users, songs and artists point back into the product")
        term = input("Search term (or B to go back): ").strip()
        if term.lower() == "b":
            return
        if not term:
            print("Try a name, song title, artist, or genre.")
            continue
        needle = term.lower()
        user_matches = [uid for uid, data in USERS.items() if needle in data["name"].lower() or needle in data["bio"].lower()]
        song_matches = [sid for sid, data in SONGS.items() if needle in " ".join(data).lower()]
        print("\nUSERS")
        for uid in user_matches:
            print(f" U {uid:<7} {person(uid)} — {USERS[uid]['bio']}")
        print("\nSONGS / ARTISTS")
        for sid in song_matches:
            print(f" S {sid:<7} {song_text(sid)}")
        if not user_matches and not song_matches:
            print(" No matches in the demo catalogue.")
        print("\nOpen with U <user id> or S <song id>; Enter to search again; B to go back.")
        action = input("> ").strip().lower().split()
        if len(action) == 2 and action[0] == "u" and action[1] in USERS:
            show_profile(action[1])
        elif len(action) == 2 and action[0] == "s" and action[1] in SONGS:
            show_song_detail(action[1])
        elif action and action[0] == "b":
            return


def show_notifications():
    while True:
        header("Notifications", "PLANNED — social events can arrive live")
        notices = NOTIFICATIONS[CURRENT_USER]
        if notices:
            for index, notice in enumerate(notices, 1):
                marker = "NEW" if not notice["read"] else "   "
                print(f" {index:>2}. [{marker}] {notice['text']}")
        else:
            print("Nothing here yet.")
        divider()
        print(" 1. Mark all as read\n 2. Simulate a live presence notification\n I. Info / implementation considerations\n B. Back")
        answer = choice()
        if answer == "1":
            for notice in notices:
                notice["read"] = True
            print("All notifications marked as read.")
            pause()
        elif answer == "2":
            candidate = next(uid for uid in USERS if uid != CURRENT_USER and not USERS[uid]["online"])
            USERS[candidate]["online"] = True
            USERS[candidate]["last_seen"] = "now"
            add_notification(CURRENT_USER, f"{person(candidate)} is online now. [simulated live event]")
            print("A presence change appeared immediately in the product view.")
            pause()
        elif answer == "i":
            developer_reference("notifications")
        elif answer == "b":
            return
        else:
            print("Please choose an available option.")
            pause()


def conversation_partners():
    partners = set(FRIENDS[CURRENT_USER])
    for pair in CONVERSATIONS:
        if CURRENT_USER in pair:
            partners.add(pair[0] if pair[1] == CURRENT_USER else pair[1])
    return sorted(partners, key=person)


def show_messages():
    while True:
        header("Messages", "CORE/PLANNED — direct, deliberately scoped chat")
        partners = conversation_partners()
        for index, uid in enumerate(partners, 1):
            messages = CONVERSATIONS.get(key_for(CURRENT_USER, uid), [])
            preview = messages[-1][1] if messages else "No messages yet"
            print(f" {index}. {person(uid):<8} {status(uid):<20} {preview[:34]}")
        divider()
        print(" 1. Open a conversation\n 2. Start a conversation with a friend\n I. Info / implementation considerations\n B. Back")
        answer = choice()
        if answer in {"1", "2"}:
            selected = choose_user(exclude_current=True)
            if selected:
                show_conversation(selected)
        elif answer == "i":
            developer_reference("messages")
        elif answer == "b":
            return
        else:
            print("Please choose an available option.")
            pause()


def show_conversation(other):
    while True:
        header(f"Chat with {person(other)}", status(other))
        messages = CONVERSATIONS.setdefault(key_for(CURRENT_USER, other), [])
        if messages:
            for author, text in messages:
                label = "You" if author == CURRENT_USER else person(author)
                print(f" {label}: {text}")
        else:
            print("No messages yet — start a small conversation.")
        divider()
        print(" 1. Send message\n B. Back")
        answer = choice()
        if answer == "1":
            text = input("Message (blank cancels): ").strip()
            if text:
                messages.append((CURRENT_USER, text))
                add_notification(other, f"New message from {person(CURRENT_USER)}.")
                print("Message sent for this session.")
                pause()
        elif answer == "b":
            return
        else:
            print("Please choose 1 or B.")
            pause()


def show_identity():
    header("Music identity", "PLANNED — user-facing analytics, not operational monitoring")
    entries = TOP10S[CURRENT_USER]
    artists = Counter(SONGS[song_id][1] for song_id in entries)
    genres = Counter(SONGS[song_id][3] for song_id in entries)
    print("MOST REPRESENTED ARTISTS")
    for artist, count in artists.most_common(4):
        print(f" {artist:<25} {'▮' * count} ({count})")
    print("\nGENRE SHAPE")
    for genre, count in genres.most_common():
        print(f" {genre:<25} {'▮' * count} ({count})")
    shared = Counter(song_id for uid, list_ in TOP10S.items() if uid != CURRENT_USER for song_id in list_)
    unique = [song_id for song_id in entries if shared[song_id] == 0]
    print("\nUNIQUENESS")
    print(f" {len(unique)}/10 of your selections are not in another demo Top 10.")
    print("\nFuture discussion: visible Top 10 history? profile-view counts? genre confidence from provider data?")
    print("\n I. Info / implementation considerations\n B. Back")
    if choice() == "i":
        developer_reference("identity")


def show_settings():
    while True:
        header("Settings & account", "PRODUCT MAP — concepts, not authentication implementation")
        print(f"Display name: {person(CURRENT_USER)}\nBio: {USERS[CURRENT_USER]['bio']}\nPrivacy: {USERS[CURRENT_USER]['privacy']}")
        divider()
        print(" 1. Edit bio (lightweight demo)\n 2. Toggle Top 10 privacy concept\n 3. Account / security ideas\n 4. Delete account concept\n 5. Logout concept\n I. Info / implementation considerations\n B. Back")
        answer = choice()
        if answer == "1":
            bio = input("New bio (blank cancels): ").strip()
            if bio:
                USERS[CURRENT_USER]["bio"] = bio
                print("Bio changed for this session.")
                pause()
        elif answer == "2":
            current = USERS[CURRENT_USER]["privacy"]
            USERS[CURRENT_USER]["privacy"] = "Public Top 10" if current != "Public Top 10" else "Friends can see my Top 10"
            print(f"Privacy concept is now: {USERS[CURRENT_USER]['privacy']}")
            pause()
        elif answer == "3":
            print("Real-product ideas: password change, sessions/devices, 2FA/OAuth, data export, blocking, report abuse.")
            pause()
        elif answer == "4":
            print("Design question: deletion should have a confirmation and define what happens to comments, messages and social links.")
            pause()
        elif answer == "5":
            print("Logout exists in the real product. This simulator keeps a seeded session so exploration stays fast.")
            pause()
        elif answer == "i":
            developer_reference("settings")
        elif answer == "b":
            return
        else:
            print("Please choose an available option.")
            pause()


def developer_reference(screen="general"):
    """Concise bridge from product discussion to likely implementation concerns."""
    references = {
        "profile": ("A profile makes musical identity visible and navigable.", "User, Profile, Top10Entry, Friendship", "Profile read/edit; relationship state; Top 10 preview.", "presence.updated; friendship.changed", "Who can see a private profile/list? Do we need blocking or following?"),
        "top10": ("One ranked Top 10 is MyPlaylist's defining social object.", "Top10, Top10Entry, Song, Reaction, Comment", "Rank validation, reorder/replace, list read, social activity.", "top10.updated; comment.created; reaction.changed", "React to the whole list, individual songs, or both? Is history visible?"),
        "social": ("Comments and reactions turn a list into a conversation.", "Comment, Reaction, User, Top10", "Create/read/moderate social interactions.", "comment.created; reaction.changed", "Can everyone comment, only friends, or based on profile privacy?"),
        "music": ("Music needs a provider-neutral representation until a source is chosen.", "Song, Artist, Album, ProviderLink, Top10Entry", "Search/provider adapter; cached/display-safe metadata.", "Optional: song metadata refreshed", "Which provider, licensing terms, rate limits, and outage fallback are acceptable?"),
        "friends": ("Friendship connects profiles, discovery, chat and notification permissions.", "Friendship / FriendRequest, User, Notification", "Send, accept, decline and remove friendship; authorization rules.", "friend_request.received; friendship.changed", "Mutual friends only, or also a one-way follow model?"),
        "discover": ("Discovery makes individual Top 10s useful beyond direct friends.", "Top10Entry, Song, User, Friendship", "Filtered/ranked discovery queries; explainable ordering.", "Optional live Top 10 updates", "Popularity can create a loop—how do we preserve variety and smaller tastes?"),
        "compatibility": ("Compatibility is a playful explanation of overlap, not an ML claim.", "Top10Entry, Song, Artist, User", "Transparent score derived from shared songs/artists/genres.", "None required initially", "Should rank weight matter? How much detail should users see about the score?"),
        "notifications": ("Notifications bring relevant social changes back to the user.", "Notification, User, FriendRequest, Comment, Reaction, Message", "Read state, preferences, event-to-notification policy.", "notification.created; presence.updated", "Which events deserve alerts, and how can users tune or mute them?"),
        "messages": ("Chat supports friend-to-friend musical conversation without becoming Discord.", "Conversation, Message, User, Friendship", "Conversation list, send/read, authorization, unread counts.", "message.created; message.read", "Can non-friends message? retention, reporting, blocking, and moderation?"),
        "identity": ("Analytics reflect a user's musical identity; they are not Prometheus/Grafana.", "Top10Entry, Song, Artist, optional History", "Aggregation queries and privacy-aware profile display.", "Optional Top 10 change event", "Are genres provider metadata? Should profile views or history be visible?"),
        "settings": ("Settings expose account, privacy and consent concepts.", "User, Profile, Preference, Session", "Validated edits, privacy checks, deletion/export workflows.", "Optional preference updates", "What is public by default, and how do deleted users/content appear?"),
        "general": ("This file is a shared product map, intentionally not an architecture blueprint.", "User, Profile, Top10Entry, Song, Friendship, Comment, Reaction, Message, Notification", "Small vertical flows first: profile → Top 10 → friend → view list.", "Presence, notifications, messages, and selective social updates.", "Agree on first-version scope before committing to experiments."),
    }
    concept, data, backend, realtime, questions = references[screen]
    header("Info / implementation considerations")
    print(f"PRODUCT CONCEPT\n {concept}\n\nLIKELY DATA\n {data}\n\nBACKEND RESPONSIBILITY (CONCEPTUAL)\n {backend}\n\nREAL-TIME POSSIBILITY\n {realtime}\n\n42 / PROJECT NOTES\n Frameworks, PostgreSQL/ORM, user interaction, real-time and notifications may be relevant. Monitoring belongs to the operational stack, not this menu.\n\nOPEN QUESTION\n {questions}")
    pause()


def switch_user():
    global CURRENT_USER
    selected = choose_user()
    if selected:
        CURRENT_USER = selected
        print(f"Session switched instantly to {person(CURRENT_USER)}. No login simulation needed.")
        pause()


def main_menu():
    while True:
        unread = sum(not notice["read"] for notice in NOTIFICATIONS[CURRENT_USER])
        header("Product map", "CORE features first; PLANNED and EXPERIMENTAL are conversation starters")
        print(" 1. My Profile                 8. Messages")
        print(" 2. My Top 10                  9. Music identity / statistics")
        print(" 3. Friends & requests        10. Settings & account")
        print(" 4. Discover                   I. Info / project reference")
        print(" 5. Search                     U. Switch user")
        print(" 6. Songs / music              0. Exit")
        print(f" 7. Notifications{' (' + str(unread) + ' new)' if unread else ''}")
        divider()
        answer = choice()
        if answer == "1": show_profile(CURRENT_USER)
        elif answer == "2": show_top10(CURRENT_USER)
        elif answer == "3": show_friends()
        elif answer == "4": show_discover()
        elif answer == "5": show_search()
        elif answer == "6": show_music()
        elif answer == "7": show_notifications()
        elif answer == "8": show_messages()
        elif answer == "9": show_identity()
        elif answer == "10": show_settings()
        elif answer == "i": developer_reference()
        elif answer == "u": switch_user()
        elif answer == "0":
            print("\nThanks for exploring MyPlaylist. Session changes were intentionally not saved.\n")
            return
        else:
            print("Please enter a menu number, I, U, or 0.")
            pause()


if __name__ == "__main__":
    try:
        main_menu()
    except (KeyboardInterrupt, EOFError):
        print("\n\nMyPlaylist simulator closed. No data was saved.")
