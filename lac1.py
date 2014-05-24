#!/usr/bin/env python
import serial
import time

# it is important to make these floats to avoid integer truncation error
ENC_COUNTS_PER_MM = 1000.0  # encoder counts per mm
SERVO_LOOP_FREQ = 5000.0    # servo loop frequency

STAGE_TRAVEL_MM = 25

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

ESC = '\033'

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

  def __init__(self, port, silent=True, reset=True):
    """
    If silent is True, then no debugging output will be printed. Default is
    True.

    If reset is True, then RT is sent to reset LAC-1. Defaults to True.
    """

    self._port = serial.Serial(
        port = port,
        baudrate = 9600,
        bytesize = 8,
        stopbits = 1,
        parity = 'N',
        timeout = 0.1)

    self._silent = silent

    if reset:
      # reset the controller to a known state
      self._sendcmds('RT')

    # turn off echo, or it will confuse us
    self._sendcmds('EF')

    # setup some initial parameters
    self._sendcmds(
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
    that accepts the max number of chars to read, and the end of line character.

    With python >= 2.6, pySerial uses io.RawIOBase, whose readline only accepts
    the max number of chars to read. io.RawIOBase does support the idea of a
    end of line character, but it is an attribute on the instance, which makes
    sense... except pySerial doesn't pass the newline= keyword argument
    along to the underlying class, and so you can't actually change it.
    """
    done = False
    line = str()
    #print 'reading line',
    while not done:
      c = self._port.read()
      #print repr(c),
      # ignores \n because we are not a terminal that cares about linefeed
      if c == '\n':
        continue
      if c == '\r':
          done = True
      else:
        line += c
        if stop_on_prompt and c == '>':
          done = True

    #print ''
    if len(line) and line[0] == '?':
      raise Exception('LAC-1 Error: '+line[1:])

    #print 'read: "%s"'%(line)
    return line

  def _sendcmds(self, *args, **kwargs):
    """
    This method sends the given commands and argument to LAC-1. Commands are
    expected in the order of

      cmd arg cmd arg

    And will be sent as:

      $cmd$arg,$cmd,$arg<CR>

    If a command takes no argument, then put None or ''.

    Arguments will be put through str, and no error checking is done. Exception
    to this is if argument is a float, in which case it will be cast to an int.

    If the keyword argument wait is True, then after sending each command, the
    serial stream is consumed until '>' is encountered. This is because SMAC
    emits '>' when it is ready for another command. Any lines seen before
    encountering '>' and is not empty will be returned.

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
      print 'sent',tosend

    self._port.write(tosend)
    self._port.write('\r')

    self._port.flush()

    datalines = []
    wait = kwargs.get('wait', True)
    if wait:
      done = False
      while not done:
        #print '_sendcmds, reading'
        line = self._readline()
        #print '_sendcmds:',line
        if line == '>':
          done = True
        elif line is not None and len(line):
          datalines.append(line)

      return datalines
    else:
      time.sleep(0.1)
      return None

  def set_home_macro(self, force=False):
    """
    This function defines a homing macros on macros 100,101,102, and 105. It
    will also inserts a call to macro 100 in macro 0. This means this routine
    will be executed on start.

    In order for the home function to work, this function must have been called
    previously, or the homing macro has been defined at macro 100 previously.

    Note that macros persist between power cycles - there is no need to
    call this every time.

    This function does nothing if TM0 returns a non-zero length string, unless
    force is True.
    """

    macro0 = self._sendcmds('TM0')
    if len(macro0) == 0 or force:
      # need motor to be off before messing with macros
      self.motor_off()

      #reset macros 100,101, and 105
      self._sendcmds('RM')

      # we insert this here because we are executed on startup, and there
      # will be no PID parameters set.
      self._sendcmds('MD100,SG50,SI80,SD600,IL5000,FR1,RI1')

      # go into velocity mode, turn motor on, set force, acceleration and
      # velocity constants, set direction to be in the direction of DECREASING
      # encoder count, start motion, wait 20ms.
      self._sendcmds('MD101,VM,MN,SQ5000,SA1000,SV50000,DI1,GO,WA20')

      # read word from memory 538, which is position error. If position error
      # is greater than 20, jump to macro 105, otherwise repeat.
      # Note that IB will execute the next 2 commands if true, so we insert
      # a NOP in the form of NO to pad it out.
      self._sendcmds('MD102,RW538,IB-20,NO,MJ105,RP')

      # if we are here, then we have found the limit. Now forward 100 enconder
      # counts and define home there
      self._sendcmds('MD105,ST,WS10,PM,MR100,GO,WS25,DH0,GH')


      self._sendcmds('MD0,MC100')

  def home(self):
    self._sendcmds('MS100')

  def go(self):
    self._sendcmds('GO')

  def stop(self):
    self._sendcmds('ST')

  def abort(self):
    self._sendcmds('AB')

  def motor_on(self):
    self._sendcmds('MN')

  def motor_off(self):
    self._sendcmds('MF')

  def go_home(self):
    self._sendcmds('MN','','GH', '')

  def set_max_velocity(self, mmpersecond):
    self._sendcmds('SV', KV*mmpersecond)

  def set_max_acceleration(self, mmpersecondpersecond):
    self._sendcmds('SA',KA*mmpersecondpersecond)

  def wait_stop(self):
    self._sendcmds('WS', 10)

  def wait(self, interval_ms):
    self._sendcmds('WA', interval_ms)

  def move_absolute_enc(self, pos_enc, wait=True):
    """
    Move to a position specified in encoder counts
    """
    self._sendcmds('PM', '', 'MN', '', 'MA', pos_enc,'GO','')
    if wait:
      self.wait_stop()

  def move_absolute_mm(self, pos_mm, **kwargs):
    self.move_absolute_enc(pos_mm * ENC_COUNTS_PER_MM, **kwargs)

  def move_absolute_um(self, pos_um, **kwargs):
    self.move_absolute_enc(1000 * pos_mm * ENC_COUNTS_PER_MM, **kwargs)


  def move_relative_enc(self, dist_enc, wait=True):
    self._sendcmds('PM', '', 'MN', '', 'MR', dist_enc, 'GO', '')

    if wait:
      self.wait_stop()

  def move_relative_mm(self, dist_mm, **kwargs):
    self.move_relative_enc(dist_mm * ENC_COUNTS_PER_MM, **kwargs)

  def get_error(self):
    """
    Asks LAC-1 for the last error
    """
    error = self._sendcmds('TE', eat_prompt=False)
    return error[0]

  def get_position_enc(self):
    """
    Returns the current position in encoder counts
    """
    pos = self._sendcmds('TP')
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
    return self._sendcmds('TK', paramset)

  def close(self):
    if self._port:
      self._sendcmds(ESC, wait=False)
      self._sendcmds(ESC, wait=False)
      self.abort()
      self.motor_off()
      self._sendcmds("EN")
      self._port.close()
      self._port = None

  def __del__(self):
    self.close()

if __name__ == '__main__':
  import sys
  if len(sys.argv) < 3:
    print 'Usage: %s <serial port> <commands and arguments>'%(sys.argv[0])
    sys.exit(1)

  stage = LAC1(sys.argv[1])
  stage._sendcmds(*sys.argv[2:])

# Tests #####################################################################
def test_set_home_macro():
  lac1 = LAC1('/dev/ttyS0', silent=False)
  lac1.set_home_macro(force=True)
  p = lac1.get_position_enc()
  assert abs(p) <= 10, p

def test_home():
  lac1 = LAC1('/dev/ttyS0', silent=False)
  lac1.home()
  p = lac1.get_position_enc()
  assert abs(p) <= 10, p

