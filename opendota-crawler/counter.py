import atexit
import os

import logger

def counter_at_exit(counter):
    with open(counter.path, 'w') as counter_file:
        counter.logger.info("Storing counter ({}) in file: {}".format(counter.count,
                                                                  counter.path))
        counter_file.write(str(counter.count))

class Counter:
    def __init__(self, counter_path="counter.txt", logger=logger.create_logger(__name__)):
        self.path = counter_path
        self.logger = logger

        if os.path.exists(self.path):
            with open(self.path, 'r') as counter_file:
                self.count = int(counter_file.read())
                self.logger.info("Loaded counter ({}) from file: {}".format(self.count,
                                                                           self.path))
        else:
            self.count = 0
            self.logger.info("Initialized counter for file: {}".format(self.path))

        atexit.register(counter_at_exit, self)

    def increment(self):
        self.count += 1
        self.logger.debug("{}: {}".format(self.path, self.count))
