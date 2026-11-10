# The body protocol

This page is the whole link between the brain and the body. Six questions,
six answers. If it is not on this page, the brain cannot ask for it.

## How a message travels

- The body listens on TCP port 8765.
- The brain sends one JSON object on one line, ending with a new line.
- The body does what it says, then writes one JSON object on one line back,
  ending with a new line.
- One question, one answer. Then the next question.
- A connection may carry many questions in a row, or just one.

Every answer has `"ok"`. When `ok` is `true` the body did it. When `ok` is
`false` there is an `"error"` with a short reason, and the body did nothing.

The pretend body adds `"sim": true` to every answer. The real body does not.

## The six questions

| Ask | Send | The body answers with |
|-----|------|-----------------------|
| ping | `{"cmd":"ping"}` | `{"ok":true,"cmd":"ping","msg":"I am here"}` |
| status | `{"cmd":"status"}` | heading, distance ahead, wheel counts, battery. See below |
| move | `{"cmd":"move","forward_cm":50,"strafe_cm":0,"speed":0.5}` | how far it really went, and why it stopped |
| turn | `{"cmd":"turn","deg":90}` | how far it really turned |
| stop | `{"cmd":"stop"}` | `{"ok":true,"cmd":"stop","msg":"Stopped"}` |
| look | `{"cmd":"look"}` | the faces the HuskyLens sees. See below |

### status

```
{"ok": true, "cmd": "status",
 "heading_deg": 0.0,
 "front_cm": 150.0,
 "counts": {"fl": 0, "fr": 0, "bl": 0, "br": 0},
 "battery_v": 12.6}
```

- `heading_deg` comes from the hub's IMU. Left is positive. It wraps at
  plus or minus 180.
- `front_cm` is the distance to the nearest thing ahead. Anything over 200,
  or nothing in range, is reported as 200.
- `counts` are the raw encoder counts for each wheel. They go up when the
  wheel rolls forward.
- `battery_v` is the hub's battery voltage.

### move

Fields in the ask. All are optional. A missing one is zero, or 0.5 for speed.

| Field | Meaning |
|-------|---------|
| `forward_cm` | Centimeters forward. Negative is backward |
| `strafe_cm` | Centimeters to the right. Negative is left |
| `speed` | 0 to 0.5. Anything higher is cut to 0.5 |

```
{"ok": true, "cmd": "move",
 "moved_cm": 120.0,
 "strafed_cm": 0.0,
 "stopped_by": "obstacle",
 "front_cm": 30.0}
```

`stopped_by` is one of:

| Value | Meaning |
|-------|---------|
| `done` | It got there |
| `obstacle` | Something was closer than 30 cm ahead |
| `stop` | A `stop`, or any other line, arrived during the move |
| `timeout` | The move's time limit ran out |

### turn

`deg` is degrees to the left. Negative turns right.

```
{"ok": true, "cmd": "turn", "turned_deg": 90.0, "heading_deg": 90.0}
```

### look

`objects` is a list with one entry per face in view. Empty when nobody is
there. The HuskyLens picture is 320 wide and 240 tall. `x` and `y` are
the center of the face in that picture. `width` and `height` are its size
in the same units. A close face is wide. A far face is narrow.

```
{"ok": true, "cmd": "look",
 "objects": [{"id": 1, "x": 160, "y": 120, "width": 120, "height": 120}]}
```

| Field | Meaning |
|-------|---------|
| `id` | The face's learned ID. The HuskyLens gives a face it has not learned an id of 0 |
| `x` | Center of the face, left to right, 0 to 320 |
| `y` | Center of the face, top to bottom, 0 to 240 |
| `width` | How wide the face is in the picture. This is the "near" number |
| `height` | How tall the face is in the picture |

Nobody in view:

```
{"ok": true, "cmd": "look", "objects": []}
```

## What the body refuses

A command that is not one of the six:

```
{"cmd":"dance"}
{"ok": false, "error": "unknown command: dance"}
```

A line that is not JSON:

```
hello
{"ok": false, "error": "not JSON: hello"}
```

A JSON line with no `cmd`:

```
{"ok": false, "error": "no cmd"}
```

The body answers with an error and keeps running. It never crashes on a
bad line.

## The safety rules

These live in the body. The brain cannot turn them off.

1. Speed is capped at half power. Any `speed` over 0.5 becomes 0.5.
2. One move is capped at 3 meters. Any distance over 300 cm becomes 300.
3. Forward motion stops when something is closer than 30 cm ahead.
   The answer says `stopped_by: obstacle`.
4. Every move has a time limit. If the cable comes out, or any message
   arrives during a move, the body stops.

The AI can be wrong. A wrong sentence costs nothing. A wrong drive command
hits a wall. That is why the rules are here and not in the brain.

## The pretend body

`nuc/body_sim.py` answers all six questions on port 8765 with the rules
above. It keeps track of where it is. There is one pretend wall, 150 cm
ahead of where it starts. A long forward move ends at the wall with
`stopped_by: obstacle` and `front_cm` of 30. Turn away from the wall and
the way ahead is clear.

The pretend body has a pretend camera too. By default it sees nobody.
Start it with `--face near` and `look` returns one wide face with id 1.
Start it with `--face far` and the same face is narrow. That is enough to
test the watching loop without the robot.

```
python3 nuc/body_sim.py --face near
```

The pretend body moves instantly. The real body takes time, and that is
where the time limit matters.
