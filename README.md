# Autonomous Obstacle-Avoiding Sphero RVR+ Robot
Raspberry Pi based project built for a summer program using sensors and code for the robot to avoid obstacles and drive in a different direction. This is part of a wider autonomous robotics project with the Sphero RVR+ which soon may have more sensors and more complicated movements.

The robot can be used to explore rooms, avoid obstructions, and navigate through simple mazes.

## Abilities
• Moves around autonomously without user input

• Automatically detects obstacles in front of the robot

• Detects and navigates around objects by moving in a separate direction

> [!NOTE]
> The currently implemented camera and person-following system is experimental. Testing and development were limited by the available hardware and software setup.

## Project Files

• `ultrasonic.py`: Main obstacle-avoidance program. Uses an ultrasonic sensor to detect obstructions and autonomously navigate around them.

• `following.py`: Experimental person-following controller that uses a person's position in the camera frame to determine the robot's movement.

• `object_detection_web.py`: Flask and YOLO-based server that processes the USB camera feed, performs object/person detection, and provides detection data to the person-following controller.

## Hardware
• Raspberry Pi 5 8GB

## Possible Improvements
• Integrate multiple ultrasonic sensors or a sensor mounted on a servo in order to "see" in multiple directions and decide the best path

• Improve the setup by mounting the Raspberry Pi board and sensors, use a dedicated Raspberry Pi Camera, portable 5V/5A power bank

• Better obstacle-avoiding logic (with better hardware and software, possible ability to map and find better paths)

• Significant improvement on the coding and functionality of the camera/web/person-following project

