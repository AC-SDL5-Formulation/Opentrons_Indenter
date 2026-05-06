# ''' 
# Simple starter program that uses the gdx functions to collect data from a Go Direct device 
# connected via Bluetooth. 

# When using gdx.open(), note it has two arguments that can be set. They are 'connection' 
# and 'device_to_open'. Here are some ways to configure gdx.open() for a bluetooth connection:

# gdx.open(connection='ble')
#             When the 'device_to_open' argument is left blank, the function 
#             finds all available Go Direct ble devices. If only one device is found it will
#             automatically connect to that device. If more than one device is found it prints 
#             the list to the terminal, and prompts the user to select the device to connect.

# gdx.open(connection='ble', device_to_open='GDX-FOR 071000U9')
#             Use your device's name as the argument. The function will search for a ble device 
#             with this name. If found it will connect it. If connecting to multiple devices 
#             separate the names with a comma, such as device_to_open='GDX-FOR 071000U9, GDX-HD 151000C1'

# gdx.open(connection='ble', device_to_open='proximity_pairing')
#             Use "proximity_pairing" as the argument and the function will find the ble device 
#             with the strongest rssi (signal strength) and connect that device.

# Tip: Skip the prompts to select the sensors and period by entering arguments in the functions.

# Example 1, collect data from sensor 1 at a period of 1000ms using:
# gdx.select_sensors([1])
# gdx.start(1000)

# Example 2, collect data from sensors 1, 2 and 3 at a period of 100ms using:
# gdx.select_sensors([1,2,3])
# gdx.start(100)
# '''

from gdx import gdx
gdx = gdx.gdx()
  
  
gdx.open(connection='ble')
gdx.select_sensors()
gdx.start() 
column_headers= gdx.enabled_sensor_info()   # returns a string with sensor description and units
print('\n')
print(column_headers)

for i in range(0,20):
    measurements = gdx.read()
    if measurements == None:
        break 
    print(measurements)

gdx.stop()
gdx.close()

# x = [-0.0083465576171875, 0.00626373291015625, 0.01251983642578125, 0.064697265625, 0.10852813720703125, 0.112701416015625, 0.123138427734375, 0.12731170654296875, 0.12939453125, 0.13565826416015625, 0.1377410888671875, 0.1377410888671875, 0.1419219970703125, 0.14400482177734375, 0.15444183349609375, 0.15235137939453125, 0.15235137939453125, 0.156524658203125, 0.16487884521484375, 0.16487884521484375, 0.18157196044921875, 0.21913909912109375, 0.22540283203125, 0.23583221435546875, 0.2337493896484375, 0.242095947265625, 0.24835968017578125, 0.252532958984375, 0.2608795166015625, 0.26922607421875, 0.26922607421875, 0.2775726318359375, 0.29218292236328125, 0.2984466552734375, 0.3255767822265625, 0.33809661865234375, 0.37566375732421875, 0.38610076904296875, 0.4007110595703125, 0.41532135009765625, 0.44245147705078125, 0.500885009765625, 0.5259323120117188, 1.2355117797851562]
# for i in x:
#    print (i)