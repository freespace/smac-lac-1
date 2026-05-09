import numpy as np
from typing import Union

from .units import ensure_units, set_units, Quantity

class Data(object):
    def __init__(self, controller, time: Union[int, float, str, Quantity], rate: Union[int, float, str, Quantity], variables: list[str], units: list[str] | None = None):
        if not variables:
            raise ValueError('At least one variable must be defined')
        num = len(variables)

        if num > 4:
            raise ValueError('Data Capture is limited to 4 variables')

        if units is None:
            units = [''] * num
        elif num != len(units):
            raise ValueError('Number of variables and number of units must be the same')

        time = ensure_units(time, 's')
        rate = ensure_units(rate, '1/s')
   
        self._controller = controller
        self._samples = (time * rate).magnitude
        self._memorySpace = self._samples * num
        self._variables = variables
        self._units = []
    
        self._controller.sendcmds('CS', self._memorySpace)
        self._controller.write_word((self._controller.servo_loop_frequency / rate).magnitude, 422)
        self._controller.write_word(num, 1600)

        for idx, variable in enumerate(self._variables):
            match variable:
                case 'position':
                    word = 494
                    size = 0
                    unit = units[idx] or 'mm'
                case 'error':
                    word = 538
                    size = 2
                    unit = units[idx] or 'mm'
                case 'current':
                    word = 548
                    size = 2
                    unit = units[idx] or 'A'
                case 'sclock':
                    word = 1826
                    size = 0
                    unit = units[idx] or 'ms'
                case 'rclock':
                    word = 1830
                    size = 0
                    unit = units[idx] or 'ms'
                case _:
                    raise ValueError(f'Incorrect variable name: {variable}')
            self._controller.write_word(word, 1602 + 4*idx)
            self._controller.write_word(size, 1604 + 4*idx)
            self._units.append(unit)

    def capture(self):
        self._controller.sendcmds('CD', self._memorySpace)

    def raw(self):
        raw_data = {name: [] for name in self._variables}

        def log(line):
            for name, val in zip(self._variables, line.split(',')):
                raw_data[name].append(int(val))

        self._controller.sendcmds('DD', self._memorySpace, wait=True, callback=log)
        return {name: np.array(vals) for name, vals in raw_data.items()}

    def data(self):
        raw_data = self.raw()

        response = {}

        for idx, variable in enumerate(self._variables):
            match variable:
                case 'position' | 'error':
                    raw_data[variable] = set_units(raw_data[variable], 'counts') / self._controller.actuator.enc_counts_per_mm
                case 'current':
                    raw_data[variable] = raw_data[variable] * set_units(11.585, 'A')  / 2047
                case 'sclock':
                    raw_data[variable] = raw_data[variable] / self._controller.servo_loop_frequency
                case 'rclock':
                    raw_data[variable] = set_units(raw_data[variable], 'ms')
            response[variable] = ensure_units(raw_data[variable], self._units[idx])
        return response