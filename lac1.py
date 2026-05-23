#!/usr/bin/env python
import serial
import time
from dataclasses import dataclass, field, astuple
from units import set_units, ensure_units

# it is important to make these floats to avoid integer truncation error
ENC_COUNTS_PER_MM = '1000.0 counts/mm'  # default encoder counts per mm
SERVO_LOOP_FREQ = '5000.0 1/s'    # servo loop frequency

# This is specific to the stage I am using
# TODO Implement range checking for safety?
STAGE_TRAVEL_MM = '25 mm'

# we will not allow travel beyond TRAVEL_SAFETY_FACTOR * STAGE_TRAVEL_ENC
TRAVEL_SAFETY_FACTOR = 1.0

# These parameters are dependent on the stage. See SMAC Actuators Users Manual
SG = 50
SI = 80
SD = 600
IL = 5000
SE = 16383
RI = 1
FR = 1

# Time parameter to WS commands. Unit is ms
WS_PERIOD_MS = 25

# LAC-1 manual recommends a small delay of 100 ms after sending commands
SERIAL_SEND_WAIT_SEC = 0.100

# Each line cannot exceed 127 characters as per LAC-1 manual
SERIAL_MAX_LINE_LENGTH = 127

@dataclass
class Actuator(object):
  """
  Class to define parameters are dependent on the stage.
  """
  enc_counts_per_mm: float = ENC_COUNTS_PER_MM
  stage_travel_mm: int = STAGE_TRAVEL_MM
  SG:int = SG
  SI:int = SI
  SD:int = SD
  IL:int = IL
  SE:int = SE
  RI:int = RI
  FR:int = FR
  stage_travel_enc: float = field(init=False)

  def __post_init__(self):
    self.stage_travel_mm = ensure_units(self.stage_travel_mm, 'mm')
    self.enc_counts_per_mm = ensure_units(self.enc_counts_per_mm, 'counts / mm')

class LAC1(object):
  """
  Class to interface with a SMAC LAC-1 module.

  SMAC serial interface accepts instructions in the format of:

    <command>[<argument>] <CR>

  Or

    <command>[<argument>],<command>[<argument>],... <CR>

  e.g.

    SG1000,SD5000 <CR>

  Note that EF is sent as the first command to LAC-1 on initialisation, and
  EN is sent as the last command on close. This simplifies parsing of outputs.

  Note that for each cmmand sent, with EF in force, LAC-1 will output

     '\r\n>'

  When it is ready for the next command
  """

  """
  When set to False, commands that are sent to LAC-1 is printed to stdout.
  Defaults to True.
  """
  _silent = True

  _port = None

  _ESC = '\033'

  _sleepfunc = time.sleep

  _last_serial_send_time = None

  def __init__(self, port, baudRate, actuator=None, silent=True, reset=True, sleepfunc=None):
    """
    If silent is True, then no debugging output will be printed. Default is
    True.

    If sleepfunc is not None, then it will be used instead of time.sleep.
    It will be passed the number of seconds to sleep for. This is provided
    for integration with single threaded GUI applications.
    """

    self.servo_loop_frequency = ensure_units(SERVO_LOOP_FREQ, '1/s')

    if sleepfunc is not None:
      self._sleepfunc = sleepfunc

    if actuator is None:
      actuator = Actuator()

    self.actuator = actuator

    # KV and KA defined the change in encoder per servo loop needed to achieve
    # 1 mm/s velocity and 1 mm/s/s acceleration, respectively.
    self.KV = ensure_units(65536 * self.actuator.enc_counts_per_mm / self.servo_loop_frequency, 'counts/(mm/s)')
    self.KA = ensure_units(65536 * self.actuator.enc_counts_per_mm / (self.servo_loop_frequency**2), 'counts/(mm/s**2)')

    print('Connecting to controller on %s (%s)'%(port, baudRate))
    self._port = serial.Serial(
        port = port,
        baudrate = baudRate,
        bytesize = 8,
        stopbits = 1,
        parity = 'N',
        timeout = 0.1)

    self._silent = silent

    self.sendcmds('EF', wait=False)

    # setup some initial parameters
    self.sendcmds(
        'SG', self.actuator.SG,
        'SI', self.actuator.SI,
        'SD', self.actuator.SD,
        'IL', self.actuator.IL,
        'SE', self.actuator.SE,
        'RI', self.actuator.RI,
        'FR', self.actuator.FR)

    # these are pretty safe values
    self.set_max_velocity('1 mm/s')
    self.set_max_acceleration('1 mm/s**2')

  def _readline(self, stop_on_prompt=True):
    """
    Returns a line, that is reads until \r. Note that there are some commands
    that will suppress the \r, so becareful if you use those commands and
    this method.

    If stop_on_prompt is True, and it is by default, then if we will stop
    when we consume '>', returning whatever we have read so far as a line,
    including the '>'.

    OK, so you are probably wondering why I wrote this. Why not just use
    self._port.readline()?

    I am glad you asked.

    With python < 2.6, pySerial uses serial.FileLike, that provides a readline
    that accepts the max number of chars to read, and the end of line
    character.

    With python >= 2.6, pySerial uses io.RawIOBase, whose readline only
    accepts the max number of chars to read. io.RawIOBase does support the
    idea of a end of line character, but it is an attribute on the instance,
    which makes sense... except pySerial doesn't pass the newline= keyword
    argument along to the underlying class, and so you can't actually change
    it.
    """
    #print 'reading line',
    # XXX The loop below implicitly handles timeouts b/c when c == '' due to
    # timeout, line += '' is a null op, and the loops continues indefinitely
    # until exitconditions are met

    done = False
    line = str()
    allowedtimeouts = int(30/self._port.timeout)

    while not done:
      c = self._port.read().decode('utf-8')
      if c == '\n':
        continue
      elif c == '\r':
        done = True
      elif c == '':
        allowedtimeouts -= 1
        if allowedtimeouts == 0:
          raise Exception('Read Timed Out')
      else:
        line += c
        if stop_on_prompt and c == '>':
          done = True

    if len(line) and line[0] == '?':
      raise Exception('LAC-1 Error: '+line[1:])

    if not self._silent:
      print('[>]',line)
    return line

  def sendcmds(self, *args, **kwargs):
    """
    This method sends the given commands and argument to LAC-1. Commands are
    expected in the order of

      cmd arg cmd arg

    And will be sent as:

      $cmd$arg,$cmd,$arg<CR>

    If a command takes no argument, then put None or ''.

    Arguments will be put through str, and no error checking is done.
    Exception to this is if argument is a float, in which case it will be cast
    to an int.

    Supported keyword arguments:

    wait
    ----
    If wait is True, then after sending each command, the serial stream
    is consumed until '>' is encountered. This is because SMAC emits '>' when
    it is ready for another command. Any lines seen before encountering '>'
    and is not empty will be returned. wait is True by default

    callback
    --------
    If callback is not None, and wait is True, then after reading
    each line from the LAC-1, the callback will be invoked with the contents
    of the line.

    LAC-1 Commands
    ==============
    AL = accumulator load
    AR = copy accumulator to register
    EF = echo off
    EN = echo on
    GO = go, starts motion. Commands like MA doesn't actually make it move.
    MC = macro call
    MA = move absolute
    """
    # XXX enforce SERIAL_SEND_WAIT_SEC
    if self._port is None:
      return

    now = time.time()
    if self._last_serial_send_time is not None:
      dt = now - self._last_serial_send_time
      timeleft = SERIAL_SEND_WAIT_SEC - dt
      if timeleft > 0:
        self._sleepfunc(timeleft)

    if len(args) == 1:
      cmds = [args[0]]
    else:
      assert(len(args)%2 == 0)

      args = list(args)
      cmds = []
      while len(args):
        cmd = args.pop(0)
        arg = args.pop(0)

        if arg is not None:
          if type(arg) is float:
            arg = int(arg)
          arg = str(arg)
        else:
          arg = ''

        cmds.append(cmd+arg)

    tosend = ','.join(cmds)

    if not self._silent:
      print('[<]',tosend)

    self._port.flushInput()
    self._port.flushOutput()

    assert len(tosend) <= SERIAL_MAX_LINE_LENGTH, 'Command exceeds allowed line length'

    self._port.write(str.encode(tosend+'\r'))

    wait = kwargs.get('wait', True)
    callbackfunc = kwargs.get('callback', None)


    datalines = []

    if wait:
      done = False
      while not done and self._port is not None:
        #print 'sendcmds, reading'
        line = self._readline()
        #print 'sendcmds:',line
        if line == '>':
          done = True
        elif line is not None and len(line):
          if callbackfunc is not None:
            callbackfunc(line)
          datalines.append(line)

      # If we have more than one line, then ignore the first which is repeat
      # of what we sent due to echo been on by default.
      # XXX I don't try to disable echo because I can't seem to turn it off
      # reliably.
      if len(datalines) == 1:
        return datalines
      else:
        return datalines[1:]
    else:
      # we update _last_serial_send_time only if we are not
      # waiting for a response
      self._last_serial_send_time = now 
      return None

  def set_home_macro(self, force=False, duty=0.9, velocity='4 mm/s', acceleration='10000 mm/s**2'):
    """
    This function defines a homing macros on macros 100,101,102, and 105. It
    will also inserts a call to macro 100 in macro 0. This means this routine
    will be executed on start.

    In order for the home() function to work, this function must have been
    called previously, or the homing macro has been defined at macro 100
    previously.

    Note that macros persist between power cycles - there is no need to
    call this every time.

    This function does nothing if TM0 returns a non-zero length string, unless
    force is True.
    """

    velocity = ensure_units(velocity, 'mm / s' )
    acceleration = ensure_units(acceleration, 'mm / s**2')

    SG = self.actuator.SG
    SI = self.actuator.SI
    SD = self.actuator.SD
    IL = self.actuator.IL
    RI = self.actuator.RI
    FR = self.actuator.FR

    macro0 = self.sendcmds('TM0')
    if len(macro0) == 0 or force:
      # need motor to be off before messing with macros
      self.motor_off()

      # reset ALL macros
      self.sendcmds('RM')

      # we insert this here because we are executed on startup, and there
      # will be no PID parameters set.
      #
      # MD: define macro
      # SG: proportional param
      # SI: integral param
      # SD: derivative param
      # IL: integral limit
      # FR: derivative sampling frequency
      # RI: sampling rate of integral
      self.sendcmds(f'MD100,SG{SG},SI{SI},SD{SD},IL{IL},FR{FR},RI{RI}')

      # go into velocity mode, turn motor on, set force, acceleration and
      # velocity constants, set direction to be in the direction of DECREASING
      # encoder count, start motion, wait 20ms.
      #
      # MD: define macro
      # VM: velocity mode
      # MN: motor on
      # SQ: torque
      # SA: acceleration
      # SV: velocity
      # DI: direction
      # GO: begin movement
      # WA: wait
      SQ = int(duty * 32767)
      print('SQ:', SQ)
      SA = int((self.KA * acceleration).to('counts').magnitude)
      print('SA:', SA)
      SV = int((self.KV * velocity).to('counts').magnitude)
      print('SV:', SV)
      self.sendcmds(f'MD101,VM,MN,SQ{SQ},SA{SA},SV{SV},DI1,GO,WA20')

      # read word from memory 538, which is position error. If position error
      # is greater than 75, jump to macro 105, otherwise repeat.
      # Note that IB will execute the next 2 commands if true, so we insert
      # a NOP in the form of NO to pad it out.
      #
      # MD: define macro
      # RW: read word from memory 538, where position error is stored
      # IB: if below
      # NO: nop
      # MJ: jump to macro
      # RP: repeat
      self.sendcmds('MD102,RW538,IB-75,NO,MJ105,RP')

      # if we are here, then we have found the limit. Now forward 1000 enconder
      # counts and define home there. Finally we turn the motor off because it
      # seems reasonable to me do do this, but of course if the axis
      # naturally falls due to gravity this could be a bad idea.
      #
      # MD: define macro
      # ST: stop
      # WS: wait stop
      # PM: position mode
      # MR: move relative
      # GO: start motion
      # WS: wait stop
      # DH: define home
      # DI: direction
      # MF: motor off
      self.sendcmds('MD105,ST,WS25,PM,MR1000,GO,WS25,DH0,DI0,MF')

      # MD: define macro
      # MC: call macro
      self.sendcmds('MD0,MC100')

  def home(self, wait=True):
    """
    Performs the homing process, and leaves the stage at 0.0. Note that this
    also modifies velocity, acceleration and torque parameters.
    """
    self.sendcmds('MS100')

    # we do this because otherwise the stage, for some reason, sometimes ends
    # up moving backwards to effectively -1000.
    self.move_absolute('0 mm', wait=wait)

  def go(self):
    self.sendcmds('GO')

  def stop(self):
    self.sendcmds('ST')

  def abort(self, **kwargs):
    self.sendcmds('AB', **kwargs)

  def motor_on(self, **kwargs):
    self.sendcmds('MN', **kwargs)

  def motor_off(self, **kwargs):
    self.sendcmds('MF', **kwargs)

  def go_home(self):
    """
    This differs from home in that it doesn't block and uses GH instead
    of calling the home macro
    """
    self.sendcmds('MN','','GH', '')

  def set_max_velocity(self, velocity):
    velocity = ensure_units(velocity, 'mm / s' )
    SV = int((self.KV * velocity).to('counts').magnitude)
    self.sendcmds('SV', SV)

  def set_max_acceleration(self, acceleration):
    acceleration = ensure_units(acceleration, 'mm / s**2')
    SA = int((self.KA * acceleration).to('counts').magnitude)
    self.sendcmds('SA', SA)

  def set_max_torque(self, q):
    """
    I don't know what units this is in, the instructions don't say
    so it just do it via trial and error
    """
    self.sendcmds('SQ',q)

  def wait_stop(self):
    self.sendcmds('WS', WS_PERIOD_MS)

  def wait(self, interval_ms):
    interval_ms = ensure_units(interval_ms, 'ms')
    self.sendcmds('WA', interval_ms.magnitude)

  def move_absolute_enc(self, pos_enc, wait=True, getposition=False):
    """
    Move to a position specified in encoder counts
    """
    pos_enc = ensure_units(pos_enc, 'counts')

    assert pos_enc <= self.actuator.stage_travel_mm * self.actuator.enc_counts_per_mm * TRAVEL_SAFETY_FACTOR
    assert pos_enc >= 0

    cmds = ['PM', '', 'MN', '', 'MA', int(pos_enc.magnitude),'GO','']
    if wait:
      cmds += ['WS', WS_PERIOD_MS]

      if getposition:
        cmds += ['TP', '']

    ret = self.sendcmds(*cmds)

    if wait and getposition:
      return set_units(int(ret[0]), 'counts')

  def move_absolute_mm(self, pos_mm, **kwargs):
    pos_mm = ensure_units(pos_mm, 'mm')
 
    ret = self.move_absolute_enc(pos_mm * self.actuator.enc_counts_per_mm, **kwargs)
    if ret is not None:
      return (ensure_units(ret, 'counts') / self.actuator.enc_counts_per_mm).to('mm').magnitude
    
  def move_absolute_um(self, pos_um, **kwargs):
    pos_um = ensure_units(pos_um, 'um')

    ret = self.move_absolute_enc(pos_um * self.actuator.enc_counts_per_mm, **kwargs)
    if ret is not None:
      return (ensure_units(ret, 'counts') / self.actuator.enc_counts_per_mm).to('um').magnitude

  def move_absolute(self, pos, **kwargs):
    pos = ensure_units(pos, 'mm')
    
    ret = self.move_absolute_enc(pos * self.actuator.enc_counts_per_mm, **kwargs)
    if ret is not None:
      return (ensure_units(ret, 'counts') / self.actuator.enc_counts_per_mm)

  def move_relative_enc(self, dist_enc, wait=True):
    dist_enc = ensure_units(dist_enc, 'counts')

    self.sendcmds('PM', '', 'MN', '', 'MR', int(dist_enc.magnitude), 'GO', '')

    if wait:
      self.wait_stop()

  def move_relative_mm(self, dist_mm, **kwargs):
    dist_mm = ensure_units(dist_mm, 'mm')

    self.move_relative_enc(dist_mm * self.actuator.enc_counts_per_mm, **kwargs)

  def move_relative(self, dist, **kwargs):
    dist = ensure_units(dist, 'mm')

    self.move_relative_enc(dist * self.actuator.enc_counts_per_mm, **kwargs)

  def get_error(self):
    """
    Asks LAC-1 for the last error
    """
    error = self.sendcmds('TE', eat_prompt=False)
    if len(error) > 0:
      return error[0]
    else:
      return None

  def get_position_enc(self):
    """
    Returns the current position in encoder counts
    """
    pos = list()
    while len(pos) < 1:
      try:
        pos = self.sendcmds('TP')
      except Exception:
        from traceback import print_exc
        print_exc()

    return set_units(int(pos[0]), 'counts')

  def get_position_mm(self):
    """
    Returns the current position in mm
    """
    ret = self.get_position_enc()
    return (ensure_units(ret, 'counts') / self.actuator.enc_counts_per_mm).to('mm').magnitude

  def get_position_um(self):
    ret = self.get_position_enc()
    return (ensure_units(ret, 'counts') / self.actuator.enc_counts_per_mm).to('um').magnitude

  def get_position(self):
    ret = self.get_position_enc()
    return (ensure_units(ret, 'counts') / self.actuator.enc_counts_per_mm)

  def get_params(self, paramset=''):
    """
    paramset is 0...n
    """
    return self.sendcmds('TK', paramset)
  
  def get_time(self):
    """
    Returns the current time in milliseconds since the controller was turned 
    on.  Time is read from the 1 mS real time clock/counter at address 1830.
    """
    ret = self.sendcmds('RL1830')
    if len(ret) > 0:
      return set_units(float(ret[0]), 'ms')
    else:
      return None
  
  def softland(self, force=False, execute=True, limit='10 mm', duty=0.9, velocity='4 mm/s', acceleration='10000 mm/s**2'):
    """
    This function executes a softland move. Details are derived from SMAC-MCA 
    Actuators User Manual rev 1.8 pg 38 
    (https://www.smac-mca.com/documents/PDFs/SMAC%20Actuators%20User%20Manual.pdf)

    Softland is the routine which enables the actuator to land on a surface 
    with a low force, for example to measure a component. This is done in 
    velocity mode, monitoring the position error as the rod is moving with a 
    controlled force
    """
    limit = ensure_units(limit, 'mm')
    velocity = ensure_units(velocity, 'mm / s' )
    acceleration = ensure_units(acceleration, 'mm / s**2')

    macro500 = self.sendcmds('TM500')
    if len(macro500) == 0 or force:

      # go into velocity mode, turn motor on, set force, acceleration and
      # velocity constants, set direction to be in the direction of INCREASING
      # encoder count, start motion, wait 20ms.
      #
      # MD: define macro
      # VM: velocity mode
      # MN: motor on
      # SQ: torque
      # SA: acceleration
      # SV: velocity
      # DI: direction
      # GO: begin movement
      # WA: wait
      SQ = int(duty * 32767)
      print('SQ:', SQ)
      SA = int((self.KA * acceleration).to('counts').magnitude)
      print('SA:', SA)
      SV = int((self.KV * velocity).to('counts').magnitude)
      print('SV:', SV)
      self.sendcmds(f'MD500,VM,MN,SQ{SQ},SA{SA},SV{SV},DI0,GO,WA200')

      # read word from memory 538, which is position error. If position error
      # is greater than 20, display a message, jump to macro 505. If position error
      # is greater than 5000, display a message, jump to macro 510. Otherwise repeat.
      #
      # MD: define macro
      # RW: read word from memory 538, where position error is stored
      # IG: if greater
      # MG: print message
      # MJ: jump to macro
      # RL: read long from memory, which is the position in encoder counts. We use this
      # RP: repeat
      max_travel = int((limit * self.actuator.enc_counts_per_mm).to('counts').magnitude)
      print('max_travel:', max_travel)
      self.sendcmds(f'MD501,RW538,IG20,MG"FOUND",MJ505,RL494,IG{max_travel},MG"TOO FAR",MJ505,RP')

      # Stop motion
      #
      # MD: define macro
      # ST: stop
      self.sendcmds('MD505,ST')

    if(execute):
      print('Executing softland macro')
      msg = self.sendcmds('MS500')
      print(msg)

  def close(self):
    if self._port:
      self._port.write(str.encode(self._ESC))
      self._port.write(str.encode(self._ESC))
      # abort, motor off, echo on
      self._port.write(str.encode('AB,MF,EN\r'))
      self._port.close()
      self._port = None

if __name__ == '__main__':
  import sys
  if len(sys.argv) < 4:
    print('Usage: %s <serial port> <baud> <commands and arguments>'%(sys.argv[0]))
    sys.exit(1)

  stage = LAC1(sys.argv[1], baudRate=int(sys.argv[2]))
  stage.sendcmds(*sys.argv[3:])

# Tests #####################################################################
def test_set_home_macro():
  lac1 = LAC1('/dev/ttyS0', 19200, silent=False)
  lac1.set_home_macro(force=True)
  lac1.home()
  p = lac1.get_position_enc()
  assert abs(p) <= 10, p

def test_home():
  lac1 = LAC1('/dev/ttyS0', 19200, silent=False)
  lac1.home()
  p = lac1.get_position_enc()
  assert abs(p) <= 10, p

