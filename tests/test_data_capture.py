import pytest
from .fakes import FakeSerial
from smac_python.units import ensure_units, has_units

@pytest.fixture
def fake_serial(monkeypatch):
    import smac_python.lac1 as lac1

    container = {'instance': None}

    def factory(*args, **kwargs):
        fake = FakeSerial(*args, **kwargs)
        container['instance'] = fake
        return fake

    monkeypatch.setattr(
        lac1.serial,
        "Serial",
        factory

    )
    return container

from smac_python.lac1 import LAC1, Actuator
def test_setup_data_capture(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    controller.setup_data_capture()

    fake = fake_serial['instance']
    assert fake.written[-5] == b'CS5000\r'
    assert fake.written[-4] == b'AL5,WW422\r'
    assert fake.written[-3] == b'AL1,WW1600\r'
    assert fake.written[-2] == b'AL494,WW1602\r'
    assert fake.written[-1] == b'AL0,WW1604\r'

def test_setup_data_capture_two_variables(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    controller.setup_data_capture(time='20 s', rate='100/s', variables=['current', 'position'])

    fake = fake_serial['instance']
    assert fake.written[-7] == b'CS4000\r'
    assert fake.written[-6] == b'AL50,WW422\r'
    assert fake.written[-5] == b'AL2,WW1600\r'
    assert fake.written[-4] == b'AL548,WW1602\r'
    assert fake.written[-3] == b'AL2,WW1604\r'
    assert fake.written[-2] == b'AL494,WW1606\r'
    assert fake.written[-1] == b'AL0,WW1608\r'

def test_setup_data_capture_to_many(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    with pytest.raises(ValueError):
        controller.setup_data_capture(variables = ['position', 'position', 'position', 'position', 'position'])

def test_capture_data(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)

    data = controller.setup_data_capture(time='20 s', rate='100/s', variables=['current', 'position'])
    data.capture()

    fake = fake_serial['instance']
    assert fake.written[-1] == b'CD4000\r'

def test_raw_data(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)

    data = controller.setup_data_capture(time='20 s', rate='100/s', variables=['current', 'position'])
    data.capture()
    data.raw()

    fake = fake_serial['instance']
    assert fake.written[-1] == b'DD4000\r'

def test_raw_data_response(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)

    fake = fake_serial['instance']

    data = controller.setup_data_capture(time='5 s', rate='1/s', variables=['current', 'position'])
    data.capture()

    fake.queue_response(b'100,200\r')
    fake.queue_response(b'101,201\r')
    fake.queue_response(b'102,202\r')
    fake.queue_response(b'103,203\r')
    fake.queue_response(b'104,204\r')

    response = data.raw()
    print(response)

    assert fake.written[-1] == b'DD10\r'
    assert len(response) == 2
    assert len(response['current']) == 5
    assert len(response['position']) == 5
    assert response['current'][2] == 102
    assert response['position'][3] == 203

def test_data_response(fake_serial):
    actuator = Actuator(
        enc_counts_per_mm='100.0 counts/mm',
        stage_travel_mm='100.0 mm',
        SG=10,
        SI=4,
        SD=100,
        IL=15000
    )

    controller = LAC1(port='COM_TEST', baudRate=9600, actuator=actuator)

    fake = fake_serial['instance']

    data = controller.setup_data_capture(time='5 s', rate='1/s', variables=['current', 'position'])
    data.capture()

    fake.queue_response(b'100,200\r')
    fake.queue_response(b'101,201\r')
    fake.queue_response(b'102,202\r')
    fake.queue_response(b'103,203\r')
    fake.queue_response(b'104,204\r')

    response = data.data()
    print(response)

    assert fake.written[-1] == b'DD10\r'
    assert len(response) == 2
    assert len(response['current']) == 5
    assert len(response['position']) == 5
    assert response['current'].check('A') == True
    assert response['position'].check('mm') == True    

def test_data_response_current(fake_serial):
    actuator = Actuator(
        enc_counts_per_mm='1000.0 counts/mm',
        stage_travel_mm='100.0 mm',
        SG=10,
        SI=4,
        SD=100,
        IL=15000
    )

    controller = LAC1(port='COM_TEST', baudRate=9600, actuator=actuator)

    fake = fake_serial['instance']

    data = controller.setup_data_capture(time='5 s', rate='1/s', variables=['current'])
    data.capture()

    fake.queue_response(b'176\r')
    fake.queue_response(b'265\r')
    fake.queue_response(b'530\r')
    fake.queue_response(b'883\r')
    fake.queue_response(b'1766\r')

    response = data.data()
    print(response)

    assert response['current'].check('A') == True
    assert response['current'].magnitude == pytest.approx([1, 1.5, 3, 5, 10], rel=0.01)

def test_data_response_position(fake_serial):
    actuator = Actuator(
        enc_counts_per_mm='1000.0 counts/mm',
        stage_travel_mm='100.0 mm',
        SG=10,
        SI=4,
        SD=100,
        IL=15000
    )

    controller = LAC1(port='COM_TEST', baudRate=9600, actuator=actuator)

    fake = fake_serial['instance']

    data = controller.setup_data_capture(time='5 s', rate='1/s', variables=['position'])
    data.capture()

    fake.queue_response(b'1000\r')
    fake.queue_response(b'2000\r')
    fake.queue_response(b'5000\r')
    fake.queue_response(b'10010\r')
    fake.queue_response(b'95000\r')

    response = data.data()
    print(response)

    assert response['position'].check('mm') == True
    assert response['position'].magnitude == pytest.approx([1, 2, 5, 10.01, 95], rel=0.01)

def test_data_response_error(fake_serial):
    actuator = Actuator(
        enc_counts_per_mm='1000.0 counts/mm',
        stage_travel_mm='100.0 mm',
        SG=10,
        SI=4,
        SD=100,
        IL=15000
    )

    controller = LAC1(port='COM_TEST', baudRate=9600, actuator=actuator)

    fake = fake_serial['instance']

    data = controller.setup_data_capture(time='5 s', rate='1/s', variables=['error'])
    data.capture()

    fake.queue_response(b'1000\r')
    fake.queue_response(b'2000\r')
    fake.queue_response(b'5000\r')
    fake.queue_response(b'10010\r')
    fake.queue_response(b'95000\r')

    response = data.data()
    print(response)

    assert response['error'].check('mm') == True
    assert response['error'].magnitude == pytest.approx([1, 2, 5, 10.01, 95], rel=0.01)

def test_data_response_rclock(fake_serial):
    actuator = Actuator(
        enc_counts_per_mm='1000.0 counts/mm',
        stage_travel_mm='100.0 mm',
        SG=10,
        SI=4,
        SD=100,
        IL=15000
    )

    controller = LAC1(port='COM_TEST', baudRate=9600, actuator=actuator)

    fake = fake_serial['instance']

    data = controller.setup_data_capture(time='5 s', rate='1/s', variables=['rclock'])
    data.capture()

    fake.queue_response(b'1000\r')
    fake.queue_response(b'2000\r')
    fake.queue_response(b'3000\r')
    fake.queue_response(b'4000\r')
    fake.queue_response(b'5000\r')

    response = data.data()
    print(response)

    assert response['rclock'].check('s') == True
    assert (response['rclock'].to('s').magnitude == [1, 2, 3, 4, 5]).all()

def test_data_response_sclock(fake_serial):
    actuator = Actuator(
        enc_counts_per_mm='1000.0 counts/mm',
        stage_travel_mm='100.0 mm',
        SG=10,
        SI=4,
        SD=100,
        IL=15000
    )

    controller = LAC1(port='COM_TEST', baudRate=9600, actuator=actuator)

    fake = fake_serial['instance']

    data = controller.setup_data_capture(time='5 s', rate='1/s', variables=['sclock'])
    data.capture()

    fake.queue_response(b'5000\r')
    fake.queue_response(b'10000\r')
    fake.queue_response(b'15000\r')
    fake.queue_response(b'20000\r')
    fake.queue_response(b'25000\r')

    response = data.data()
    print(response)

    assert response['sclock'].check('s') == True
    assert (response['sclock'].to('s').magnitude == [1, 2, 3, 4, 5]).all()