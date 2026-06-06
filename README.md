**ServoSorter** is a utility that uses commonly available, low-cost RC/hobbyist servos to provide a tiered sorting function.

- [Overview and Terminology](#overview-and-terminology)
- [Installation](#installation)
- [Usage](#usage)
- [Software Dependencies](#software-dependencies)
- [Hardware Requirements](#hardware-requirements)
- [Other Requirements](#other-requirements)
- [3D-Printed Assets](#3d-printed-assets)
- [Future Plans](#future-plans)
- [Additional Information](#additional-information)

# Overview and Terminology
<img width="420" height="500" alt="SortingMachineSmaller" src="https://github.com/user-attachments/assets/a95718f1-c8e4-43ed-80e4-d5efb9eb689e" />

This solution requires a controlling program to detect/declare an object's "sort attribute" prior to sending an object into the sorter. A simple example to consider is sorting marbles using a sort attribute of color. Your controlling program would detect the marble's color and tell that color to ServoSorter. ServoSorter would then configure the servos accordingly prior to the marble being dropped into the sorting device. The marble would then drop into bin assigned to that color.

Each servo is installed in a housing ("chute") and attached to a deflector arm ("flap") that directs an object one way ("main") or another ("alt"). The process requires gravity to move the object through the process. Once the object goes through the servo's chute, the object is sent either into another chute or into its final, sorted location ("bin"). Each chute is organized into a tier ("layer"). Each layer doubles in size compared to the prior layer.

In the video above, you can see an object dropping into bin 2 and then the machine preparing for the next object by moving the servos to point to bin 3.

# Installation

ServoSorter is available as a Python package on PyPI. To install:
1. Navigate to your project folder
    ```bash
    cd /path/to/your/project
    ```
2. Create a virtual environment (named ".venv" by convention, but can be named anything)

   ```bash
   python3 -m venv .venv
   ```
3. Activate the virtual environment

   ```bash
   source .venv/bin/activate
   ```
4. Install the package from the **(.venv) $** prompt

    ```bash
    python3 -m pip install servo-sorter
    ```
# Usage

Instantiate the ServoSorter class with the following arguments:

- **sorter_name** - a unique name of your choice to distinguish it from any other ServoSorter-consuming processes
- **servo_count** - the number of servos your sorting process is using (the number of available bins will always be equal to the servo_count + 1)
- **driver_i2c_addresses** - a list of i2c addresses associated to your PCA9685 servo drivers
- **actuation_ranges** - a "list of lists" containing the actuation ranges (e.g. 90, 180, etc. depending on what types of micro servos you're using)
- **main_angles** - a "list of lists" containing the "main" angle values for each servo being used
- **alt_angles** - a "list of lists" containing the "alt" angle values for each servo being used
- (optional) **servo_sleep_duration_seconds** - the number of seconds between each servo movement; defaults to 0; partial seconds are allowed (e.g. .5)
- (optional) **avoid_unnecessary_servo_movement** - determines whether to move only the servos necessary for the specified bin (True) or move all servos (False); defaults to True

```python
import servo_sorter

# assumes you have 7 servos, three attached to the first driver, four attached to the second driver
# the first driver's address is 0x40 (which is the board's default)
# the second driver's address is 0x41 (accomplished via soldering a jumper on the board)
# all servos have a 90 degree actuation range except the second one, which has a 180 degree actuation range
my_sorter = servo_sorter.ServoSorter("TestSorter", 7, [0x40, 0x41], \
                     [[90, 180, 90], [90, 90, 90, 90]], \
                     [[20,  24, 16], [12, 14, 10, 12]], \
                     [[76, 148, 74], [66, 70, 66, 66]], \
                     0, True)
```

When your logic wants to move the sorting device to point to a bin associated to a particular sort attribute, use the <code>move_servos_to_sort_attribute_bin</code> method. The provided sort attribute value can be any text value of your choice (e.g. colors, types, etc.) depending on what you're sorting. [NOTE: if ServoSorter "runs out" of bins and cannot assign one for the sort attribute you're passing in, it will use bin 1 as the default.]

```python
found_bin_boolean, assigned_bin_boolean, bin_value, sort_attribute = 
my_sorter.move_servos_to_sort_attribute_bin("green")
```

When your logic wants to control bin assignments directly and point to a specific bin number, use the <code>move_servos_directly_to_bin</code> method:

```python
configured_bin_number = my_sorter.move_servos_directly_to_bin(4)
```

If your logic wants to reset a bin assignment, use the <code>reset_bin</code> method:
```python
reset_bin_successful_boolean = my_sorter.reset_bin(4)
```
If your logic wants to reset all bin assignments, use the <code>reset_all_bins</code> method:
```python
reset_all_bins_successful_boolean = my_sorter.reset_all_bins()
```

Bin assignments can be seen in the JSON file created by servo-sorter. The filename will be formatted as *[sorter_name].servosorter_db.json* and it will look something like this:
```json
{
    "bins": [
        "DEFAULT",
        "OPEN",
        "OPEN",
        "green",
        "red",
        "blue",
        "white"
    ]
}
```
# Software Dependencies

This package leverages the [adafruit-circuitpython-servokit](https://github.com/adafruit/Adafruit_CircuitPython_ServoKit) Python package (which will be installed automatically).

Your controlling logic environment must be running Python 3.11 or later and have an i2c interface enabled.

# Hardware Requirements

ServoSorter operates on a Python-supported device (e.g. a Raspberry Pi running the Raspberry Pi OS / Debian Linux).

It requires the attachment of one or more 16-channel PCA9685 PWM/Servo drivers (each of which can manage up to 16 servos). The PCA9685 is required because a typical device like a Raspberry Pi cannot provide enough power to reliably actuate servos. PCA9685 devices each leverage their own power supply (which need to be purchased separately) and can be chained together, so the solution requires that only a single PCA9685 be connected to your controlling device. The PCA9685 utilizes i2c for communication, so your device must also support i2c. You can buy the PCA9685 directly from Adafruit [here](https://www.adafruit.com/product/815). You can also get generic versions from [Micro Center](https://www.microcenter.com/product/639725/inland-ks006516-channel-12-bit-pwm-servo-driver-i2c-interface) or [Amazon](https://a.co/d/03u5w4rV) with the headers already attached. I've successfully used [this power supply](https://a.co/d/0j9ds8GN) to power the PCA9685, but there are many options.

You need to use only positional rotation servos (e.g. 90-degree, 180-degree). Continuous rotation servos and linear servos are not supported. I recommend buying servos with clutches (even though they are a little more expensive). I've used [this one from Maker's Supply](https://us.store.bambulab.com/products/9g-servo-motor-with-clutch-protection?id=42123031019656) (make sure to get the positional one, NOT the continuous rotation one). They get cheaper if you buy them in bulk. A servo with a clutch will better handle the scenario where your servo gets jammed/stalled and will adjust accordingly. The cheaper servos (I've used [these from Micro Center](https://www.microcenter.com/product/613883/inland-ks0209-blue-9g-servo-motor) and [these from Amazon](https://a.co/d/03cdrJ0h)) will just burn out if they get jammed/stalled for any significant amount of time, which could lead to bigger issues (including spiked power consumption and even potential fires). If you go witht the cheaper servos, you might consider adding a fuse to your solution.

# Other Requirements

<img width="1283" height="1525" alt="ServoNumbering" src="https://github.com/user-attachments/assets/c43d76b2-3b3e-448c-b12d-194e7fbc10cd" />


At present, servos must be organized into COMPLETE layers and in order by servo number from left to right. In the image above, you see a sorter with seven servos showing you the order in which the servos need to be configured. With each layer doubling the number of servos from the previous layer, the allowed number of servos is 1, 3, 7, 15, 31, 63, 127, 255, or 511. The maximum number of PCA9685 drivers supported by the ServoKit library is 62. With each driver supporting up to 16 servos, the theoretical maximum number of servos is 992, but the layer requirements described above cap the max number at 511. This equates to a maximum number of "bins" of 512 and a maximum number of drivers of 32.

Servos must be attached to a driver "in order". PCA9685 driver boards may label the servo connectors 0-15. So, the first servo must be attached to slot 0, the second servo to slot 1, the third servo to slot 2, etc. Because multiple servo drivers (the i2c addresses of which are passed into ServoSorter) can be used, it needs to know which servos are connected to which drivers. This is accomplished via the "list of lists" passed in for actuation ranges, main angles, and alt angles when instantiating the ServoSorter class. Values in the first list relate to servos attached to the first driver. Values in the second list relate to servos attached to the second driver, and so on. It is ok not to "fill up" a driver with servos, but the rules above must be adhered to.

If multiple servo drivers are to be used, you must solder the jumpers on the second driver (and beyond) to create unique i2c addresses for them. Refer to [this Adafruit article](https://learn.adafruit.com/16-channel-pwm-servo-driver/chaining-drivers) for details on how to do that.

A sorted object must complete its sorting procedure before the next object is sorted. In other words, an object cannot still be in the sorting device when the next object is sent in to be sorted.

Servos need to be calibrated. Due to variations in servo actuation angle ranges (as well as any variations in the housings you might use), it is required to calibrate each servo so that ServoSorter knows its precise "main" and "alt" angle values. The calibration results will dictate the numbers you plug into the "main angle" and "alt angle" lists that are passed in when instantiating the ServoSorter class. You can use logic like this (after installing the servo-sorter package and adding some horns/arms to your servos) to do your calibrations to determine what your main/alt values should be for your scenario:

```python
from adafruit_servokit import ServoKit
i2c_address = 0x40
kit = ServoKit(channels=16, address=i2c_address)

servo_slot = 0 # assumes servo is connected to PCA9685's first slot
actuation_range = 90 # assumes the servo's actuation range is 90 degrees

kit.servo[servo_slot].actuation_range = actuation_range

kit.servo[servo_slot].angle = 0 # try different angle values between 0 and the servo's actuation range
```

# 3D-Printed Assets

You can use [this model](https://makerworld.com/en/models/2878141-flush-mount-servo-enclosure-embedded-servo-horns#profileId-3214191) as a starting point for your project's servo housings and flaps/arms. I will soon be publishing another model that looks more like the one in my video above and I will update this README once I do that.

# Future Plans

The following are being considered for future enhancements:

- Create an admin tool using Textual (a Python text-based UI platform) to help with things like calibration.
 
- Support when a given layer has just a few servos (eliminating the requirement for exactly 1, 3, 7, 15, 31, 63, 127, 255, or 511 servos).

- Add support for "break beam" sensors to confirm when a sorted object leaves the sorting device.

- Feature to "re-do" servo movements in order in case the sorted object gets stuck in the sorting device (in an attempt to free/dislodge the object).

- Allow "locking" of bin assignments.

# Additional Information
Here is a full list of valid i2c addresses that can be provided for the PCA9685 address values (controllable per driver by using soldered jumpers on each PCA9685 board):
```text
0x40, 0x41, 0x42, 0x43, 0x44,
0x45, 0x46, 0x47, 0x48, 0x49,
0x4a, 0x4b, 0x4c, 0x4d, 0x4e,
0x4f, 0x50, 0x51, 0x52, 0x53,
0x54, 0x55, 0x56, 0x57, 0x58,
0x59, 0x5a, 0x5b, 0x5c, 0x5d,
0x5e, 0x5f, 0x60, 0x61, 0x62,
0x63, 0x64, 0x65, 0x66, 0x67,
0x68, 0x69, 0x6a, 0x6b, 0x6c,
0x6d, 0x6e, 0x6f, 0x70, 0x71,
0x72, 0x73, 0x74, 0x75, 0x76,
0x77, 0x78, 0x79, 0x7a, 0x7b,
0x7c, 0x7d, 0x7e, 0x7f
```
