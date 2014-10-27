def getport():
  import os
  serialport = os.environ.get('LAC1_PORT', '/dev/ttyS0')
  return serialport
