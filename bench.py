#!/usr/bin/env python

import sys
from lac1 import LAC1

from getport import getport
lac1 = LAC1(getport(), baudRate=19200)

lac1.home()

lac1.set_max_velocity(1000)
lac1.set_max_torque(10000)
lac1.set_max_acceleration(30000)
#lac1.set_max_acceleration(5000)

import time
nloops = 1000
dist = 2

lac1.move_absolute_mm(0)
starttime = time.time()
for cnt in xrange(nloops):
  try:
    lac1.move_absolute_mm(dist, wait=False)
    p = lac1.get_position_mm()
    while p < dist:
      p = lac1.get_position_mm()
    
    lac1.move_absolute_mm(0, wait=False)
    p = lac1.get_position_mm()
    while p > 0:
      p = lac1.get_position_mm()


    sys.stdout.write('.')
    sys.stdout.flush()
    if cnt%100==0:
      print cnt
  except Exception, ex:
    print 'Exception occured on loop %d'%(cnt+1), ex
    break

dt = time.time() - starttime

# we cover 2*dist per loop
disttravelled = nloops * dist * 2

print 'Travelled ', disttravelled,'mm'
print 'Loops:',nloops, 'Loop distance:',dist*2
print 'total time: %.2f\tavg speed: %.2f mm/s'%(dt, disttravelled/dt)
