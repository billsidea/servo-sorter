from adafruit_servokit import ServoKit
import math
import time
import json
import logging
import platformdirs
from pathlib import Path

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class ServoSorter:
    """ServoSorter is a utility that uses commonly available, low-cost RC/hobbyist servos to provide a tiered sorting
    function. The most economical servo is the SG90 micro servo.
    
    Each servo is installed in a housing ("chute") and attached to a deflector arm ("flap") that directs an object one
    way ("main") or another ("alt"). The process requires gravity to move the object through the process. Once the
    object goes through the servo's chute, the object is sent either into another chute or into its final, sorted
    location ("bin"). Each chute is organized into a tier ("layer"). Each layer doubles in size compared to the prior
    layer (see diagram below).
    
    ServoSorter operates on a Python-supported device (e.g. a Raspberry Pi running the Raspberry Pi OS / Linux) and
    uses the Adafruit ServoKit library (https://github.com/adafruit/Adafruit_CircuitPython_ServoKit). It requires the
    attachment of one or more PCA9685 PWM/Servo drivers (each of which can manage up to 16 servos). The PCA9685 is
    required because a typical device like a Raspberry Pi cannot provide enough power to reliably actuate servos.
    PCA9685 devices each leverage their own power supply (which need to be purchased separately) and can be chained
    together, so the solution requires that only a single PCA9685 be connected to your controlling device. The PCA9685
    utilizes I2C for communication, so your device must also support I2C.
    
    ServoSorter needs to know:
    - The number of connected servos/chutes. This cannot easily be detected automatically, so it needs to be provided
      as a configuration value by the user.
    
    ServoSorter requires:
    - That you use only positional rotation servos (e.g. 90-degree, 180-degree). Continuous rotation servos and
      linear servos are not supported.
    - That servos are organized into COMPLETE layers. With each layer doubling the number of servos from the
      previous layer, the allowed number of servos is 1, 3, 7, 15, 31, 63, 127, 255, or 511. The maximum number of
      PCA9685 drivers supported by the ServoKit library is 62. With each driver supporting up to 16 servos, the
      theoretical maximum number of servos is 992, but the layer requirements described above cap the max number
      at 511. This equates to a maximum number of "bins" of 512 and a maximum number of drivers of 32.
    - That you use only 16-channel PCA9685 devices. There are some that exist with only 8 channels and those are not
      supported by ServoSorter.
    - That servos are attached to a driver "in order". PCA9685 drivers label the servo connectors 0-15. So, the
      first servo must be attached to slot 0, the second servo to slot 1, the third servo to slot 2, etc. Note that
      ServoSorter documentation will refer to these as servos 1-16 (not 0-15).
    - That a sorted object completes its sorting procedure before the next object is sorted. In other words, an
      object cannot still be in the sorting device when the next object is sent in to be sorted.
    - That servos be calibrated. Due to variations in servo actuation angle ranges, it is required to calibrate
      each servo so that ServoSorter knows its precise "main" and "alt" angle values.
      
    Notable:
    - PCA9685 drivers label the servos 0-15. ServoSorter documentation will refer to these as servos 1-16.
    """

    # class variables (shared by all instances)
    servo_driver_channels = 16

    PACKAGE_NAME = "servo_sorter"

    # initialization of class
    def __init__(self, sorter_name, servo_count, driver_i2c_addresses, actuation_ranges, main_angles, alt_angles, \
                 servo_sleep_duration_seconds=0, avoid_unnecessary_servo_movement=True):

        # instance variables (unique to each instance)
        self.sorter_name = sorter_name
        self.number_of_servos = servo_count
        self.number_of_bins = servo_count + 1
        self.only_move_necessary_servos = avoid_unnecessary_servo_movement
        self.sleep_duration_between_servo_movements = servo_sleep_duration_seconds
        self._current_bin = 1 # protected; updated only by move_servos_to_bin and exposed via current_bin property
        self.kit = []
        self.actuation_ranges = []
        self.main_angles = []
        self.alt_angles = []
        self.driver_i2c_addresses = []
        self.json_db = {}
        
        # open / initialize json file as database
        self.sorter_db_filename = str(sorter_name) + "_servosorter_db.json"
        self.sorter_db_path = Path(platformdirs.user_config_dir(self.PACKAGE_NAME)) / self.sorter_db_filename
        if not self.sorter_db_path.exists():
            self.sorter_db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.sorter_db_path, 'r', encoding='utf-8') as f:
                self.json_db = json.load(f)
        except FileNotFoundError:
            # the file is not there, create it with some defaults
            with open(self.sorter_db_path, 'w', encoding='utf-8') as f:
                self.json_db = {"bins": ["DEFAULT"]}
                json.dump(self.json_db, f, indent=4, ensure_ascii=False)
            
        #self._driver_count = math.ceil(self.number_of_servos / self.servo_driver_channels)
        self._driver_count = len(actuation_ranges)
        self.driver_i2c_addresses = driver_i2c_addresses
        
        # input validations
        if(self._driver_count != len(main_angles) or self._driver_count != len(alt_angles) or self._driver_count != len(self.driver_i2c_addresses)):
            raise ValueError("There is an inconsistency with the number of drivers indicated by " \
                             f"the actuation range settings ({len(actuation_ranges)} drivers), the main angles setting ({len(main_angles)} drivers), " \
                             f"the alt angles setting ({len(alt_angles)} drivers), and driver i2c address setting ({len(self.driver_i2c_addresses)} drivers)")
        
        for i in range(len(actuation_ranges)):
            if(len(actuation_ranges[i]) != len(main_angles[i]) or len(actuation_ranges[i]) != len(alt_angles[i])):
                raise ValueError("The provided arrays for actuation ranges, main angles, and alt angles do not specify the same number of values for each driver")
        
        if(len(self.driver_i2c_addresses) != len(set(self.driver_i2c_addresses))):
            raise ValueError("The provided array of driver addresses contains duplicate values")
        
        if(self.number_of_servos not in [1, 3, 7, 15, 31, 63, 127, 255, 511]):
            raise ValueError(f"The specified number of servos ({self.number_of_servos}) is not a supported value")
        
        provided_actuation_values = sum(len(row) for row in actuation_ranges)
        if(provided_actuation_values != self.number_of_servos):
            raise ValueError(f"The provided number of actuation range values ({provided_actuation_values}) does not equal the number of servos ({self.number_of_servos})")

        provided_main_angle_values = sum(len(row) for row in main_angles)
        if(provided_main_angle_values != self.number_of_servos):
            raise ValueError(f"The provided number of main angle values ({provided_main_angle_values}) does not equal the number of servos ({self.number_of_servos})")

        provided_alt_angle_values = sum(len(row) for row in alt_angles)
        if(provided_alt_angle_values != self.number_of_servos):
            raise ValueError(f"The provided number of alt angle values ({provided_alt_angle_values}) does not equal the number of servos ({self.number_of_servos})")

        # instantiate a ServoKit object per driver (number inferred by number of servos) and
        # set servo actuation range values and main/alt angle values
        # we are expecting an array of arrays for actuation ranges, main angles, and alt angles
        try:
            for i in range(self._driver_count):
                # determine driver address and pass appropriate value
                self.kit.append(ServoKit(channels=self.servo_driver_channels, address=self.driver_i2c_addresses[i]))
                self.actuation_ranges.append(actuation_ranges[i])
                self.main_angles.append(main_angles[i])
                self.alt_angles.append(alt_angles[i])
        except ValueError as e:
            e.add_note("ServoSorter cannot communicate with a specified servo driver. Check the i2c addresses being passed.")
            logger.exception(e)
            raise
        except (IndexError, TypeError) as e:
            logger.error(e)
            raise AddressRangeAngleError()

        try:
            for i in range(self.number_of_servos):
                work_driver_index, work_servo_index = self._determine_servo_index_values(i + 1) # the called function expects a servo number, not the index
                logger.debug("work driver index: %s, work servo index: %s, actuation range: %s",
                             work_driver_index, work_servo_index, self.actuation_ranges[work_driver_index][work_servo_index])
                self.kit[work_driver_index].servo[work_servo_index].actuation_range = self.actuation_ranges[work_driver_index][work_servo_index]
                # move servo to "main" angle upon initialization
                self.kit[work_driver_index].servo[work_servo_index].angle = self.main_angles[work_driver_index][work_servo_index]
                if(self.sleep_duration_between_servo_movements > 0):
                    time.sleep(self.sleep_duration_between_servo_movements)
        except (IndexError, TypeError) as e:
            logger.error(e)
            raise AddressRangeAngleError()
        
        logger.info("ServoSorter class instantiated")
        
    # methods
    def _determine_servo_index_values(self, servo_number):
#         work_driver_index = math.ceil(servo_number / self.servo_driver_channels) - 1 # 0-based indexing
#         work_servo_index = (servo_number - (work_driver_index * self.servo_driver_channels)) - 1 # 0-based indexing
#         return work_driver_index, work_servo_index
        current_count = 0
        
        for row_index, row in enumerate(self.actuation_ranges):
            row_length = len(row)
            
            # Check if the servo number value falls within the current row
            if current_count + row_length >= servo_number:
                # Find the exact index in the row (1-based index)
                target_index = servo_number - current_count - 1
                return row_index, target_index
                
            current_count += row_length
            
        return None, None  # provided servo number exceeds total elements    
        
    def reset_bin(self, bin_number):
        if(bin_number == 1):
            return False # bin 1 is reserved
        else:
            try:
                self.json_db["bins"][bin_number - 1] = "OPEN"
                self._save_db()
                return True
            except ValueError:
                # bin not found
                return False

    def reset_all_bins(self):
        self.json_db["bins"] = ["DEFAULT"]
        self._save_db()
        return True
    
    def _save_db(self):
        with open(self.sorter_db_path, 'w', encoding='utf-8') as f:
            json.dump(self.json_db, f, indent=4, ensure_ascii=False)
        
    def retrieve_or_assign_bin_for_sort_attribute(self, sort_attribute):
        found_bin = False
        assigned_bin = False
        selected_bin_index = 0
        selected_bin_number = 0
        try:
            selected_bin_index = self.json_db["bins"].index(sort_attribute)
            selected_bin_number = selected_bin_index + 1
            found_bin = True
        except ValueError:
            if(len(self.json_db["bins"]) < self.number_of_bins):
                # there are available bins, add bin assignment
                self.json_db["bins"].append(sort_attribute)
                selected_bin_number = len(self.json_db["bins"])
                selected_bin_index = selected_bin_number - 1
                self._save_db()
                assigned_bin = True
            elif("OPEN" in self.json_db["bins"]):
                selected_bin_index = self.json_db["bins"].index("OPEN")
                selected_bin_number = selected_bin_index + 1
                self.json_db["bins"][selected_bin_index] = sort_attribute
                self._save_db()
                assigned_bin = True
            else:
                # no more available bins
                logger.debug("No more available bins. Moving to DEFAULT bin.")
                selected_bin_number = 1 # must default to DEFAULT
                selected_bin_index = 0
                
        return found_bin, assigned_bin, selected_bin_number, self.json_db["bins"][selected_bin_index]
    
    def move_servos_to_sort_attribute_bin(self, sort_attribute, secondary_sort_attribute="DEFAULT"):
        found_bin, assigned_bin, selected_bin_number, selected_bin_sort_attribute = self.retrieve_or_assign_bin_for_sort_attribute(sort_attribute)
        # if primary sort attribute is not found and cannot be assigned, try using the secondary attribute, if provided
        if(selected_bin_number == 1 and secondary_sort_attribute != "DEFAULT"):
            found_bin, assigned_bin, selected_bin_number, selected_bin_sort_attribute = self.retrieve_or_assign_bin_for_sort_attribute(secondary_sort_attribute)
        actual_bin_number = self.move_servos_directly_to_bin(selected_bin_number)
        return found_bin, assigned_bin, actual_bin_number, self.json_db["bins"][actual_bin_number - 1]
    
    def move_servos_directly_to_bin(self, bin_number):
        # movement logic here
        servo_layer = 1
        servo_layer_handles = self.number_of_servos + 1
        servo_layer_midpoint = servo_layer_handles / 2
        servo_layer_decision_point = servo_layer_midpoint
        layer_servo_index = 0
        for i in range(self.number_of_servos):
            layer_servo_index += 1
            if((bin_number <= (layer_servo_index * servo_layer_handles) and bin_number > ((layer_servo_index - 1) * servo_layer_handles)) or
               self.only_move_necessary_servos == False):                
                work_driver_index, work_servo_index = self._determine_servo_index_values(i + 1) # 0-based indexing

                if(bin_number <= servo_layer_decision_point):
                    logger.debug("driver: %s, servo: %s, angle: %s",
                                 work_driver_index, work_servo_index, self.main_angles[work_driver_index][work_servo_index])
                    self.kit[work_driver_index].servo[work_servo_index].angle = self.main_angles[work_driver_index][work_servo_index]
                else:
                    logger.debug("driver: %s, servo: %s, angle: %s",
                                 work_driver_index, work_servo_index, self.alt_angles[work_driver_index][work_servo_index])
                    self.kit[work_driver_index].servo[work_servo_index].angle = self.alt_angles[work_driver_index][work_servo_index]

                if(self.sleep_duration_between_servo_movements > 0):
                    time.sleep(self.sleep_duration_between_servo_movements)

            servo_layer_decision_point = servo_layer_decision_point + servo_layer_handles
            if(layer_servo_index >= (2 ** (servo_layer - 1))):
                servo_layer += 1
                servo_layer_handles = servo_layer_handles / 2
                servo_layer_midpoint = servo_layer_handles / 2
                servo_layer_decision_point = servo_layer_midpoint
                layer_servo_index = 0

        self._current_bin = bin_number
        return self._current_bin
    
    #properties
    @property
    def current_bin(self):
        return self._current_bin
    
    @property
    def all_bins(self):
        return self.json_db["bins"]

    # special method (string representation of class)
    def __str__(self):
        return f"Sorter {self.sorter_name!r} has {self.number_of_servos} servos and {self.number_of_bins} bins. The currently selected bin is {self._current_bin}."
    
    # special method (unambiguous string representation of class)
    def __repr__(self):
        class_name = type(self).__name__
        return f"{class_name}(sorter_name={self.sorter_name!r}," \
               f" sorter_db_filename={self.sorter_db_filename!r}," \
               f" number_of_servos={self.number_of_servos!r}," \
               f" number_of_bins={self.number_of_bins!r}," \
               f" current_bin={self._current_bin!r}," \
               f" actuation_ranges={self.actuation_ranges!r}," \
               f" main_angles={self.main_angles!r}," \
               f" alt_angles={self.alt_angles!r}," \
               f" only_move_necessary_servos={self.only_move_necessary_servos!r}," \
               f" sleep_duration_between_servo_movements={self.sleep_duration_between_servo_movements!r}," \
               f" driver_count={self._driver_count!r})"

class AddressRangeAngleError(Exception):
    def __init__(self):
        super().__init__("ServoSorter is having trouble with the array values passed as i2c addresses, actuation " \
                         "ranges, main angles, or alt angles. Check your calling program's config files or logic to " \
                         "ensure correct and complete values are being passed in the appropriate format.")
