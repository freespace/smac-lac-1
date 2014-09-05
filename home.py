from lac1 import LAC1

lac1 = LAC1('/dev/ttyS0', baudRate=19200)
lac1.set_home_macro(force=True)
lac1.home()
print 'Homed'
