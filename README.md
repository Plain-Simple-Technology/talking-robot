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
| `nuc/model_check.py` | Proves the NUC can reach the AI model. One question, a chat, or two tool checks |
| `.env.example` | The three model settings. Copy it to `.env` and fill it in |
| `tests/` | The tests. All must pass before Week 1 |

Not in the kit: `BodyServer.java`. That is the real body, and the student
writes it with Claude Code in Week 2. The starter ask is in the project doc.

## Bench setup check

In this folder:

```
python3 -m pytest -q
```

You should see every test pass. If you do not, copy the exact message
into the logbook for the instructor.

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

The face sits in the middle of the picture, at x 160. To move it, add
`--face-x` with a number from 0 to 319. Small is left, big is right.

```
python3 nuc/body_sim.py --face near --face-x 40
python3 nuc/body_sim.py --face near --face-x 280
```

Use these to test that the robot turns toward a face.

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

## The robot's AI model

The robot thinks with a local model. It is not a paid API. The model
runs on a Mac mini that sits beside the robot, served by a program
called Ollama. The NUC reaches it over the network, by the Mac mini's
`.local` name. The NUC itself runs no model.

The agent reads three settings from a file called `.env` in this folder.
Copy `.env.example` to `.env` and fill it in:

| Name | What it is |
|------|------------|
| `MODEL_URL` | Where Ollama answers, for example `http://your-mac-mini.local:11434/v1` |
| `MODEL_NAME` | Which model to use, for example `llama3.1:8b` |
| `MODEL_KEY` | A key, if the server wants one. Ollama does not, so `ollama` is fine |

`.env` is listed in `.gitignore`. It never goes into the repo, and no key
goes into any file that does. If you need to share the settings, write
the three names down. Never the key.

Check the link before anything else is built. First install the one
package it needs, then run it:

```
pip install openai
python3 nuc/model_check.py
python3 nuc/model_check.py --chat
python3 nuc/model_check.py --tools
```

The first prints the model's name, asks one short question, and prints
the answer and the seconds it took. `--chat` is a typed chat, and an
empty line quits. `--tools` sends "Drive forward one meter" with one move
tool and a plain question with the same tool, and says whether each came
back right. If the model cannot be reached it says so in one line.

Some models think before they answer. The thinking is not words, and it
adds ten seconds or more before the first word. `model_check.py` turns it
off with one setting, `reasoning_effort`, marked near the top of the
file. The agent should do the same.

Ollama and the models are not part of this kit. Nothing here installs
them, and no model files belong in Git.

## Rules

- Wheels off the floor for any code that has not driven before.
- A step is done when its test passes on the real robot. The pretend body does not count.
- Every change goes into Git. One repo holds the whole robot.
- Nothing with a password or a key goes into Git. The key lives in `.env`. See `.gitignore`.
