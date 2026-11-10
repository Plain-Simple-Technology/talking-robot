"""Fourteen tests for the starter kit.

Run from the kit folder:

    python3 -m pytest -q

They cover the three wheel patterns in the Week 1 table, the power cap,
ping and status, a move that ends at the obstacle limit, a square that
returns to its start, a refused bad command, a garbage line that gets an
error instead of a crash, the 3 meter cap, and the pretend camera's three
settings: none, far and near.
"""

import os
import socket
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "nuc"))

import body_sim  # noqa: E402
from body_client import Body, BodyError  # noqa: E402
from mecanum import MAX_POWER, wheel_powers  # noqa: E402


def signs(powers):
    return tuple("+" if p > 0 else "-" if p < 0 else "0" for p in powers)


# The wheel math. Order is fl, fr, bl, br.

def test_forward_pattern():
    assert signs(wheel_powers(1, 0, 0)) == ("+", "+", "+", "+")


def test_strafe_right_pattern():
    assert signs(wheel_powers(0, 1, 0)) == ("+", "-", "-", "+")


def test_turn_right_pattern():
    assert signs(wheel_powers(0, 0, 1)) == ("+", "-", "+", "-")


def test_power_cap():
    assert MAX_POWER == 0.5
    for wishes in [(1, 0, 0), (1, 1, 1), (-1, 1, -1), (1, -1, 0), (0.2, 0, 0)]:
        for p in wheel_powers(*wishes):
            assert abs(p) <= MAX_POWER
    assert wheel_powers(0, 0, 0) == (0, 0, 0, 0)


# The pretend body, through the client.

@pytest.fixture
def make_body():
    """A factory: make_body(face) starts a pretend body and returns a Body."""
    servers = []

    def make(face="none"):
        server = body_sim.start_in_thread(face=face)
        servers.append(server)
        return Body(port=server.server_address[1])

    yield make
    for server in servers:
        server.shutdown()
        server.server_close()


@pytest.fixture
def body(make_body):
    return make_body()


def test_ping(body):
    answer = body.ping()
    assert answer["ok"] is True
    assert answer["msg"] == "I am here"
    assert answer["sim"] is True


def test_status(body):
    s = body.status()
    assert s["ok"] is True
    assert s["heading_deg"] == 0
    assert s["front_cm"] == 150
    assert set(s["counts"]) == {"fl", "fr", "bl", "br"}
    assert s["battery_v"] > 0


def test_move_stops_at_obstacle(body):
    answer = body.move(forward_cm=500)
    assert answer["stopped_by"] == "obstacle"
    assert answer["moved_cm"] == 120
    assert answer["front_cm"] == 30
    assert body.status()["counts"]["fl"] > 0


def test_square_returns_to_start(body):
    answers = body.square(side_cm=50)
    assert len(answers) == 8
    moves = answers[0::2]
    assert all(m["stopped_by"] == "done" and m["moved_cm"] == 50 for m in moves)
    assert moves[0]["front_cm"] == 100
    assert body.status()["heading_deg"] == 0
    # Peek at the pretend floor. The real body has no idea where it is.
    sim = body_sim.BodySim()
    for a in answers:
        if a["cmd"] == "move":
            sim.shift(a["moved_cm"], a["strafed_cm"])
        else:
            sim.heading = (sim.heading + a["turned_deg"]) % 360
    assert abs(sim.x) < 0.01 and abs(sim.y) < 0.01


def test_distance_cap(body):
    body.turn(180)
    answer = body.move(forward_cm=1000)
    assert answer["moved_cm"] == 300
    assert answer["stopped_by"] == "done"


def test_bad_command_refused(body):
    with pytest.raises(BodyError) as e:
        body.send({"cmd": "dance"})
    assert "unknown command: dance" in str(e.value)


def test_garbage_line_gets_error_not_crash(body):
    with socket.create_connection((body.host, body.port), timeout=5) as s:
        s.sendall(b"hello\n")
        reply = s.makefile("r").readline()
    assert '"ok": false' in reply
    assert "not JSON" in reply
    # The body is still alive.
    assert body.ping()["ok"] is True


# The pretend camera. Field names are from docs/PROTOCOL.md.

FACE_FIELDS = {"id", "x", "y", "width", "height"}


def test_look_none(body):
    answer = body.look()
    assert answer["ok"] is True
    assert answer["objects"] == []
    assert answer["sim"] is True


def test_look_far(make_body):
    answer = make_body("far").look()
    assert answer["sim"] is True
    assert len(answer["objects"]) == 1
    face = answer["objects"][0]
    assert set(face) == FACE_FIELDS
    assert face["id"] == 1
    assert 0 < face["width"] < 60


def test_look_near(make_body):
    near = make_body("near").look()["objects"][0]
    far = make_body("far").look()["objects"][0]
    assert set(near) == FACE_FIELDS
    assert near["id"] == 1
    assert near["width"] >= 100
    assert near["width"] > far["width"]
    assert make_body("near").look()["sim"] is True
