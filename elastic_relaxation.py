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

for i in range(0, 1): # number of samples
    for j in range(0, 1): # number of replicates 
        force_newtons = []
        force_mpa = []
        time_stored = []
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

        
        start_time = time.time()
        cnc.move_to_point(z=z_value - (height*0.05))
        print("relaxation test")

        for r in range(0, 30):
            
            final_measurement = 0

            for q in range(0, 8):
                measurements = gdx.read()
                if q > 6:
                    final_measurement = measurements[0] - blank
                    force_newtons.append(round(final_measurement, 4))
                    new_time = time.time()
                    time_stored.append(new_time-start_time)
                    print(final_measurement)

            if final_measurement > 2:
                break

            if len(force_newtons) > 2 and force_newtons[-1] < 0.65 * force_newtons[-2] and force_newtons[-1] > 0.1:
                break

            print("_____________________________________")
            print("force (N): ", force_newtons)
            print("time (secs): ", (new_time-start_time))

        print("")
        print("_____________________________________")
        print("Sample number: ", sample_number)
        print("Replicate number: ", replicate_number)
        print("")
        print("Height of sample is: ", height)

        for l in range(len(force_newtons)):
            stress_value = round(((force_newtons[l] / 25520) * 100) * 1000, 4)
            force_mpa.append(stress_value)

            # Save each point as one row for the CSV
            all_results.append({
                "sample": sample_number,
                "replicate": replicate_number,
                "sample_label": sample_label,
                "point_index": l + 1,
                "height": height,
                "compression_mm": (height*0.05),
                "force_N": force_newtons[l],
                "time_secs": time_stored[l],
                "stress_mPa": stress_value
                
                
            })

        print("Stress, in mPa: ", force_mpa)
        print("Time, in sec", (new_time-start_time))

# Write everything to CSV at the end
csv_file_name = "relaxation_results.csv"

with open(csv_file_name, mode="w", newline="") as file:
    writer = csv.DictWriter(
        file,
        fieldnames=[
            "sample",
            "replicate",
            "sample_label",
            "point_index",
            "height",
            "compression_mm",
            "force_N",
            "time_secs",
            "stress_mPa"
        ]
    )
    writer.writeheader()
    writer.writerows(all_results)

print("")
print("CSV file saved as:", csv_file_name)

cnc.home()
gdx.close()