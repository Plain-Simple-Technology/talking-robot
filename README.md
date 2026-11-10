# Talking Robot starter kit

This is the starter kit for the PST STEM project "Build a Talking Robot".
It is a 13 week, one student project. The robot is two computers joined
by one cable. The REV Control Hub is the body. The Intel NUC is the brain.

The brain can only ask the body for six things. This kit holds the brain
side of that conversation, and a pretend body so the brain can be built
before the real link works.

## What is in the kit

| Path | What it is |
|------|------------|
| `docs/PROTOCOL.md` | The six questions and six answers. The contract between brain and body |
| `nuc/mecanum.py` | The wheel math. Three wishes in, four wheel powers out |
| `nuc/body_client.py` | The `Body` class. How the NUC talks to the body |
| `nuc/body_sim.py` | The pretend body. Runs on the NUC, answers on port 8765 |
| `tests/test_kit.py` | Eleven tests. All must pass before Week 1 |

Not in the kit: `BodyServer.java`. That is the real body, and the student
writes it with Claude Code in Week 2. The starter ask is in the project doc.

## Bench setup check

In this folder:

```
python3 -m pytest -q
```

You should see `11 passed`. If you do not, copy the exact message into
the logbook for the instructor.

## Week 2: try the pretend body

Open two terminals in this folder.

Terminal 1:

```
python3 nuc/body_sim.py
```

Terminal 2:

```
python3 nuc/body_client.py
```

Two lines print. That was a conversation between two programs.

Ask a question by hand:

```
nc 127.0.0.1 8765
{"cmd":"ping"}
{"cmd":"status"}
{"cmd":"dance"}
```

Drive a square and read the answers:

```
python3 nuc/body_client.py square
```

Stop the pretend body with Ctrl-C.

## Pretend faces

The pretend body has a pretend camera. By default `look` sees nobody.

```
python3 nuc/body_sim.py --face near
python3 nuc/body_sim.py --face far
```

With `near`, `look` returns one wide face with id 1. With `far`, the same
face is narrow. Use these to test the watching loop before the HuskyLens
is wired. The field names are in `docs/PROTOCOL.md`.

## Week 1: the wheel math

From the `nuc` folder:

```
python3 -c "from mecanum import wheel_powers; print(wheel_powers(0, 1, 0))"
```

The four numbers are front left, front right, back left, back right.
They should match the strafe right row: forward, back, back, forward.

## Real body or pretend body

The NUC's programs always talk to `127.0.0.1:8765`. They cannot tell the
real body from the pretend one, with one exception. The pretend body puts
`"sim": true` in every answer. If you see that when you expected the real
hub, the pretend body is still running.

To reach the real hub over the USB cable:

```
adb forward tcp:8765 tcp:8765
```

## Rules

- Wheels off the floor for any code that has not driven before.
- A step is done when its test passes on the real robot. The pretend body does not count.
- Every change goes into Git. One repo holds the whole robot.
- Nothing with a password or a key goes into Git. See `.gitignore`.
