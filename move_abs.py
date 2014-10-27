from lac1 import LAC1

from getport import getport

if __name__ == '__main__':
  import sys
  if len(sys.argv) != 2:
    print sys.argv[0],'<abs position in mm>'
    sys.exit(1)
  else:
    lac1 = LAC1(getport(), baudRate=19200)
    lac1.set_max_velocity(50)
    lac1.set_max_acceleration(100)
    p = float(sys.argv[1])
    print 'Moving to',p,'mm'
    lac1.move_absolute_mm(p)
    print 'Done'
