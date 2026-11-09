"""The brain's side of the link.

Body is a small class with one method per question in docs/PROTOCOL.md.
Each call opens a connection to the body, sends one JSON line, reads one
JSON line back, and closes. The body may be the real hub through
`adb forward tcp:8765 tcp:8765`, or the pretend body from body_sim.py.
The brain cannot tell them apart, except that the pretend body says
"sim": true.

Run it:

    python3 nuc/body_client.py          ping, then status
    python3 nuc/body_client.py square   a 50 cm square, four moves and four turns
"""

import json
import socket
import sys

HOST = "127.0.0.1"
PORT = 8765
TIMEOUT_S = 30.0


class BodyError(Exception):
    """The body said ok: false."""


class Body:
    def __init__(self, host=HOST, port=PORT, timeout=TIMEOUT_S):
        self.host = host
        self.port = port
        self.timeout = timeout

    def send(self, ask):
        """Send one dict, get one dict back. Raises on ok: false."""
        line = json.dumps(ask) + "\n"
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
            s.sendall(line.encode())
            reply = s.makefile("r").readline()
        if not reply:
            raise BodyError("the body closed the connection without answering")
        answer = json.loads(reply)
        if not answer.get("ok"):
            raise BodyError(answer.get("error", "unknown error"))
        return answer

    def ping(self):
        return self.send({"cmd": "ping"})

    def status(self):
        return self.send({"cmd": "status"})

    def move(self, forward_cm=0, strafe_cm=0, speed=0.5):
        return self.send({
            "cmd": "move",
            "forward_cm": forward_cm,
            "strafe_cm": strafe_cm,
            "speed": speed,
        })

    def turn(self, deg):
        return self.send({"cmd": "turn", "deg": deg})

    def stop(self):
        return self.send({"cmd": "stop"})

    def look(self):
        return self.send({"cmd": "look"})

    def square(self, side_cm=50):
        """Drive a square: four moves and four left turns. Returns the answers."""
        answers = []
        for _ in range(4):
            answers.append(self.move(forward_cm=side_cm))
            answers.append(self.turn(90))
        return answers


def main(argv):
    body = Body()
    try:
        if len(argv) > 1 and argv[1] == "square":
            for answer in body.square():
                print(answer)
        else:
            print(body.ping())
            print(body.status())
    except ConnectionRefusedError:
        print("Connection refused on port %d." % PORT)
        print("Is the body running? Pretend body: python3 nuc/body_sim.py")
        print("Real hub: start BodyServer, then adb forward tcp:8765 tcp:8765")
        return 1
    except BodyError as e:
        print("The body refused:", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
