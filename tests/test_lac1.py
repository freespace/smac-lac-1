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

from lac1 import LAC1
def test_init(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)

    fake = fake_serial['instance']
    assert fake.port == 'COM_TEST'
    assert fake.written[0] == b'EF\r'

def test_sendcmds(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    controller.sendcmds('AA')

    fake = fake_serial['instance']
    assert fake.written[-1] == b'AA\r'

def test_sendcmd_with_arguments(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    controller.sendcmds('AA', 10)

    fake = fake_serial['instance']
    assert fake.written[-1] == b'AA10\r'

def test_sendcmd_with_float_arguments(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    controller.sendcmds('AA', 10.7)

    fake = fake_serial['instance']
    assert fake.written[-1] == b'AA10\r'

def test_sendcmd_multiple(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    controller.sendcmds('AA', '', 'BB', 20)

    fake = fake_serial['instance']
    assert fake.written[-1] == b'AA,BB20\r'

def test_sendcmd_set_home_macro_no_macro(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)

    fake = fake_serial['instance']
    fake.queue_response(b'')

    controller.set_home_macro()

    fake = fake_serial['instance']
    assert fake.written[-8] == b'TM0\r'
    assert fake.written[-7] == b'MF\r'    
    assert fake.written[-6] == b'RM\r'
    assert fake.written[-5] == b'MD100,SG50,SI80,SD600,IL5000,FR1,RI1\r'
    assert fake.written[-4] == b'MD101,VM,MN,SQ29490,SA26214,SV52428,DI1,GO,WA20\r'
    assert fake.written[-3] == b'MD102,RW538,IB-75,NO,MJ105,RP\r'
    assert fake.written[-2] == b'MD105,ST,WS25,PM,MR1000,GO,WS25,DH0,DI0,MF\r'
    assert fake.written[-1] == b'MD0,MC100\r'

def test_sendcmd_set_home_macro_existing_macro(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)

    fake = fake_serial['instance']
    fake.queue_response(b'MD0,MC100')

    controller.set_home_macro()

    fake = fake_serial['instance']
    assert fake.written[-1] == b'TM0\r'

def test_sendcmd_set_home_macro_force(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)

    fake = fake_serial['instance']
    fake.queue_response(b'MD0,MC100')

    controller.set_home_macro(force=True)

    fake = fake_serial['instance']
    assert fake.written[-8] == b'TM0\r'
    assert fake.written[-7] == b'MF\r'    
    assert fake.written[-6] == b'RM\r'
    assert fake.written[-5] == b'MD100,SG50,SI80,SD600,IL5000,FR1,RI1\r'
    assert fake.written[-4] == b'MD101,VM,MN,SQ29490,SA26214,SV52428,DI1,GO,WA20\r'
    assert fake.written[-3] == b'MD102,RW538,IB-75,NO,MJ105,RP\r'
    assert fake.written[-2] == b'MD105,ST,WS25,PM,MR1000,GO,WS25,DH0,DI0,MF\r'
    assert fake.written[-1] == b'MD0,MC100\r'

def test_home(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    controller.home()

    fake = fake_serial['instance']
    assert fake.written[-2] == b'MS100\r'
    assert fake.written[-1] == b'PM,MN,MA0,GO,WS25\r'

def test_go(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    controller.go()

    fake = fake_serial['instance']
    assert fake.written[-1] == b'GO\r'

def test_stop(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    controller.stop()

    fake = fake_serial['instance']
    assert fake.written[-1] == b'ST\r'

def test_abort(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    controller.abort()

    fake = fake_serial['instance']
    assert fake.written[-1] == b'AB\r'

def test_motor_on(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    controller.motor_on()

    fake = fake_serial['instance']
    assert fake.written[-1] == b'MN\r'

def test_motor_off(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    controller.motor_off()

    fake = fake_serial['instance']
    assert fake.written[-1] == b'MF\r'

def test_go_home(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    controller.go_home()

    fake = fake_serial['instance']
    assert fake.written[-1] == b'MN,GH\r'

def test_set_max_velocity_100(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    controller.set_max_velocity(100)

    fake = fake_serial['instance']
    assert fake.written[-1] == b'SV1310720\r'

def test_set_max_velocity_1(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    controller.set_max_velocity(1)

    fake = fake_serial['instance']
    assert fake.written[-1] == b'SV13107\r'

def test_max_acceleration_1000(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    controller.set_max_acceleration(1000)

    fake = fake_serial['instance']
    assert fake.written[-1] == b'SA2621\r'

def test_max_acceleration_1(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    controller.set_max_acceleration(1)

    fake = fake_serial['instance']
    assert fake.written[-1] == b'SA2\r'

def test_max_torque(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    controller.set_max_torque(2000)

    fake = fake_serial['instance']
    assert fake.written[-1] == b'SQ2000\r'

def test_wait_stop(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    controller.wait_stop()

    fake = fake_serial['instance']
    assert fake.written[-1] == b'WS25\r'

def test_move_absolute_enc(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    controller.move_absolute_enc(1000)

    fake = fake_serial['instance']
    assert fake.written[-1] == b'PM,MN,MA1000,GO,WS25\r'

def test_move_absolute_enc_negative(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    with pytest.raises(AssertionError):
        controller.move_absolute_enc(-1000)

def test_move_absolute_enc_too_far(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    with pytest.raises(AssertionError):
        controller.move_absolute_enc(100000000)

def test_move_absolute_enc_no_wait(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    controller.move_absolute_enc(1000, wait=False)

    fake = fake_serial['instance']
    assert fake.written[-1] == b'PM,MN,MA1000,GO\r'

def test_move_absolute_enc_position(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)

    fake = fake_serial['instance']
    fake.queue_response(b'1000\r')

    pos = controller.move_absolute_enc(1000, getposition=True)
    assert fake.written[-1] == b'PM,MN,MA1000,GO,WS25,TP\r'
    assert pos == 1000

def test_move_absolute_mm(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    controller.move_absolute_mm(1)

    fake = fake_serial['instance']
    assert fake.written[-1] == b'PM,MN,MA1000,GO,WS25\r'

def test_move_absolute_um(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)

    fake = fake_serial['instance']
    fake.queue_response(b'1000\r')

    pos = controller.move_absolute_um(1000, getposition=True)
    assert fake.written[-1] == b'PM,MN,MA1000,GO,WS25,TP\r'
    assert pos == 1000

def test_move_relative_enc(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    controller.move_relative_enc(5000)

    fake = fake_serial['instance']
    assert fake.written[-2] == b'PM,MN,MR5000,GO\r'
    assert fake.written[-1] == b'WS25\r'

def test_move_relative_mm(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    controller.move_relative_mm(5)

    fake = fake_serial['instance']
    assert fake.written[-2] == b'PM,MN,MR5000,GO\r'
    assert fake.written[-1] == b'WS25\r'

def test_get_error(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)

    fake = fake_serial['instance']
    fake.queue_response(b'5\r')

    err = controller.get_error()
    assert fake.written[-1] == b'TE\r'
    assert err == '5'

def test_get_position_enc(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)

    fake = fake_serial['instance']
    fake.queue_response(b'1000\r')
    pos = controller.get_position_enc()
    assert pos == 1000

def test_get_position_mm(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)

    fake = fake_serial['instance']
    fake.queue_response(b'1000\r')
    pos = controller.get_position_mm()
    assert pos == 1

def test_get_position_um(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)

    fake = fake_serial['instance']
    fake.queue_response(b'1000\r')
    pos = controller.get_position_um()
    assert pos == 1000

def test_get_params(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)

    fake = fake_serial['instance']
    fake.queue_response(b'Version XXX\r')

    param = controller.get_params(10)
    assert fake.written[-1] == b'TK10\r'
    assert param[0] == 'Version XXX'

def test_close(fake_serial):
    controller = LAC1(port='COM_TEST', baudRate=9600)
    controller.close()

    fake = fake_serial['instance']
    assert fake.written[-3] == b'\033'
    assert fake.written[-2] == b'\033'
    assert fake.written[-1] == b'AB,MF,EN\r'

    assert fake.is_open == False

