import pytest
from fakes import FakeSerial

@pytest.fixture
def fake_serial(monkeypatch):
    import lac1

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

@pytest.fixture
def actuator():
    from lac1 import Actuator
    actuator = Actuator(
        enc_counts_per_mm=1000.0,
        stage_travel_mm=100.0,
        SG=10,
        SI=4,
        SD=100,
        IL=15000
    )

    return actuator

@pytest.fixture
def high_res_actuator():
    from lac1 import Actuator
    actuator = Actuator(
        enc_counts_per_mm=5000.0,
        stage_travel_mm=100.0,
        SG=10,
        SI=4,
        SD=100,
        IL=15000
    )

    return actuator

from lac1 import LAC1

# Unit tests to confrim properties from customer actuator are being used

def test_init(fake_serial, actuator):
    controller = LAC1(port='COM_TEST', baudRate=9600, actuator=actuator)

    fake = fake_serial['instance']
    assert fake.port == 'COM_TEST'
    assert fake.written[0] == b'EF\r'
    assert fake.written[1] == b'SG10,SI4,SD100,IL15000,SE16383,RI1,FR1\r'

def test_sendcmd_set_home_macro_no_macro(fake_serial, actuator):
    controller = LAC1(port='COM_TEST', baudRate=9600, actuator=actuator)

    fake = fake_serial['instance']
    fake.queue_response(b'')

    controller.set_home_macro()

    fake = fake_serial['instance']
    assert fake.written[-8] == b'TM0\r'
    assert fake.written[-7] == b'MF\r'    
    assert fake.written[-6] == b'RM\r'
    assert fake.written[-5] == b'MD100,SG10,SI4,SD100,IL15000,FR1,RI1\r'
    assert fake.written[-4] == b'MD101,VM,MN,SQ29490,SA26214,SV52428,DI1,GO,WA20\r'
    assert fake.written[-3] == b'MD102,RW538,IB-75,NO,MJ105,RP\r'
    assert fake.written[-2] == b'MD105,ST,WS25,PM,MR1000,GO,WS25,DH0,DI0,MF\r'
    assert fake.written[-1] == b'MD0,MC100\r'

def test_move_absolute_mm(fake_serial, high_res_actuator):
    controller = LAC1(port='COM_TEST', baudRate=9600, actuator=high_res_actuator)
    controller.move_absolute_mm(1)

    fake = fake_serial['instance']
    assert fake.written[-1] == b'PM,MN,MA5000,GO,WS25\r'