# Autonomous Obstacle-Avoiding Sphero RVR+ Robot
Raspberry Pi based project built for a summer program using sensors and code for the robot to avoid obstacles and drive in a different direction. This is part of a wider autonomous robotics project with the Sphero RVR+ which soon may have more sensors and more complicated movements. The robot can be used to navigate through mazes and explore rooms.

## Abilities
• Moves around autonomously without user input
• Automatically detects obstacles in front of the robot
• Deters and navigates around objects by moving in a separate direction

• Currently has a poorly-tested feature where the robot tries to detect and follow ones position using a connected camera, viewed from a website the Raspberry Pi is hosting (Testing and improvement was limited by hardware setup)

## Possible Improvements
• Integrate multiple ultrasonic sensors or a sensor mounted on a Swervo in order to "see" in multiple directions and decide the best path
• Improve the setup by mounting the Raspberry Pi board and sensors, use a dedicated Raspberry Pi Camera, portable 5V/5A power bank
• Better obstacle-avoiding logic (with better hardware and software, possible ability to map and find better paths)
• Significant improvement on the coding and functionality of the camera/web/person-following project

