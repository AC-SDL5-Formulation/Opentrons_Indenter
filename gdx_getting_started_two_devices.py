''' 
Simple starter program to show how to configure the gdx functions to read 
from more than one Go Direct device.  

Two things to note for connecting multiple devices. The first is listing
all devices in the 'device_to_open' argument, separating the device names
with a comma, such as:

gdx.open(connection='ble', device_to_open='GDX-FOR 071000U9, GDX-HD 151000C1')

The second is setting the select_sensor() argument as a 2D list of sensor
numbers, such as:

gdx.select_sensors([[1,2,3], [1]])

To review how to set the select_sensors() argument based on how many devices
and sensors are configured, here are some examples:
    Configure 1 device with sensor number 1:
    gdx.select_sensors([1])
    Configure 1 device with sensor numbers 1, 5, and 6:
    gdx.select_sensors([1,5,6])
    Configure 2 devices. Device 1 with sensor number 1. Device 2 with sensor 5:
    gdx.select_sensors([[1], [5]])
    Configure 3 devices. Device 1 with sensors 1,5,6. Device 2 with sensor 5. 
    Device 3 with sensors 1 and 2:
    gdx.select_sensors([[1,5,6], [5], [1,2]]) 
'''

# from gdx import gdx
# gdx = gdx.gdx()


# # ENTER YOUR DEVICE NAMES HERE
# gdx.open(connection='ble', device_to_open='enter 1st device name here, 2nd device name here')
# #gdx.open(connection='usb', device_to_open='GDX-FOR 071000U9, GDX-MD 0B1008M1')

# # ENTER YOUR 2D LIST OF SENSORS HERE
# gdx.select_sensors([[], []])
# #gdx.select_sensors([[1,2], [5]])

# gdx.start(500) 
# column_headers= gdx.enabled_sensor_info()   # returns a string with sensor description and units
# print('\n')
# print(column_headers)

# for i in range(0,5):
#     measurements = gdx.read()
#     if measurements == None: 
#         break 
#     print(measurements)

# gdx.stop()
# gdx.close()

x = [-0.04174041748046875, 0.0187835693359375, 0.03130340576171875, 0.06678009033203125, 0.0834808349609375, 0.08765411376953125, 0.102264404296875, 0.1377410888671875, 0.18157196044921875, 0.13983154296875, 0.135650634765625, 0.13983154296875, 0.18782806396484375, 0.2024383544921875, 0.200347900390625, 0.194091796875, 0.194091796875, 0.19826507568359375, 0.2024383544921875, 0.20452880859375, 0.20870208740234375, 0.210784912109375, 0.21704864501953125, 0.21704864501953125, 0.221221923828125, 0.2379150390625, 0.23583221435546875, 0.24208831787109375, 0.26296234130859375, 0.25252532958984375, 0.2775726318359375, 0.285919189453125, 0.285919189453125, 0.29843902587890625, 0.30052947998046875, 0.30887603759765625, 0.31931304931640625, 0.323486328125, 0.32765960693359375, 0.33600616455078125, 0.33600616455078125, 0.34435272216796875, 0.34435272216796875, 0.3485260009765625, 0.361053466796875, 0.371490478515625, 0.38191986083984375, 0.40904998779296875, 1.6967391967773438]
for i in x:
    print (i)