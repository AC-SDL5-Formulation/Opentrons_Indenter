from cnc_machine import CNC_Machine
import threading
from gdx import gdx
import timeit
gdx = gdx.gdx()
gdx.open(connection='ble')
gdx.select_sensors()
gdx.start() 

cnc = CNC_Machine(virtual=False)
column_headers= gdx.enabled_sensor_info()   # returns a string with sensor description and units
print('\n')
print(column_headers)
indent_dict = {}
thread_flag = True

track_time = timeit.default_timer()

indent_var = [thread_flag, track_time, cnc]


def gdx_threaded_function():
     while indent_var[0]: 
          track = timeit.default_timer() - indent_var[1]
          val = gdx.read()
          indent_dict[track] = val[0]
          

gdx_thread = threading.Thread(target = gdx_threaded_function, daemon=True)
gdx_thread.start()

cnc.home()

cnc.move_to_location(location_name='main_rack_A', location_index=0, safe=True)


# final_measurement = gdx.readValues()


for i in range (0, 1):
     for j in range(0, 1): 
          cnc.move_to_location('main_rack_A', (i+(j*4)),safe=True, speed=200)
          for r in range(0,100):
               cnc.move_to_point(z=-10-(3*r), speed=200)
               print("third")
               final_measurement = list(indent_dict.values())[-1]
               print(final_measurement)
               if final_measurement > 4:
                    break


cnc.home()
indent_var[0] = False

gdx_thread.join(timeout=3)
print("Bloop")
gdx.close()
#print(indent_dict)
print(list(indent_dict.keys()))
print(list(indent_dict.values()))