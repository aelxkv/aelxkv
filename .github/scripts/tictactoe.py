"""Tic-tac-toe played through GitHub issues.

A visitor clicks a square in the README. That opens a pre-filled issue whose
title looks like  ttt|move|4  (squares 0-8, left to right, top to bottom).
This script reads the title, plays the move, lets the bot answer, then
rewrites the board inside README.md and saves the game state.

SECURITY: the issue title and author name are untrusted input. They arrive
only through environment variables, are checked against strict regexes, and
are never passed to a shell.
"""
import json
import os
import random
import re
import sys
from urllib.parse import quote

REPO = "aelxkv/aelxkv"
README = "README.md"
STATE_PATH = "game/state.json"
START, END = "<!--TTT:START-->", "<!--TTT:END-->"

LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8),
         (0, 3, 6), (1, 4, 7), (2, 5, 8),
         (0, 4, 8), (2, 4, 6)]
NAMES = ["top-left", "top-middle", "top-right",
         "middle-left", "center", "middle-right",
         "bottom-left", "bottom-middle", "bottom-right"]
MISTAKE_CHANCE = 0.35  # the bot plays a random square this often, so it can lose


def fresh(tally=None):
    return {
        "board": [" "] * 9,
        "status": "playing",  # playing | x_won | o_won | draw
        "last": "",
        "tally": tally or {"visitors": 0, "bot": 0, "draws": 0},
    }


def load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            state = json.load(f)
        if len(state["board"]) != 9:
            raise ValueError("bad board")
        return state
    except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError):
        return fresh()


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
        f.write("\n")


def winner(board):
    for a, b, c in LINES:
        if board[a] != " " and board[a] == board[b] == board[c]:
            return board[a]
    return None


def line_to_finish(board, mark):
    for line in LINES:
        cells = [board[i] for i in line]
        if cells.count(mark) == 2 and cells.count(" ") == 1:
            return line[cells.index(" ")]
    return None


def bot_move(board):
    empty = [i for i, v in enumerate(board) if v == " "]
    if random.random() < MISTAKE_CHANCE:
        return random.choice(empty)
    for mark in ("O", "X"):  # win first, then block
        move = line_to_finish(board, mark)
        if move is not None:
            return move
    for pref in (4, 0, 2, 6, 8, 1, 3, 5, 7):
        if board[pref] == " ":
            return pref


def issue_link(title):
    body = "Just press 'Submit new issue'. Please don't edit the title."
    return (f"https://github.com/{REPO}/issues/new"
            f"?title={quote(title, safe='')}&body={quote(body, safe='')}")


def render(state):
    board = state["board"]
    rows = []
    for r in range(3):
        cells = []
        for c in range(3):
            i = r * 3 + c
            if board[i] in ("X", "O"):
                cells.append(f"**{board[i]}**")
            elif state["status"] == "playing":
                cells.append(f"[·]({issue_link(f'ttt|move|{i}')})")
            else:
                cells.append("·")
        rows.append("| " + " | ".join(cells) + " |")
    table = "| | | |\n|:-:|:-:|:-:|\n" + "\n".join(rows)

    again = f"[Play again]({issue_link('ttt|new')})"
    status = {
        "playing": "Your turn. You're **X**, the bot is **O**. Click a **·** to play.",
        "x_won": f"A visitor won this round. {again}",
        "o_won": f"The bot won this round. {again}",
        "draw": f"It's a draw. {again}",
    }[state["status"]]

    t = state["tally"]
    score = f"Score so far: visitors **{t['visitors']}**, bot **{t['bot']}**, draws **{t['draws']}**"
    last = ""
    if state.get("last"):
        last = f"  \nLast move by [{state['last']}](https://github.com/{state['last']})"

    return f"{table}\n\n{status}  \n{score}{last}"


def write_readme(state):
    with open(README, encoding="utf-8") as f:
        text = f.read()
    if START not in text or END not in text:
        sys.exit(f"Markers {START} / {END} not found in {README}")
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    new = f"{head}{START}\n{render(state)}\n{END}{tail}"
    with open(README, "w", encoding="utf-8") as f:
        f.write(new)


def play(state, title, user):
    """Apply one issue to the state. Returns the comment to post."""
    if title == "ttt|new":
        state.update(fresh(state["tally"]))
        return "New game started. You're X and you go first."

    m = re.fullmatch(r"ttt\|move\|([0-8])", title)
    if not m:
        return "I couldn't read that move. Please use the links in the README."

    cell = int(m.group(1))
    board = state["board"]
    if state["status"] != "playing":
        return "That game is over. Use the 'Play again' link in the README."
    if board[cell] != " ":
        return f"The {NAMES[cell]} square is taken. Pick an empty one."

    board[cell] = "X"
    state["last"] = user
    if winner(board) == "X":
        state["status"] = "x_won"
        state["tally"]["visitors"] += 1
        return f"You played {NAMES[cell]} and won. Nice one!"
    if " " not in board:
        state["status"] = "draw"
        state["tally"]["draws"] += 1
        return f"You played {NAMES[cell]}. The board is full, so it's a draw."

    reply = bot_move(board)
    board[reply] = "O"
    if winner(board) == "O":
        state["status"] = "o_won"
        state["tally"]["bot"] += 1
        return f"You played {NAMES[cell]}. The bot answered {NAMES[reply]} and won."
    if " " not in board:
        state["status"] = "draw"
        state["tally"]["draws"] += 1
        return f"You played {NAMES[cell]}. The bot answered {NAMES[reply]}. Draw."
    return f"You played {NAMES[cell]}. The bot answered {NAMES[reply]}. Your turn."


def main():
    state = load_state()

    if "--render" in sys.argv:  # just redraw the README from saved state
        save_state(state)
        write_readme(state)
        return

    title = os.environ.get("ISSUE_TITLE", "").strip()
    user = os.environ.get("ISSUE_USER", "")
    if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", user):
        user = ""

    comment = play(state, title, user)
    save_state(state)
    write_readme(state)

    with open(os.environ.get("COMMENT_FILE", "comment.txt"), "w", encoding="utf-8") as f:
        f.write(comment + "\n")


if __name__ == "__main__":
    main()
