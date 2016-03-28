#!/usr/bin/env python
import serial
import time

# it is important to make these floats to avoid integer truncation error
ENC_COUNTS_PER_MM = 1000.0  # encoder counts per mm
SERVO_LOOP_FREQ = 5000.0    # servo loop frequency

# This is specific to the stage I am using
# TODO Implement range checking for safety?
STAGE_TRAVEL_MM = 25
STAGE_TRAVEL_UM = STAGE_TRAVEL_MM*1000
STAGE_TRAVEL_ENC = STAGE_TRAVEL_MM * ENC_COUNTS_PER_MM

# we will not allow travel beyond TRAVEL_SAFETY_FACTOR * STAGE_TRAVEL_ENC
TRAVEL_SAFETY_FACTOR = 1.0

# KV and KA defined the change in encoder per servo loop needed to achieve
# 1 mm/s velocity and 1 mm/s/s acceleration, respectively.
KV = 65536 * ENC_COUNTS_PER_MM / SERVO_LOOP_FREQ
KA = 65536 * ENC_COUNTS_PER_MM / (SERVO_LOOP_FREQ**2)

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

  def __init__(self, port, baudRate, silent=True, reset=True, sleepfunc=None):
    """
    If silent is True, then no debugging output will be printed. Default is
    True.

    If sleepfunc is not None, then it will be used instead of time.sleep.
    It will be passed the number of seconds to sleep for. This is provided
    for integration with single threaded GUI applications.
    """

    if sleepfunc is not None:
      self._sleepfunc = sleepfunc

    print 'Connecting to LAC-1 on %s (%s)'%(port, baudRate)
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
        'SG', SG,
        'SI', SI,
        'SD', SD,
        'IL', IL,
        'SE', SE,
        'RI', RI,
        'FR', FR)

    # these are pretty safe values
    self.set_max_velocity(1)
    self.set_max_acceleration(1)

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
      c = self._port.read()
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
      print '[>]',line
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
      print '[<]',tosend

    self._port.flushInput()
    self._port.flushOutput()

    assert len(tosend) <= SERIAL_MAX_LINE_LENGTH, 'Command exceeds allowed line length'

    self._port.write(tosend+'\r')

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

  def set_home_macro(self, force=False):
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
      self.sendcmds('MD100,SG50,SI80,SD700,IL5000,FR1,RI1')

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
      self.sendcmds('MD101,VM,MN,SQ30000,SA30000,SV50000,DI1,GO,WA20')

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
      # MF: motor off
      self.sendcmds('MD105,ST,WS25,PM,MR1000,GO,WS25,DH0,MF')

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
    self.move_absolute_enc(0, wait)

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

  def set_max_velocity(self, mmpersecond):
    self.sendcmds('SV', KV*mmpersecond)

  def set_max_acceleration(self, mmpersecondpersecond):
    self.sendcmds('SA',KA*mmpersecondpersecond)

  def set_max_torque(self, q):
    """
    I don't know what units this is in, the instructions don't say
    so it just do it via trial and error
    """
    self.sendcmds('SQ',q)

  def wait_stop(self):
    self.sendcmds('WS', WS_PERIOD_MS)

  def wait(self, interval_ms):
    self.sendcmds('WA', interval_ms)

  def move_absolute_enc(self, pos_enc, wait=True, getposition=False):
    """
    Move to a position specified in encoder counts
    """
    assert pos_enc <= STAGE_TRAVEL_ENC * TRAVEL_SAFETY_FACTOR
    assert pos_enc >= 0

    cmds = ['PM', '', 'MN', '', 'MA', int(pos_enc),'GO','']
    if wait:
      cmds += ['WS', WS_PERIOD_MS]

      if getposition:
        cmds += ['TP', '']

    ret = self.sendcmds(*cmds)

    if wait and getposition:
      return int(ret[0])

  def move_absolute_mm(self, pos_mm, **kwargs):
    self.move_absolute_enc(pos_mm * ENC_COUNTS_PER_MM, **kwargs)

  def move_absolute_um(self, pos_um, **kwargs):
    kwargs['getposition'] = True
    ret = self.move_absolute_enc(pos_um * ENC_COUNTS_PER_MM / 1000, **kwargs)
    if ret is not None:
      return 1000 * ret / ENC_COUNTS_PER_MM

  def move_relative_enc(self, dist_enc, wait=True):
    self.sendcmds('PM', '', 'MN', '', 'MR', dist_enc, 'GO', '')

    if wait:
      self.wait_stop()

  def move_relative_mm(self, dist_mm, **kwargs):
    self.move_relative_enc(dist_mm * ENC_COUNTS_PER_MM, **kwargs)

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
      except Exception, ex:
        from traceback import print_exc
        print_exc(ex)

    return int(pos[0])

  def get_position_mm(self):
    """
    Returns the current position in mm
    """
    return self.get_position_enc() / ENC_COUNTS_PER_MM

  def get_position_um(self):
    return 1000 * self.get_position_enc() / ENC_COUNTS_PER_MM

  def get_params(self, paramset=''):
    """
    paramset is 0...n
    """
    return self.sendcmds('TK', paramset)

  def close(self):
    if self._port:
      self._port.write(self._ESC)
      self._port.write(self._ESC)
      # abort, motor off, echo on
      self._port.write('AB,MF,EN\r')
      self._port.close()
      self._port = None

if __name__ == '__main__':
  import sys
  if len(sys.argv) < 4:
    print 'Usage: %s <serial port> <baud> <commands and arguments>'%(sys.argv[0])
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

