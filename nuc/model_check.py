"""Check the robot's AI model.

The model runs on a Mac mini beside the robot, served by Ollama. The NUC
reaches it over the network. This program proves that the link works
before any of the robot's own programs are written.

Settings come from a file called .env in the kit folder:

    MODEL_URL=http://<the mac mini>.local:11434/v1
    MODEL_NAME=qwen3:8b
    MODEL_KEY=ollama

Run it:

    python3 nuc/model_check.py           one short question, with timing
    python3 nuc/model_check.py --chat    a typed chat. Empty line quits
    python3 nuc/model_check.py --tools   two tool-use checks

It uses the openai package, which speaks the same language as Ollama:

    pip install openai
"""

import json
import os
import sys
import time

NAMES = ("MODEL_URL", "MODEL_NAME", "MODEL_KEY")

# Some models "think" before they answer. The thinking is not words the
# robot can say, and it adds ten seconds or more before the first word.
# This turns it off on Ollama. Models that never think ignore it.
REASONING_EFFORT = "none"
QUESTION = "In one short sentence, what is a robot?"
SYSTEM = "You are a friendly robot. Answer in one or two short sentences."

# The one tool used by --tools. The description is the instruction.
MOVE_TOOL = {
    "type": "function",
    "function": {
        "name": "move",
        "description": "Drive the robot forward. Distance is in centimeters, "
                       "at most 300. Negative is backward.",
        "parameters": {
            "type": "object",
            "properties": {
                "forward_cm": {"type": "number",
                               "description": "Centimeters to drive forward"},
            },
            "required": ["forward_cm"],
        },
    },
}


def read_env(path=".env"):
    """Read NAME=value lines from a file. Lines starting with # are skipped.

    The real environment wins over the file, so a value can be set for
    one run without editing the file.
    """
    values = {}
    if os.path.exists(path):
        with open(path) as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, value = line.split("=", 1)
                name = name.strip()
                value = value.strip().strip('"').strip("'")
                if name in NAMES:
                    values[name] = value
    for name in NAMES:
        if os.environ.get(name):
            values[name] = os.environ[name]
    return values


def settings(path=".env"):
    """The three settings, or a plain message about what is missing."""
    values = read_env(path)
    missing = [n for n in NAMES if not values.get(n)]
    if missing:
        return None, ("Missing %s. Copy .env.example to .env and fill it in."
                      % ", ".join(missing))
    return values, None


def make_client(values):
    """An openai client pointed at the model. Imported here so the tests
    can run without the openai package installed."""
    from openai import OpenAI
    return OpenAI(base_url=values["MODEL_URL"], api_key=values["MODEL_KEY"],
                  timeout=120.0, max_retries=0)


def plain_error(e):
    """One line for a model that cannot be reached, no stack trace."""
    name = type(e).__name__
    text = str(e).split("\n")[0]
    if "Connection" in name or "connect" in text.lower():
        return "Cannot reach the model. Is Ollama running on the Mac mini, and is MODEL_URL right?"
    if "NotFound" in name or "not found" in text.lower():
        return "The model is not there. Check MODEL_NAME, or pull it with ollama pull."
    if "Timeout" in name:
        return "The model did not answer in time. Is MODEL_URL right, and is the Mac mini awake?"
    return "The model gave an error: %s: %s" % (name, text)


def ask(client, model, messages, tools=None):
    """One chat call. Returns the message object."""
    kwargs = {"model": model, "messages": messages}
    if tools:
        kwargs["tools"] = tools
    if REASONING_EFFORT:
        kwargs["reasoning_effort"] = REASONING_EFFORT
    reply = client.chat.completions.create(**kwargs)
    return reply.choices[0].message


def ask_streamed(client, model, messages):
    """One streamed call. Returns (text, seconds to first word, seconds to end)."""
    start = time.monotonic()
    first = None
    parts = []
    kwargs = {"model": model, "messages": messages, "stream": True}
    if REASONING_EFFORT:
        kwargs["reasoning_effort"] = REASONING_EFFORT
    stream = client.chat.completions.create(**kwargs)
    for chunk in stream:
        if not chunk.choices:
            continue
        piece = chunk.choices[0].delta.content
        if piece:
            if first is None:
                first = time.monotonic() - start
            parts.append(piece)
    return "".join(parts), first, time.monotonic() - start


def tool_calls_of(message):
    """The tool calls on a message as a list of (name, arguments dict)."""
    calls = []
    for call in message.tool_calls or []:
        try:
            args = json.loads(call.function.arguments or "{}")
        except ValueError:
            args = {}
        calls.append((call.function.name, args))
    return calls


# The three ways to run it

def run_once(client, model, out=print):
    out("Model: %s" % model)
    out("Q: %s" % QUESTION)
    text, first, total = ask_streamed(client, model, [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": QUESTION},
    ])
    out("A: %s" % text.strip())
    out("First word in %.2f s. Full answer in %.2f s." % (first or 0.0, total))
    return 0


def run_chat(client, model, lines=None, out=print):
    """A plain typed chat. An empty line quits. lines is for the tests."""
    out("Chat with %s. Empty line quits." % model)
    history = [{"role": "system", "content": SYSTEM}]
    while True:
        try:
            line = next(lines) if lines is not None else input("you> ")
        except (EOFError, StopIteration, KeyboardInterrupt):
            break
        line = line.strip()
        if not line:
            break
        history.append({"role": "user", "content": line})
        message = ask(client, model, history)
        text = (message.content or "").strip()
        history.append({"role": "assistant", "content": text})
        out("robot> %s" % text)
    return 0


def check_drive(message):
    """Right when it called move with about 100 cm and nothing else."""
    calls = tool_calls_of(message)
    if len(calls) != 1:
        return False, "expected one move call, got %d" % len(calls)
    name, args = calls[0]
    if name != "move":
        return False, "called %s, not move" % name
    try:
        cm = float(args.get("forward_cm"))
    except (TypeError, ValueError):
        return False, "no forward_cm number in %s" % args
    if abs(cm - 100) > 1:
        return False, "forward_cm was %s, not 100" % cm
    return True, "move(forward_cm=%g)" % cm


def check_plain(message):
    """Right when it answered in words and did not touch the tool."""
    calls = tool_calls_of(message)
    if calls:
        return False, "called %s for a plain question" % calls[0][0]
    if not (message.content or "").strip():
        return False, "no words in the answer"
    return True, (message.content or "").strip()[:60]


def run_tools(client, model, out=print):
    out("Model: %s" % model)
    checks = [
        ("Drive forward one meter", check_drive),
        ("What color is the sky on a clear day?", check_plain),
    ]
    right = 0
    for question, check in checks:
        message = ask(client, model, [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": question},
        ], tools=[MOVE_TOOL])
        ok, note = check(message)
        right += ok
        out("%s  %s  ->  %s" % ("RIGHT" if ok else "WRONG", question, note))
    out("%d of %d right." % (right, len(checks)))
    return 0 if right == len(checks) else 1


def main(argv, env_path=".env", client_factory=make_client, out=print):
    mode = argv[1] if len(argv) > 1 else ""
    if mode not in ("", "--chat", "--tools"):
        out("Usage: python3 nuc/model_check.py [--chat | --tools]")
        return 2
    values, problem = settings(env_path)
    if problem:
        out(problem)
        return 1
    try:
        client = client_factory(values)
        if mode == "--chat":
            return run_chat(client, values["MODEL_NAME"], out=out)
        if mode == "--tools":
            return run_tools(client, values["MODEL_NAME"], out=out)
        return run_once(client, values["MODEL_NAME"], out=out)
    except ImportError:
        out("The openai package is missing. Run: pip install openai")
        return 1
    except Exception as e:  # one plain line, no stack trace
        out(plain_error(e))
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
