from lac1 import LAC1

from getport import getport
lac1 = LAC1(getport(), baudRate=19200)

lac1.home()

lac1.set_max_velocity(5000)
lac1.set_max_torque(10000)
lac1.set_max_acceleration(30000)
#lac1.set_max_acceleration(5000)

import time
nloops = 50
dist = 5

lac1.move_absolute_mm(0)
starttime = time.time()
for cnt in xrange(nloops):
  lac1.move_absolute_mm(dist)
  lac1.move_absolute_mm(0)

dt = time.time() - starttime

# we cover 2*dist per loop
disttravelled = nloops * dist * 2

print 'Travelled ', disttravelled,'mm'
print 'Loops:',nloops, 'Loop distance:',dist*2
print 'total time: %.2f\tavg speed: %.2f mm/s'%(dt, disttravelled/dt)
