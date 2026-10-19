from enum import Enum

import numpy as np
from typing import Union

from .units import ensure_units, set_units, Quantity

# from User Manual section Internal Variables
class DataVariable(Enum):
    POSITION = (494,0,'mm')     # Curp LONG 01EEH/0494 
    ERROR = (538,2,'mm')        # PERR WORD 021AH/0538 
    CURRENT = (548,2,'A')       # IMON WORD 0224H/0548 
    SCLOCK = (1826,0,'ms')      # SCLOCK LONG 0722H/1826 
    RCLOCK = (1830,0,'ms')      # RCLOCK LONG 0726H/1830 

    def __str__(self):
            return self.name.lower()

    def __init__(self, address, size, unit):
        self.address = address
        self.size = size
        self.unit = unit

class DataCapture(object):
    def __init__(self, controller, time: Union[int, float, str, Quantity], rate: Union[int, float, str, Quantity], variables: list[DataVariable], units: list[str] | None = None):
        if not variables:
            raise ValueError('At least one variable must be defined')
        self._num = len(variables)

        if self._num > 4:
            raise ValueError('Data Capture is limited to 4 variables')

        if units is None:
            units = [''] * self._num
        elif self._num != len(units):
            raise ValueError('Number of variables and number of units must be the same')

        time = ensure_units(time, 's')
        self._rate = ensure_units(rate, '1/s')
   
        self._controller = controller
        # Round up number of samples to ensure enough allocation
        self._samples = int(np.ceil((time * self._rate).magnitude))
        self._memorySpace = self._samples * self._num
        self._variables = variables
        self._units = []
    
        self._controller.sendcmds('CS', self._memorySpace)
        self._controller.write_word((self._controller.servo_loop_frequency / self._rate).magnitude, 422)
        self._controller.write_word(self._num, 1600)

        for idx, data_variable in enumerate(self._variables):
            if not data_variable:
                raise ValueError(f'Incorrect variable name: {data_variable}')
            
            self._controller.write_word(data_variable.address, 1602 + 4*idx)
            self._controller.write_word(data_variable.size, 1604 + 4*idx)
            self._units.append(units[idx] or data_variable.unit)

    def capture(self):
        self._controller.sendcmds('CD', self._memorySpace)

    def raw(self, time: Union[int, float, str, Quantity, None] = None):
        if(time is None):
            memory = self._memorySpace
        else:
            time = ensure_units(time, 's')
            memory = int(np.ceil((time * self._rate).magnitude)) * self._num
        
        raw_data = {str(variable): [] for variable in self._variables}

        def log(line):
            for variable, val in zip(self._variables, line.split(',')):
                raw_data[str(variable)].append(int(val))

        self._controller.sendcmds('DD', memory, wait=True, callback=log)
        return {name: np.array(vals) for name, vals in raw_data.items()}

    def data(self, time: Union[int, float, str, Quantity, None] = None):

        raw_data = self.raw(time)

        response = {}

        for idx, variable in enumerate(self._variables):
            match variable:
                case DataVariable.POSITION | DataVariable.ERROR:
                    raw_data[str(variable)] = set_units(raw_data[str(variable)], 'counts') / self._controller.actuator.enc_counts_per_mm
                case DataVariable.CURRENT:
                    raw_data[str(variable)] = raw_data[str(variable)] * set_units(11.585, 'A')  / 2047
                case DataVariable.SCLOCK:
                    raw_data[str(variable)] = raw_data[str(variable)] / self._controller.servo_loop_frequency
                case DataVariable.RCLOCK:
                    raw_data[str(variable)] = set_units(raw_data[str(variable)], 'ms')
            response[str(variable)] = ensure_units(raw_data[str(variable)], self._units[idx])
        return response