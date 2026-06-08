# from cnc_machine import CNC_Machine

# from gdx import gdx
# import time
# gdx = gdx.gdx()
  
  
# gdx.open(connection='ble')
# gdx.select_sensors()
# gdx.start() 
# column_headers= gdx.enabled_sensor_info()   # returns a string with sensor description and units
# print('\n')
# print(column_headers)


# cnc = CNC_Machine(virtual=False)

# # cnc.home()


# cnc.home()

# cnc.move_to_location(location_name='main_rack_A', location_index=0, safe=True)

# for q in range(0, 8):
#      measurements = gdx.read()
#      if q > 6:
#           blank = measurements[0]
#           print(blank)


# final_measurement = gdx.readValues()



# for i in range (0, 3):
#      for j in range(0, 3): 
#           force_newtons = []
#           force_mpa = []
#           distance = []
#           compression_percent = []
#           final_measurement = 90
#           cnc.move_to_location('main_rack_A', (i+(j*6)),safe=True)
#           gdx.start()
#           for k in range(0, 50):
#                # change expected sample height here
#                cnc.move_to_point(z=-25-((0.5*k)))
#                print("first")
#                final_measurement = 0
#                for q in range(0, 8):
#                     measurements = gdx.read()
#                     if q > 6:
#                          final_measurement = measurements[0] - blank
#                          print(final_measurement)
              
#                if final_measurement > 0.07:
#                     z_value = (-25-((0.5*k)))+0.6
#                     break
#           cnc.move_to_point(z=z_value)
#           for r in range(0, 100):
#                cnc.move_to_point(z=z_value-(0.1*r))
#                print("second")
#                final_measurement = 0
#                for q in range(0, 8):
#                     measurements = gdx.read()
#                     if q > 6:
#                          final_measurement = measurements[0] - blank
#                          print(final_measurement)
#                if final_measurement > 0.05:
#                     z_value = (z_value-(0.1*r))+0.15
#                     break
#           height = ((z_value - (0.05*r)) + 30.55)
#           for r in range(0,100):
#                cnc.move_to_point(z=z_value-(0.05*r))
#                print("third")
#                final_measurement = 0
#                for q in range(0, 8):
#                     measurements = gdx.read()
#                     if q > 6:
#                          final_measurement = measurements[0] - blank
#                          force_newtons.append(round(final_measurement, 4))
#                          distance.append(round(0.05*r, 2))
#                          print(final_measurement)
#                if final_measurement > 10:
#                     break
#                if len(force_newtons) > 10 and force_newtons[-1] < 0.65 * force_newtons[-2] and force_newtons[-1] > 0.1:
#                     break
#                print("_____________________________________")
#                print("force (N): ", force_newtons)
#                print("distance (mm): ", distance)
#           print("")
#           print("_____________________________________")
#           print("Sample number: ", i+1)
#           print("Replicate number: ", j+1)
#           print("")
#           print("Height of sample is: ", height)
#           for l in range(len(force_newtons)):
#                force_mpa.append(round(((force_newtons[l]/25520)*100)*1000, 4)) #divide by area in sq metres, and then convert pa to mpa
#                compression_percent.append(round((distance[l]/height)*100, 4))
          
#           print("Stress, in mPa: ", force_mpa)
#           print("Strain, in %: ", compression_percent)



# cnc.home()

# gdx.close()





from cnc_machine import CNC_Machine
from gdx import gdx
import time
import csv

gdx = gdx.gdx()

gdx.open(connection='ble')
gdx.select_sensors()
gdx.start()

column_headers = gdx.enabled_sensor_info()   # returns a string with sensor description and units
print('\n')
print(column_headers)

cnc = CNC_Machine(virtual=False)

# cnc.home()
cnc.home()
cnc.move_to_location(location_name='main_rack_A', location_index=0, safe=True)

# This will store all rows for the CSV
all_results = []

for q in range(0, 8):
    measurements = gdx.read()
    if q > 6:
        blank = measurements[0]
        print(blank)

final_measurement = gdx.readValues()

for i in range(2, 3): # numnber of sample types
    for j in range(0, 3): #number of replicates
        force_newtons = []
        force_mpa = []
        distance = []
        compression_percent = []
        final_measurement = 90

        sample_number = i + 1
        replicate_number = j + 1
        sample_label = f"sample {sample_number} replicate {replicate_number}"

        cnc.move_to_location('main_rack_A', (i + (j * 6)), safe=True)
        gdx.start()

        for k in range(0, 50):
            # change expected sample height here
            expected_height = 0
            cnc.move_to_point(z=-expected_height-(0.5 * k))
            print("first")
            final_measurement = 0

            for q in range(0, 8):
                measurements = gdx.read()
                if q > 6:
                    final_measurement = measurements[0] - blank
                    print(final_measurement)

            if final_measurement > 0.07:
                z_value = (- expected_height - (0.5 * k)) + 0.6
                break

        cnc.move_to_point(z=z_value)

        for r in range(0, 100):
            cnc.move_to_point(z=z_value - (0.1 * r))
            print("second")
            final_measurement = 0

            for q in range(0, 8):
                measurements = gdx.read()
                if q > 6:
                    final_measurement = measurements[0] - blank
                    print(final_measurement)

            if final_measurement > 0.05:
                z_value = (z_value - (0.1 * r)) + 0.15
                break

        height = ((z_value - (0.05 * r)) + 22)

        

        for r in range(0, 1000):
            cnc.move_to_point(z=z_value - (0.05 * r))
            print("third")
            final_measurement = 0

            for q in range(0, 8):
                measurements = gdx.read()
                if q > 6:
                    final_measurement = measurements[0] - blank
                    force_newtons.append(round(final_measurement, 4))
                    distance.append(round(0.05 * r, 2))
                    print(final_measurement)

            if final_measurement > 2:
                break

            if len(force_newtons) > 2 and force_newtons[-1] < 0.65 * force_newtons[-2] and force_newtons[-1] > 0.1:
                break

            print("_____________________________________")
            print("force (N): ", force_newtons)
            print("distance (mm): ", distance)

        print("")
        print("_____________________________________")
        print("Sample number: ", sample_number)
        print("Replicate number: ", replicate_number)
        print("")
        print("Height of sample is: ", height)

        for l in range(len(force_newtons)):
            stress_value = round(((force_newtons[l] / 25520) * 1000) * 1000, 4)
            strain_value = round((distance[l] / height) * 100, 4)

            force_mpa.append(stress_value)
            compression_percent.append(strain_value)

            # Save each point as one row for the CSV
            all_results.append({
                "sample": sample_number,
                "replicate": replicate_number,
                "sample_label": sample_label,
                "point_index": l + 1,
                "height": height,
                "distance_mm": distance[l],
                "force_N": force_newtons[l],
                "strain_percent": strain_value,
                "stress_mPa": stress_value
                
                
            })

        print("Stress, in mPa: ", force_mpa)
        print("Strain, in %: ", compression_percent)

# Write everything to CSV at the end
csv_file_name = "stress_strain_results.csv"

with open(csv_file_name, mode="w", newline="") as file:
    writer = csv.DictWriter(
        file,
        fieldnames=[
            "sample",
            "replicate",
            "sample_label",
            "point_index",
            "height",
            "distance_mm",
            "force_N",
            "strain_percent",
            "stress_mPa"
        ]
    )
    writer.writeheader()
    writer.writerows(all_results)

print("")
print("CSV file saved as:", csv_file_name)

cnc.home()
gdx.close()
