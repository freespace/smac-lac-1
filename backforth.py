from lac1 import LAC1

lac1 = LAC1('/dev/ttyS0', baudRate=19200)
lac1.home()

lac1.set_max_velocity(5000)
lac1.set_max_torque(10000)
lac1.set_max_acceleration(30000)
#lac1.set_max_acceleration(5000)

import time
nloops = 50
dist = 20

starttime = time.time()
lac1.move_absolute_mm(0)
lac1.move_absolute_mm(dist)
dt = time.time() - starttime

# we cover 2*dist per loop
disttravelled = dist

print 'Travelled ', disttravelled,'mm'
print 'total time: %.2f\tavg speed: %.2f mm/s'%(dt, disttravelled/dt)
