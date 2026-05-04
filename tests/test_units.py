import pytest

from units import Q_, ensure_units, has_units

def test_has_units_true():
    assert has_units(Q_('10 mm')) == True

def test_has_units_false():
    assert has_units(10) == False

def test_ensure_units_quantity():
    value = ensure_units(Q_('10 mm'), 'mm')
    assert value == Q_('10 mm') 

def test_ensure_units_int():
    with pytest.warns(UserWarning, match='No units assigned, assumed value of 10, has units of mm'):
        value = ensure_units(10, 'mm')
        assert value == Q_('10 mm')

def test_ensure_units_float():
    with pytest.warns(UserWarning, match='No units assigned, assumed value of 10.0, has units of mm'):
        value = ensure_units(10.0, 'mm')
        assert value == Q_('10 mm')

def test_ensure_units_string():
    value = ensure_units('10 mm', 'mm')
    assert value == Q_('10 mm')  

def test_ensure_units_string_without_units():
    with pytest.warns(UserWarning, match='No units assigned, assumed value of 10, has units of mm'):
        value = ensure_units('10', 'mm')
        assert value == Q_('10 mm')

def test_ensure_units_m():
    value = ensure_units('0.01 m', 'mm')
    assert value == Q_('10 mm')

def test_ensure_units_A():
    with pytest.raises(TypeError) as err:
        ensure_units('10 A', 'mm')
    assert '10 A is using the wrong type of units, expected mm' in str(err.value)