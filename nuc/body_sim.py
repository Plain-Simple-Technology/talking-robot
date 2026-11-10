"""The pretend body.

A small TCP server that answers the six questions in docs/PROTOCOL.md
the way a real Control Hub would, with the same safety rules. It keeps
track of where it is on a pretend floor. There is one wall, 150 cm ahead
of where it starts.

Run it:

    python3 nuc/body_sim.py
    python3 nuc/body_sim.py --face near    look sees one wide face, id 1
    python3 nuc/body_sim.py --face far     look sees the same face, narrow

Then, in another terminal:

    python3 nuc/body_client.py
    nc 127.0.0.1 8765

Stop it with Ctrl-C. Every answer carries "sim": true so you can tell it
from the real hub.
"""

import argparse
import json
import math
import socket
import socketserver
import sys
import threading

HOST = "127.0.0.1"
PORT = 8765

# The safety rules. Same numbers as docs/PROTOCOL.md.
MAX_SPEED = 0.5
MAX_MOVE_CM = 300.0
STOP_AT_CM = 30.0

# The pretend world.
WALL_X_CM = 150.0        # a wall across the floor at x = 150
CLEAR_CM = 200.0         # "nothing in range" is reported as 200
COUNTS_PER_CM = 23.7     # a made-up number. She measures the real one in Week 4
BATTERY_V = 12.6

COMMANDS = ("ping", "status", "move", "turn", "stop", "look")

# The pretend camera. Field names are from docs/PROTOCOL.md.
# The HuskyLens picture is 320 wide and 240 tall. A close face is wide.
FACES = {
    "none": [],
    "far": [{"id": 1, "x": 160, "y": 120, "width": 30, "height": 30}],
    "near": [{"id": 1, "x": 160, "y": 120, "width": 120, "height": 120}],
}


def wrap_deg(deg):
    """Wrap an angle to the range -180 to 180."""
    return (deg + 180.0) % 360.0 - 180.0


class BodySim:
    """Where the pretend robot is, and what it does when asked."""

    def __init__(self, face="none"):
        if face not in FACES:
            raise ValueError("face must be one of %s" % ", ".join(FACES))
        self.face = face
        self.x = 0.0            # cm. The wall is at x = WALL_X_CM
        self.y = 0.0            # cm. Plus is to the left of the start heading
        self.heading = 0.0      # degrees. 0 faces the wall. Left is positive
        self.counts = {"fl": 0, "fr": 0, "bl": 0, "br": 0}
        self.lock = threading.Lock()

    # The sensor

    def gap_cm(self):
        """True distance along the heading to the wall, or None if facing away."""
        facing = math.cos(math.radians(self.heading))
        if facing <= 0.001:
            return None
        return max((WALL_X_CM - self.x) / facing, 0.0)

    def front_cm(self):
        """What the sensor reports: the gap, or CLEAR_CM when nothing is in range."""
        gap = self.gap_cm()
        if gap is None or gap > CLEAR_CM:
            return CLEAR_CM
        return round(gap, 1)

    # The six questions

    def handle(self, ask):
        if not isinstance(ask, dict):
            return self.error("not an object")
        cmd = ask.get("cmd")
        if cmd is None:
            return self.error("no cmd")
        if cmd not in COMMANDS:
            return self.error("unknown command: %s" % cmd)
        with self.lock:
            return getattr(self, "do_" + cmd)(ask)

    def do_ping(self, ask):
        return self.ok("ping", msg="I am here")

    def do_status(self, ask):
        return self.ok(
            "status",
            heading_deg=round(wrap_deg(self.heading), 1),
            front_cm=self.front_cm(),
            counts=dict(self.counts),
            battery_v=BATTERY_V,
        )

    def do_move(self, ask):
        try:
            forward = float(ask.get("forward_cm", 0) or 0)
            strafe = float(ask.get("strafe_cm", 0) or 0)
            speed = float(ask.get("speed", MAX_SPEED) or MAX_SPEED)
        except (TypeError, ValueError):
            return self.error("move needs numbers")

        # Rule 1 and rule 2. Speed and distance are capped.
        speed = min(abs(speed), MAX_SPEED)
        forward = max(-MAX_MOVE_CM, min(MAX_MOVE_CM, forward))
        strafe = max(-MAX_MOVE_CM, min(MAX_MOVE_CM, strafe))

        # Rule 3. Forward motion stops short of the wall.
        stopped_by = "done"
        gap = self.gap_cm()
        if forward > 0 and gap is not None:
            room = gap - STOP_AT_CM
            if forward > room:
                forward = max(room, 0.0)
                stopped_by = "obstacle"

        self.shift(forward, strafe)
        for wheel in self.counts:
            self.counts[wheel] += int(round(forward * COUNTS_PER_CM))

        return self.ok(
            "move",
            moved_cm=round(forward, 1),
            strafed_cm=round(strafe, 1),
            stopped_by=stopped_by,
            front_cm=self.front_cm(),
        )

    def do_turn(self, ask):
        try:
            deg = float(ask.get("deg", 0) or 0)
        except (TypeError, ValueError):
            return self.error("turn needs a number")
        self.heading = (self.heading + deg) % 360.0
        return self.ok(
            "turn",
            turned_deg=round(deg, 1),
            heading_deg=round(wrap_deg(self.heading), 1),
        )

    def do_stop(self, ask):
        # The pretend body moves instantly, so there is never a move to stop.
        return self.ok("stop", msg="Stopped")

    def do_look(self, ask):
        return self.ok("look", objects=[dict(f) for f in FACES[self.face]])

    # Helpers

    def shift(self, forward, strafe):
        h = math.radians(self.heading)
        # Forward is along the heading. Strafe right is 90 degrees to the right of it.
        self.x += forward * math.cos(h) + strafe * math.sin(h)
        self.y += forward * math.sin(h) - strafe * math.cos(h)

    @staticmethod
    def ok(cmd, **fields):
        answer = {"ok": True, "cmd": cmd}
        answer.update(fields)
        answer["sim"] = True
        return answer

    @staticmethod
    def error(reason):
        return {"ok": False, "error": reason, "sim": True}


def answer_line(sim, line):
    """One line of text in, one line of JSON out. Never raises."""
    text = line.strip()
    if not text:
        return None
    try:
        ask = json.loads(text)
    except ValueError:
        short = text if len(text) <= 60 else text[:57] + "..."
        answer = BodySim.error("not JSON: %s" % short)
    else:
        try:
            answer = sim.handle(ask)
        except Exception as e:  # a bug in the sim must not kill the server
            answer = BodySim.error("body error: %s" % e)
    return json.dumps(answer) + "\n"


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        for raw in self.rfile:
            try:
                line = raw.decode("utf-8", errors="replace")
            except Exception:
                line = ""
            reply = answer_line(self.server.sim, line)
            if reply is None:
                continue
            self.wfile.write(reply.encode())
            self.wfile.flush()


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, sim=None):
        super().__init__(address, Handler)
        self.sim = sim or BodySim()


def start_in_thread(host=HOST, port=0, face="none"):
    """Start a pretend body in the background. Returns the server.

    Port 0 picks a free port. Read it from server.server_address[1].
    face is "none", "far" or "near". Used by the tests.
    Call server.shutdown() when done.
    """
    server = Server((host, port), BodySim(face=face))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def main(argv):
    parser = argparse.ArgumentParser(description="The pretend robot body.")
    parser.add_argument("--port", type=int, default=PORT, help="port to listen on (default 8765)")
    parser.add_argument("--face", choices=sorted(FACES), default="none",
                        help="what the pretend camera sees: none, far or near (default none)")
    args = parser.parse_args(argv[1:])
    try:
        server = Server((HOST, args.port), BodySim(face=args.face))
    except OSError as e:
        print("Could not listen on port %d: %s" % (args.port, e))
        print("Is another pretend body already running? Stop it with Ctrl-C.")
        return 1
    print("Pretend body on port %d. Wall at %.0f cm. Face: %s. Ctrl-C to stop."
          % (args.port, WALL_X_CM, args.face), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPretend body stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
