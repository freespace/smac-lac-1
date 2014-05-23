from lac1 import LAC1

lac1 = LAC1('/dev/ttyS0')
lac1.home()

lac1.set_max_velocity(10000)
lac1.set_max_acceleration(20000)

import time
starttime = time.time()
nloops = 20
dist = 10
for cnt in xrange(nloops):
  lac1.move_absolute_mm(0)
  lac1.move_absolute_mm(dist)
  lac1.move_absolute_mm(0)

dt = time.time() - starttime

# we cover 2*dist per loop
disttravelled = nloops * dist * 2

print 'total time: %.2f\tavg speed: %.2f mm/s'%(dt, disttravelled/dt)
