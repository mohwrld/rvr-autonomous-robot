import asyncio
import time

from gpiozero import DistanceSensor, LED, TonalBuzzer
from gpiozero.tones import Tone
from sphero_sdk import (
    SpheroRvrAsync,
    SerialAsyncDal,
    DriveFlagsBitmask,
    Colors
)


loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

rvr = SpheroRvrAsync(
    dal=SerialAsyncDal(loop, device="/dev/ttyAMA0")
)

sensor = DistanceSensor(
    echo=24,
    trigger=23,
    max_distance=4
)

led = LED(17)
buzzer = TonalBuzzer(18)

STOP_DISTANCE_CM = 50
DRIVE_SPEED = 50
TURN_SPEED = 10
REVERSE_SPEED = 25

REQUIRED_CLOSE_READINGS = 3
REQUIRED_CLEAR_READINGS = 3
PATH_CHECK_READINGS = 5
PATH_SETTLE_DELAY = 0.4

TURN_STEP = 5
TURN_STEP_DELAY = 0.1
CHECK_DELAY = 0.25

# Corner-recovery settings
QUICK_FAILURE_TIME = 1.5
QUICK_FAILURE_LIMIT = 2
REVERSE_TIME = 1.0
ESCAPE_TURN_DEGREES = 135

current_heading = 0
quick_failures = 0
last_direction_change_time = 0
escape_turn_right = True


async def set_driving_status():
    led.off()
    buzzer.stop()

    await rvr.led_control.set_all_leds_color(
        color=Colors.green
    )


async def set_obstacle_status():
    led.on()
    buzzer.play(Tone("A5"))

    await rvr.led_control.set_all_leds_color(
        color=Colors.red
    )


async def set_turning_status():
    # Keep the warning buzzer sounding while the robot is
    # turning away from an obstacle. set_driving_status()
    # stops it once a clear path has been selected.
    await rvr.led_control.set_all_leds_color(
        color=Colors.yellow
    )


async def drive_forward():
    await rvr.drive_with_heading(
        speed=DRIVE_SPEED,
        heading=current_heading,
        flags=DriveFlagsBitmask.none.value
    )


async def drive_reverse():
    await rvr.drive_with_heading(
        speed=REVERSE_SPEED,
        heading=current_heading,
        flags=DriveFlagsBitmask.drive_reverse.value
    )


async def stop_robot():
    await rvr.drive_with_heading(
        speed=0,
        heading=current_heading,
        flags=DriveFlagsBitmask.none.value
    )


async def turn_slowly(target_heading):
    global current_heading

    target_heading %= 360
    await set_turning_status()

    while current_heading != target_heading:
        clockwise = (target_heading - current_heading) % 360
        counterclockwise = (current_heading - target_heading) % 360

        if clockwise <= counterclockwise:
            amount = min(TURN_STEP, clockwise)
            current_heading = (current_heading + amount) % 360
        else:
            amount = min(TURN_STEP, counterclockwise)
            current_heading = (current_heading - amount) % 360

        await rvr.drive_with_heading(
            speed=TURN_SPEED,
            heading=current_heading,
            flags=DriveFlagsBitmask.none.value
        )

        await asyncio.sleep(TURN_STEP_DELAY)

    await stop_robot()
    await asyncio.sleep(0.3)


async def path_is_clear():
    """
    Check the current direction using a majority of several readings.

    Waiting briefly after a turn prevents vibration or sensor settling from
    making a clear direction look blocked. A single bad ultrasonic reading
    will not force the robot to abandon an otherwise clear path.
    """
    clear_readings = 0

    await asyncio.sleep(PATH_SETTLE_DELAY)

    for _ in range(PATH_CHECK_READINGS):
        distance_cm = sensor.distance * 100

        print(
            f"Checking heading {current_heading}: "
            f"{distance_cm:.1f} cm"
        )

        if distance_cm > STOP_DISTANCE_CM:
            clear_readings += 1

        await asyncio.sleep(0.15)

    print(
        f"Clear readings: {clear_readings}/"
        f"{PATH_CHECK_READINGS}"
    )

    return clear_readings >= REQUIRED_CLEAR_READINGS


def heading_choices():
    """
    Check directions relative to where the robot is facing.

    This avoids repeatedly prioritizing absolute heading 0.
    """
    return [
        (current_heading + 90) % 360,
        (current_heading - 90) % 360,
        (current_heading + 180) % 360
    ]


async def find_clear_direction():
    await stop_robot()
    await set_obstacle_status()

    for target_heading in heading_choices():
        print(f"Trying heading {target_heading}...")

        await turn_slowly(target_heading)

        if await path_is_clear():
            print(
                f"Clear path found at heading "
                f"{target_heading}."
            )

            await set_driving_status()
            return True

        print(f"Heading {target_heading} is blocked.")
        await set_obstacle_status()

    print("No clear path found.")
    return False


async def escape_corner():
    """
    Create space by reversing, then make a large alternating turn.
    """
    global escape_turn_right

    await stop_robot()
    await set_obstacle_status()

    print("Corner recovery: reversing...")
    await drive_reverse()
    await asyncio.sleep(REVERSE_TIME)
    await stop_robot()
    await asyncio.sleep(0.2)

    if escape_turn_right:
        target_heading = (
            current_heading + ESCAPE_TURN_DEGREES
        ) % 360
    else:
        target_heading = (
            current_heading - ESCAPE_TURN_DEGREES
        ) % 360

    escape_turn_right = not escape_turn_right

    print(
        f"Corner recovery: turning to "
        f"{target_heading}..."
    )

    await turn_slowly(target_heading)

    if await path_is_clear():
        print("Corner recovery successful.")
        await set_driving_status()
        return True

    print("Corner recovery direction is still blocked.")
    return False


async def main():
    global current_heading
    global quick_failures
    global last_direction_change_time

    print("Waking RVR...")
    await rvr.wake()
    await asyncio.sleep(2)

    await rvr.reset_yaw()
    await asyncio.sleep(0.5)

    current_heading = 0
    close_readings = 0
    last_direction_change_time = time.monotonic()

    await set_driving_status()
    print("Driving forward...")

    while True:
        distance_cm = sensor.distance * 100

        print(
            f"Heading: {current_heading} | "
            f"Distance: {distance_cm:.1f} cm"
        )

        if distance_cm <= STOP_DISTANCE_CM:
            close_readings += 1
        else:
            close_readings = 0

        if close_readings >= REQUIRED_CLOSE_READINGS:
            print("Obstacle detected.")
            await stop_robot()
            await set_obstacle_status()

            time_since_last_turn = (
                time.monotonic()
                - last_direction_change_time
            )

            if time_since_last_turn < QUICK_FAILURE_TIME:
                quick_failures += 1
                print(
                    "The previous direction failed quickly. "
                    f"Failure count: {quick_failures}"
                )
            else:
                quick_failures = 0

            if quick_failures >= QUICK_FAILURE_LIMIT:
                clear_direction_found = await escape_corner()
                quick_failures = 0
            else:
                clear_direction_found = (
                    await find_clear_direction()
                )

            close_readings = 0

            while not clear_direction_found:
                print(
                    "Still blocked. Trying corner recovery "
                    "again..."
                )
                await asyncio.sleep(0.5)
                clear_direction_found = await escape_corner()

            last_direction_change_time = time.monotonic()

            await set_driving_status()
            print("Continuing forward...")

        await drive_forward()
        await asyncio.sleep(CHECK_DELAY)


if __name__ == "__main__":
    try:
        loop.run_until_complete(main())

    except KeyboardInterrupt:
        print("\nStopping program...")

    finally:
        try:
            loop.run_until_complete(stop_robot())
        except Exception as error:
            print(f"Could not stop RVR: {error}")

        led.off()
        buzzer.stop()
        sensor.close()

        try:
            loop.run_until_complete(
                rvr.led_control.turn_leds_off()
            )
        except Exception:
            pass

        try:
            loop.run_until_complete(rvr.close())
        except Exception:
            pass

        loop.close()
        print("Done.")