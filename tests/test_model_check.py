"""Tests for nuc/model_check.py that need no model and no network.

The openai client is replaced with a fake that answers like Ollama does.
"""

import os
import re
import sys
from types import SimpleNamespace

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "nuc"))

import model_check  # noqa: E402


# A fake openai client. Answers are queued in the order they are asked.

def words(text):
    return SimpleNamespace(content=text, tool_calls=None)


def tool_call(name, arguments):
    call = SimpleNamespace(function=SimpleNamespace(name=name, arguments=arguments))
    return SimpleNamespace(content=None, tool_calls=[call])


class FakeCompletions:
    def __init__(self, answers):
        self.answers = list(answers)
        self.asked = []

    def create(self, **kwargs):
        self.asked.append(kwargs)
        message = self.answers.pop(0)
        if kwargs.get("stream"):
            pieces = re.findall(r"\S+\s*", message.content or "")
            return iter(
                SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=piece))])
                for piece in pieces
            )
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeClient:
    def __init__(self, answers):
        self.chat = SimpleNamespace(completions=FakeCompletions(answers))


def factory_for(answers):
    client = FakeClient(answers)
    return client, (lambda values: client)


@pytest.fixture
def env_file(tmp_path):
    p = tmp_path / ".env"
    p.write_text("# the model\nMODEL_URL=http://mini.local:11434/v1\n"
                 "MODEL_NAME=qwen3:8b\nMODEL_KEY='ollama'\n")
    return str(p)


@pytest.fixture
def clean_env(monkeypatch):
    for name in model_check.NAMES:
        monkeypatch.delenv(name, raising=False)


# Reading .env

def test_read_env(env_file, clean_env):
    values = model_check.read_env(env_file)
    assert values == {"MODEL_URL": "http://mini.local:11434/v1",
                      "MODEL_NAME": "qwen3:8b", "MODEL_KEY": "ollama"}


def test_environment_wins_over_file(env_file, clean_env, monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "llama3.1:8b")
    assert model_check.read_env(env_file)["MODEL_NAME"] == "llama3.1:8b"


def test_missing_settings_is_one_plain_line(tmp_path, clean_env):
    lines = []
    code = model_check.main(["x"], env_path=str(tmp_path / "none"), out=lines.append)
    assert code == 1
    assert lines == ["Missing MODEL_URL, MODEL_NAME, MODEL_KEY. "
                     "Copy .env.example to .env and fill it in."]


def test_bad_flag(env_file, clean_env):
    lines = []
    assert model_check.main(["x", "--bogus"], env_path=env_file, out=lines.append) == 2
    assert lines[0].startswith("Usage:")


# No flag: one question with timing

def test_run_once(env_file, clean_env):
    client, factory = factory_for([words("A robot is a machine that moves by itself.")])
    lines = []
    code = model_check.main(["x"], env_path=env_file, client_factory=factory, out=lines.append)
    assert code == 0
    assert lines[0] == "Model: qwen3:8b"
    assert lines[2] == "A: A robot is a machine that moves by itself."
    assert lines[3].startswith("First word in ") and lines[3].endswith(" s.")
    assert client.chat.completions.asked[0]["stream"] is True
    # Thinking is turned off, so the first word comes fast.
    assert client.chat.completions.asked[0]["reasoning_effort"] == "none"


# --chat

def test_chat_quits_on_empty_line(env_file, clean_env):
    client, factory = factory_for([words("Hello!"), words("Blue.")])
    lines = []
    code = model_check.run_chat(client, "qwen3:8b", lines=iter(["hi", "sky color?", ""]), out=lines.append)
    assert code == 0
    assert lines[1:] == ["robot> Hello!", "robot> Blue."]
    # The whole conversation goes back each time.
    last = client.chat.completions.asked[-1]["messages"]
    assert [m["role"] for m in last][:4] == ["system", "user", "assistant", "user"]


# --tools

def test_tools_both_right(env_file, clean_env):
    client, factory = factory_for([
        tool_call("move", '{"forward_cm": 100}'),
        words("The sky is blue."),
    ])
    lines = []
    code = model_check.main(["x", "--tools"], env_path=env_file, client_factory=factory, out=lines.append)
    assert code == 0
    assert lines[1].startswith("RIGHT  Drive forward one meter")
    assert lines[2].startswith("RIGHT  What color")
    assert lines[3] == "2 of 2 right."
    assert client.chat.completions.asked[0]["tools"] == [model_check.MOVE_TOOL]
    assert client.chat.completions.asked[0]["reasoning_effort"] == "none"


def test_tools_wrong_answers(env_file, clean_env):
    client, factory = factory_for([
        tool_call("move", '{"forward_cm": 1}'),       # one meter is 100 cm
        tool_call("move", '{"forward_cm": 50}'),      # a plain question is not a drive
    ])
    lines = []
    code = model_check.main(["x", "--tools"], env_path=env_file, client_factory=factory, out=lines.append)
    assert code == 1
    assert lines[1].startswith("WRONG") and "not 100" in lines[1]
    assert lines[2].startswith("WRONG") and "called move" in lines[2]
    assert lines[3] == "0 of 2 right."


# The model cannot be reached

def test_unreachable_is_one_plain_line(env_file, clean_env):
    class APIConnectionError(Exception):
        pass

    def factory(values):
        raise APIConnectionError("Connection error.")

    lines = []
    code = model_check.main(["x"], env_path=env_file, client_factory=factory, out=lines.append)
    assert code == 1
    assert len(lines) == 1
    assert lines[0].startswith("Cannot reach the model.")
