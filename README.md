# Autonomous Obstacle-Avoiding Sphero RVR+ Robot
Raspberry Pi-based project built for a summer program utilizing several sensors and Python code for the robot to autonomously avoid obstacles and drive in different directions. This is part of a wider autonomous robotics project with the Sphero RVR+ which soon may incorporate more sensors and more advanced movement and logic.

The robot can be used to explore rooms, avoid obstructions, and navigate through simple mazes.

## Abilities
• Moves around autonomously without user input

• Automatically detects obstacles in front of the robot

• Detects and avoids objects by changing direction into a clear path

> [!NOTE]
> The currently implemented camera and person-following system is experimental. Testing and development were limited by the available hardware and software setup.

## Project Files

• `ultrasonic.py`: Main obstacle-avoidance program. Uses an ultrasonic sensor to detect obstructions and autonomously navigate around them.

• `following.py`: Experimental person-following controller that uses a person's position in the camera frame to determine the robot's movement.

• `object_detection_web.py`: Flask and YOLO-based server that processes the USB camera feed, performs object/person detection, and provides detection data to the person-following controller.

## Hardware Used
• Sphero RVR+ Robot

• Raspberry Pi 5 8GB

• HC-SR04 ultrasonic sensor

• USB Camera

## Possible Improvements
• Integrate multiple ultrasonic sensors or a sensor mounted on a servo in order to "see" in multiple directions and decide the best path

• Improve the physical setup by mounting the Raspberry Pi board and sensors, using a dedicated Raspberry Pi Camera, and powering via portable 5V/5A power bank

• Better obstacle-avoiding logic (with better hardware and software, possible ability to map and find better paths)

• Significant improvement on the coding, utility, and functionality of the camera/web/person-following project

