import asyncio
import time

import requests
from sphero_sdk import SpheroRvrAsync, SerialAsyncDal


DETECTIONS_URL = "http://127.0.0.1:5000/detections"

CENTER_DEADBAND = 0.05

FOLLOW_SPEED = 22
MAX_HEADING_CHANGE = 6
STEERING_GAIN = 12

STOP_BOX_WIDTH = 260
MAX_DETECTION_AGE = 1.0

OFFSET_SMOOTHING = 0.35
POLL_DELAY = 0.15


loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

rvr = SpheroRvrAsync(
    dal=SerialAsyncDal(
        loop,
        device="/dev/ttyAMA0",
    )
)

current_heading = 0
smoothed_offset = 0.0

http_session = requests.Session()


def get_person_data():
    response = http_session.get(
        DETECTIONS_URL,
        timeout=1,
    )

    response.raise_for_status()

    data = response.json()

    return data.get("person", {})


async def drive(speed):
    await rvr.drive_with_heading(
        speed=speed,
        heading=current_heading,
        flags=0,
    )


async def stop_robot():
    await drive(0)


def smooth_offset(new_offset):
    global smoothed_offset

    smoothed_offset = (
        OFFSET_SMOOTHING * new_offset
        + (1 - OFFSET_SMOOTHING) * smoothed_offset
    )

    return smoothed_offset


async def follow_person(offset):
    global current_heading

    offset = smooth_offset(offset)

    if abs(offset) <= CENTER_DEADBAND:
        heading_change = 0
    else:
        heading_change = round(
            offset * STEERING_GAIN
        )

        if heading_change == 0:
            heading_change = 1 if offset > 0 else -1

        heading_change = max(
            -MAX_HEADING_CHANGE,
            min(MAX_HEADING_CHANGE, heading_change),
        )

    current_heading = (
        current_heading + heading_change
    ) % 360

    print(
        f"Offset: {offset:+.2f} | "
        f"Correction: {heading_change:+d}° | "
        f"Heading: {current_heading}"
    )

    await drive(FOLLOW_SPEED)


async def main():
    global current_heading
    global smoothed_offset

    print("Waking RVR...")
    await rvr.wake()
    await asyncio.sleep(2)

    await rvr.reset_yaw()
    await asyncio.sleep(0.5)

    current_heading = 0
    smoothed_offset = 0.0

    print("Person-following controller started.")
    print("Press Ctrl+C to stop.")

    while True:
        try:
            person = get_person_data()

            if not person.get("detected", False):
                print("No person detected — stopping.")
                smoothed_offset = 0.0
                await stop_robot()
                await asyncio.sleep(POLL_DELAY)
                continue

            offset = person.get("normalized_offset")
            box_width = person.get("box_width")
            timestamp = person.get("timestamp")

            if (
                offset is None
                or box_width is None
                or timestamp is None
            ):
                print("Incomplete detection data — stopping.")
                smoothed_offset = 0.0
                await stop_robot()
                await asyncio.sleep(POLL_DELAY)
                continue

            detection_age = time.time() - timestamp

            if detection_age > MAX_DETECTION_AGE:
                print("Detection is stale — stopping.")
                smoothed_offset = 0.0
                await stop_robot()
                await asyncio.sleep(POLL_DELAY)
                continue

            if box_width >= STOP_BOX_WIDTH:
                print(
                    f"Person is close — stopping. "
                    f"Box width: {box_width:.1f}"
                )

                smoothed_offset = 0.0
                await stop_robot()
                await asyncio.sleep(POLL_DELAY)
                continue

            await follow_person(float(offset))

        except requests.RequestException as error:
            print(
                f"Flask connection failed — stopping: "
                f"{error}"
            )

            smoothed_offset = 0.0
            await stop_robot()

        except (TypeError, ValueError) as error:
            print(
                f"Invalid detection data — stopping: "
                f"{error}"
            )

            smoothed_offset = 0.0
            await stop_robot()

        await asyncio.sleep(POLL_DELAY)


if __name__ == "__main__":
    try:
        loop.run_until_complete(main())

    except KeyboardInterrupt:
        print("\nStopping controller...")

    finally:
        try:
            loop.run_until_complete(stop_robot())
        except Exception as error:
            print(f"Could not stop RVR: {error}")

        http_session.close()

        try:
            loop.run_until_complete(rvr.close())
        except Exception:
            pass

        loop.close()
        print("Done.")