"""Mecanum wheel math.

A mecanum robot moves by mixing three wishes into four wheel speeds:

    forward   plus is forward
    strafe    plus is right
    turn      plus is turn right (clockwise seen from above)

Each wheel gets a share of each wish. The order of the four numbers is
always front left, front right, back left, back right.

    Wish          fl   fr   bl   br
    Forward        +    +    +    +
    Strafe right   +    -    -    +
    Turn right     +    -    +    -

Speed is capped at half power. MAX_POWER is the cap. The body enforces
it too, but the brain should never ask for more.
"""

MAX_POWER = 0.5


def wheel_powers(forward, strafe, turn, max_power=MAX_POWER):
    """Return (fl, fr, bl, br) wheel powers for three wishes.

    Each wish is a number from -1 to 1. The result is scaled so the
    biggest wheel power is max_power when any wish is at full, and
    no wheel ever goes past max_power.
    """
    fl = forward + strafe + turn
    fr = forward - strafe - turn
    bl = forward - strafe + turn
    br = forward + strafe - turn

    biggest = max(abs(fl), abs(fr), abs(bl), abs(br), 1.0)
    scale = max_power / biggest

    return (
        round(fl * scale, 3),
        round(fr * scale, 3),
        round(bl * scale, 3),
        round(br * scale, 3),
    )


if __name__ == "__main__":
    print("forward     ", wheel_powers(1, 0, 0))
    print("strafe right", wheel_powers(0, 1, 0))
    print("turn right  ", wheel_powers(0, 0, 1))
