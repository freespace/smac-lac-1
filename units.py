from typing import Union
from warnings import warn

from pint import UnitRegistry, Quantity

ureg = UnitRegistry()

def has_units(value: Union[int, float, str, Quantity]) -> bool:
  return isinstance(value, Quantity)

def set_units(value: Union[int, float], units: str) -> Quantity:
  """
  Sets the units of the value using Pint. Does not provide any checking.
  """
  return value * ureg(units)

def ensure_units(value: Union[int, float, str, Quantity], defaultUnits: str) -> Quantity:
  """
  Checkes that the value provided matches the type of the default units. This 
  value can be submitted as a Pint quanity, a number, or a string. 
  If no unit is provide provides a warning and assigns the defualt unit.
  Raises an error if the wrong type of unit is assigned.
  """
  if not isinstance(value, Quantity):
    match value:
        case int() | float():
            response = value * ureg('dimensionless')
        case str():
            response = 1 * ureg(value)
        case _:
            raise TypeError('Unsupported type')
  else:
     response = value

  if (response.check(defaultUnits)):
     return response.to(defaultUnits)
  else:
    if(len(response.dimensionality) == 0):
      # number is dimensionless
      warn(f'No units assigned, assumed value of {value}, has units of {defaultUnits}')
      response = float(value) * ureg(defaultUnits)
      return response.to(defaultUnits)
    else:
      # unit has the wrong dimensionality (i.e current when expecting distance)
      raise TypeError(f'{value} is using the wrong type of units, expected {defaultUnits}')
