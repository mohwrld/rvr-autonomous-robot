import threading
import time
from pathlib import Path

import cv2
from flask import Flask, Response, jsonify
from ultralytics import YOLO


app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "yolo11n.pt"

FRAME_WIDTH = 640
FRAME_HEIGHT = 480
JPEG_QUALITY = 75
CAMERA_RETRY_DELAY = 1.0

if not MODEL_PATH.exists():
    raise FileNotFoundError(
        f"YOLO model not found at {MODEL_PATH}. "
        "Place yolo11n.pt in the same folder as this script."
    )

model = YOLO(str(MODEL_PATH))

camera = None
camera_path = None
camera_lock = threading.Lock()

latest_objects = []

latest_person = {
    "detected": False,
    "center_x": None,
    "offset_x": None,
    "normalized_offset": None,
    "box_width": None,
    "confidence": None,
    "image_width": FRAME_WIDTH,
    "timestamp": 0.0,
}

detections_lock = threading.Lock()


def get_camera_candidates():
    candidates = []

    by_id_dir = Path("/dev/v4l/by-id")

    if by_id_dir.exists():
        preferred_links = sorted(
            by_id_dir.glob("*C920*video-index0")
        )

        other_index_zero_links = sorted(
            by_id_dir.glob("*video-index0")
        )

        for path in preferred_links + other_index_zero_links:
            path_string = str(path)

            if path_string not in candidates:
                candidates.append(path_string)

    sysfs_dir = Path("/sys/class/video4linux")

    if sysfs_dir.exists():
        preferred_devices = []
        other_devices = []

        for video_dir in sorted(sysfs_dir.glob("video*")):
            device_path = f"/dev/{video_dir.name}"
            name_file = video_dir / "name"

            try:
                device_name = name_file.read_text().strip().lower()
            except OSError:
                device_name = ""

            if (
                "c920" in device_name
                or "webcam" in device_name
                or "usb camera" in device_name
            ):
                preferred_devices.append(device_path)
            else:
                other_devices.append(device_path)

        for path_string in preferred_devices + other_devices:
            if path_string not in candidates:
                candidates.append(path_string)

    return candidates


def try_open_camera(candidate):
    test_camera = cv2.VideoCapture(candidate)

    if not test_camera.isOpened():
        test_camera.release()
        return None

    test_camera.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        FRAME_WIDTH,
    )
    test_camera.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        FRAME_HEIGHT,
    )
    test_camera.set(
        cv2.CAP_PROP_BUFFERSIZE,
        1,
    )

    success, frame = test_camera.read()

    if not success or frame is None:
        test_camera.release()
        return None

    return test_camera


def connect_camera():
    global camera
    global camera_path

    with camera_lock:
        if camera is not None:
            camera.release()
            camera = None
            camera_path = None

        candidates = get_camera_candidates()

        for candidate in candidates:
            opened_camera = try_open_camera(candidate)

            if opened_camera is not None:
                camera = opened_camera
                camera_path = candidate

                print(f"Using camera: {camera_path}")
                return True

    print("No usable USB camera was found.")
    return False


def read_camera_frame():
    global camera

    with camera_lock:
        if camera is None:
            return False, None

        return camera.read()


def release_camera():
    global camera
    global camera_path

    with camera_lock:
        if camera is not None:
            camera.release()

        camera = None
        camera_path = None


def generate_frames():
    global latest_objects
    global latest_person

    while True:
        if camera is None:
            if not connect_camera():
                time.sleep(CAMERA_RETRY_DELAY)
                continue

        success, frame = read_camera_frame()

        if not success or frame is None:
            print(
                "Camera frame failed. "
                "Searching for the camera again..."
            )

            release_camera()
            time.sleep(CAMERA_RETRY_DELAY)
            continue

        frame_height, frame_width = frame.shape[:2]

        try:
            result = model.predict(
                source=frame,
                imgsz=320,
                conf=0.45,
                verbose=False,
            )[0]
        except Exception as error:
            print(f"YOLO prediction failed: {error}")
            time.sleep(0.1)
            continue

        detected_objects = set()
        non_person_detections = []
        person_detections = []

        if result.boxes is not None:
            coordinates = result.boxes.xyxy.tolist()
            class_ids = result.boxes.cls.tolist()
            confidences = result.boxes.conf.tolist()

            for box, class_id, confidence in zip(
                coordinates,
                class_ids,
                confidences,
            ):
                object_name = result.names[int(class_id)]
                detected_objects.add(object_name)

                detection = {
                    "box": box,
                    "name": object_name,
                    "confidence": float(confidence),
                }

                if object_name == "person":
                    person_detections.append(detection)
                else:
                    non_person_detections.append(detection)

        selected_person = None

        if person_detections:
            selected_person = max(
                person_detections,
                key=lambda detection: (
                    detection["box"][2]
                    - detection["box"][0]
                )
                * (
                    detection["box"][3]
                    - detection["box"][1]
                ),
            )

            x1, y1, x2, y2 = selected_person["box"]

            center_x = (x1 + x2) / 2
            box_width = x2 - x1

            image_center_x = frame_width / 2
            offset_x = center_x - image_center_x

            normalized_offset = (
                offset_x / image_center_x
            )

            normalized_offset = max(
                -1.0,
                min(1.0, normalized_offset),
            )

            person_data = {
                "detected": True,
                "center_x": round(center_x, 2),
                "offset_x": round(offset_x, 2),
                "normalized_offset": round(
                    normalized_offset,
                    4,
                ),
                "box_width": round(box_width, 2),
                "confidence": round(
                    selected_person["confidence"],
                    4,
                ),
                "image_width": frame_width,
                "timestamp": time.time(),
            }

        else:
            person_data = {
                "detected": False,
                "center_x": None,
                "offset_x": None,
                "normalized_offset": None,
                "box_width": None,
                "confidence": None,
                "image_width": frame_width,
                "timestamp": time.time(),
            }

        with detections_lock:
            latest_objects = sorted(detected_objects)
            latest_person = person_data

        annotated_frame = frame.copy()
        detections_to_draw = non_person_detections.copy()

        if selected_person is not None:
            detections_to_draw.append(selected_person)

        for detection in detections_to_draw:
            x1, y1, x2, y2 = detection["box"]

            x1 = int(x1)
            y1 = int(y1)
            x2 = int(x2)
            y2 = int(y2)

            object_name = detection["name"]
            confidence = detection["confidence"]

            if object_name == "person":
                color = (0, 255, 0)
            else:
                color = (255, 170, 0)

            cv2.rectangle(
                annotated_frame,
                (x1, y1),
                (x2, y2),
                color,
                2,
            )

            label = (
                f"{object_name} "
                f"{confidence:.2f}"
            )

            cv2.putText(
                annotated_frame,
                label,
                (x1, max(y1 - 8, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
            )

        encoded, buffer = cv2.imencode(
            ".jpg",
            annotated_frame,
            [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY],
        )

        if not encoded:
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + buffer.tobytes()
            + b"\r\n"
        )


@app.route("/")
def index():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >

    <title>Robot Camera</title>

    <style>
        body {
            margin: 0;
            padding: 20px;
            background: #202020;
            color: white;
            font-family: Arial, sans-serif;
            text-align: center;
        }

        .container {
            max-width: 640px;
            margin: auto;
        }

        .camera {
            width: 100%;
            max-width: 480px;
            height: auto;
            border: 2px solid #555;
            border-radius: 10px;
        }

        .panel {
            max-width: 448px;
            margin: 16px auto 0;
            padding: 14px;
            background: #303030;
            border-radius: 10px;
        }

        #objects {
            min-height: 24px;
            margin: 10px 0;
            font-size: 18px;
        }

        #speechStatus {
            min-height: 22px;
            color: #bbbbbb;
        }

        button {
            margin: 8px;
            padding: 10px 16px;
            border: none;
            border-radius: 7px;
            color: white;
            font-size: 15px;
            cursor: pointer;
        }

        #enableSpeech {
            background: #2563eb;
        }

        #muteSpeech {
            background: #b91c1c;
        }
    </style>
</head>

<body>
    <main class="container">
        <h1>Robot Object Detection</h1>

        <img
            class="camera"
            src="/video_feed"
            alt="Live robot camera feed"
        >

        <section class="panel">
            <h2>Detected objects</h2>

            <div id="objects">
                Waiting for detections...
            </div>

            <div id="speechStatus">
                Speech is disabled.
            </div>

            <button id="enableSpeech" type="button">
                Enable speech
            </button>

            <button id="muteSpeech" type="button">
                Mute
            </button>
        </section>
    </main>

    <script>
        let speechEnabled = false;
        let lastSpokenTime = 0;
        let sentenceIndex = 0;

        const speechDelay = 7000;

        const objectsElement =
            document.getElementById("objects");

        const speechStatusElement =
            document.getElementById("speechStatus");

        const enableSpeechButton =
            document.getElementById("enableSpeech");

        const muteSpeechButton =
            document.getElementById("muteSpeech");

        function chooseArticle(objectName) {
            return /^[aeiou]/i.test(objectName)
                ? "an"
                : "a";
        }

        function formatObjectList(objects) {
            const namedObjects = objects.map(
                objectName =>
                    `${chooseArticle(objectName)} ${objectName}`
            );

            if (namedObjects.length === 1) {
                return namedObjects[0];
            }

            if (namedObjects.length === 2) {
                return (
                    `${namedObjects[0]} and ` +
                    `${namedObjects[1]}`
                );
            }

            const firstObjects = namedObjects
                .slice(0, -1)
                .join(", ");

            const lastObject =
                namedObjects[
                    namedObjects.length - 1
                ];

            return (
                `${firstObjects}, and ` +
                `${lastObject}`
            );
        }

        function makeSentence(objects) {
            const objectList =
                formatObjectList(objects);

            const patterns = [
                `I can see ${objectList}.`,
                `The camera detects ${objectList}.`,
                `In front of the robot, I see ${objectList}.`,
                `Currently visible: ${objectList}.`,
                `The robot is looking at ${objectList}.`
            ];

            const sentence =
                patterns[
                    sentenceIndex
                    % patterns.length
                ];

            sentenceIndex += 1;

            return sentence;
        }

        function speakObjects(objects) {
            if (
                !speechEnabled
                || objects.length === 0
            ) {
                return;
            }

            const sentence =
                makeSentence(objects);

            window.speechSynthesis.cancel();

            const speech =
                new SpeechSynthesisUtterance(
                    sentence
                );

            speech.rate = 1;
            speech.pitch = 1;
            speech.volume = 1;

            window.speechSynthesis.speak(speech);

            speechStatusElement.textContent =
                `Speaking: ${sentence}`;
        }

        async function updateDetections() {
            try {
                const response = await fetch(
                    "/detections",
                    {
                        cache: "no-store"
                    }
                );

                if (!response.ok) {
                    throw new Error(
                        `HTTP error ${response.status}`
                    );
                }

                const data =
                    await response.json();

                const objects =
                    data.objects || [];

                if (objects.length === 0) {
                    objectsElement.textContent =
                        "No recognized objects";
                } else {
                    objectsElement.textContent =
                        objects.join(", ");
                }

                const enoughTimePassed =
                    Date.now()
                    - lastSpokenTime
                    >= speechDelay;

                const alreadySpeaking =
                    window.speechSynthesis.speaking;

                if (
                    speechEnabled
                    && objects.length > 0
                    && enoughTimePassed
                    && !alreadySpeaking
                ) {
                    speakObjects(objects);

                    lastSpokenTime =
                        Date.now();
                }

            } catch (error) {
                console.error(error);

                objectsElement.textContent =
                    "Could not retrieve detections";
            }
        }

        enableSpeechButton.addEventListener(
            "click",
            () => {
                speechEnabled = true;
                lastSpokenTime = 0;

                speechStatusElement.textContent =
                    "Speech is enabled.";

                window.speechSynthesis.cancel();

                const confirmation =
                    new SpeechSynthesisUtterance(
                        "Speech enabled."
                    );

                confirmation.rate = 1;
                confirmation.pitch = 1;
                confirmation.volume = 1;

                window.speechSynthesis.speak(
                    confirmation
                );
            }
        );

        muteSpeechButton.addEventListener(
            "click",
            () => {
                speechEnabled = false;

                window.speechSynthesis.cancel();

                speechStatusElement.textContent =
                    "Speech is disabled.";
            }
        );

        setInterval(
            updateDetections,
            1000
        );

        updateDetections();
    </script>
</body>
</html>
"""


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(),
        mimetype=(
            "multipart/x-mixed-replace; "
            "boundary=frame"
        ),
    )


@app.route("/detections")
def detections():
    with detections_lock:
        objects = latest_objects.copy()
        person = latest_person.copy()

    return jsonify(
        {
            "objects": objects,
            "person": person,
            "camera": camera_path,
        }
    )


if __name__ == "__main__":
    try:
        if not connect_camera():
            print(
                "Camera is not currently available. "
                "The server will keep retrying when "
                "/video_feed is opened."
            )

        app.run(
            host="0.0.0.0",
            port=5000,
            threaded=True,
            debug=False,
            use_reloader=False,
        )

    finally:
        release_camera()