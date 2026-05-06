from opentrons import protocol_api
from opentrons.types import Point
from serial import *
import json
from time import sleep

requirements = {
#    "robotType": "Flex",
    "apiLevel": "2.18"
}



def run(protocol: protocol_api.ProtocolContext):
    # Number of replicates per experiment
    replicates = 7
    total_volume = 300 * replicates

    # Read the dataframe with 8 experiments (each experiment will be repeated 3 times)

    # Expand each row into 'replicates' entries (order is preserved so that rows 0 to 7 are repeated)
    DMAm_volumes    = [9.36, 1.83, 50, 50]
    AMPS_volumes    = [62.72, 0, 50, 50]
    PBS_volumes = [185.92, 152.17, 50, 50]
    crosslinker_volumes = [12, 96, 50, 50]
    photoinitiator_volumes = [30, 30, 50, 50]
    
    DMAm_replicates = []
    AMPS_replicates = []
    crosslinker_replicates = []
    photoinitiator_replicates = []
    PBS_replicates = []


    # top of plate
    for i in range(len(DMAm_volumes)):
        DMAm_replicates.append(DMAm_volumes[i]*replicates)
        AMPS_replicates.append(AMPS_volumes[i]*replicates)
        crosslinker_replicates.append(crosslinker_volumes[i]*replicates)
        photoinitiator_replicates.append(photoinitiator_volumes[i]*replicates)
        PBS_replicates.append(PBS_volumes[i]*replicates)

    

    # Total number of wells to fill
    total_wells = len(DMAm_volumes)

    # Create a list of well indices (0 to total_wells - 1)
    exp_no = list(range(total_wells))

    # Set up tip rack and pipette
    tip1000 = protocol.load_labware('opentrons_96_filtertiprack_1000ul','8')
    pipette_1000 = protocol.load_instrument ('p1000_single_gen2', 'right',tip_racks=[tip1000])
    # pipette_1000.tip_racks = tip1000b


    tip200 = protocol.load_labware('opentrons_96_filtertiprack_200ul','9')
    pipette_200 = protocol.load_instrument ('p300_single', 'left',tip_racks=[tip200])

    pipette = pipette_200



    def pipette_select(volume):
        if volume >= 200:
            pipette = pipette_1000
        else:
            pipette = pipette_200
        return pipette

    #Set intended pipette aspiration rate. Slower for higher viscosity stocks, and higher for lower viscosity ones
    # pipette.flow_rate.aspirate = 3
    # pipette.flow_rate.dispense = 3
    # pipette.flow_rate.blow_out = 50

    # pipette_200.flow_rate.aspirate = 3
    # pipette_200.flow_rate.dispense = 3
    # pipette_200.flow_rate.blow_out = 50

    # pipette_1000.flow_rate.aspirate = 3
    # pipette_1000.flow_rate.dispense = 3
    # pipette_1000.flow_rate.blow_out = 50

    # Load stock labware and assign stock wells.
    stock = protocol.load_labware('allen_8_wellplate_20000ul', '6')
    DMAm_stock = stock['A1']
    AMPS_stock = stock['A2']
    crosslinker_stock = stock['A3']
    photoinitiator_stock = stock['A4']
    PBS_stock = stock['B1']

    # Load destination wellplates`1`
    wellplate1 = protocol.load_labware('nest_96_wellplate_2ml_deep', '5')

    wellplate_test = protocol.load_labware('testwell', '4')

    # wellplate2 = protocol.load_labware('sdlplateblock', '4')
    UV_stand = protocol.load_labware('testwell', '10')
    

    def custom_pickup1(location, x, y, z):
        custom_move(location, x+8, y-31, z + 17)
        sleep(2)
        custom_move(location, x+8, y-31, z + 12)
        sleep(2)
        custom_move(location, x+8, y-31, z + 7)

    def custom_dropoff1(location, x, y, z):
        offset_point = Point(x+8, y-21, z+23)
        loc_offset = location.move(offset_point)
        sleep(2)
        pipette_1000.drop_tip(loc_offset)

    def custom_pickup2(location, x, y, z):
        custom_move(location, x+8, y-21, z+17)
        sleep(2)
        custom_move(location, x+8, y-21, z+12)
        sleep(2)
        custom_move(location, x+8, y-21, z+7)

    def custom_dropoff2(location, x, y, z):
        offset_point = Point(x+8, y-31, z + 23)
        loc_offset = location.move(offset_point)
        sleep(2)
        pipette_1000.drop_tip(loc_offset)
    
    def custom_move(location, x, y, z):
        offset_point = Point(x, y, z)
        loc_offset = location.move(offset_point)
        pipette_1000.move_to(loc_offset, minimum_z_height=50)

    # Helper function to dispense a reagent from a given source to each well.
    def dispense_reagent(volume_list, source, reagent_name):
        EPS = 1e-6
        pipette_200.pick_up_tip()
        pipette_1000.pick_up_tip()
        for i in exp_no:
            if volume_list[i]>EPS:
                pipette = pipette_select(volume_list[i])
                pipette.aspirate(volume=volume_list[i], location=source.bottom(z=1), rate=10)
                pipette.touch_tip(location=source, radius=0.9, v_offset=-1, speed=50)
                pipette.dispense(volume=volume_list[i], location=wellplate1.wells()[i].top(z=0), rate=10)
                pipette.blow_out(location=wellplate1.wells()[i].top(z=0))
                protocol.delay(2)
                pipette.touch_tip(location=wellplate1.wells()[i], radius=0.9, v_offset=-0.5, speed=50)
        pipette_1000.drop_tip()
        pipette_200.drop_tip()
        protocol.comment(f"Dispensed {reagent_name} to all wells.")

### -----------


    # dispense_reagent(DMAm_replicates, DMAm_stock, "DMAm")
    # dispense_reagent(AMPS_replicates, AMPS_stock, "AMPS")
    # dispense_reagent(crosslinker_replicates, crosslinker_stock, "crosslinker")
    # dispense_reagent(photoinitiator_replicates, photoinitiator_stock, "photoinitiator")
    # dispense_reagent(PBS_replicates, PBS_stock, "PBS")

    
###--------------

    # # Pipette flow rate adjusted for better pipette mixing. Comment out if using vial stir plate
    pipette.flow_rate.aspirate = 110
    pipette.flow_rate.dispense = 110
    pipette.flow_rate.blow_out = 50

    pipette_200.flow_rate.aspirate = 110
    pipette_200.flow_rate.dispense = 110
    pipette_200.flow_rate.blow_out = 50

    pipette_1000.flow_rate.aspirate = 110
    pipette_1000.flow_rate.dispense = 110
    pipette_1000.flow_rate.blow_out = 50


    # # This section pipette mixes. Comment out pipette mixing if using vial stir plate
    # if total_volume >= 200:
    #     for i in range(total_wells):
    #         pipette = pipette_1000
    #         pipette.pick_up_tip()
    #         pipette.mix(10, total_volume/1.667, wellplate1.wells()[i+8].bottom(1))  # mix 5 times, 100 µL, near the bottom
    #         pipette.drop_tip()
    # else:
    #     for i in range(total_wells):
    #         pipette = pipette_200
    #         pipette.pick_up_tip()
    #         pipette.mix(10, total_volume/1.667, wellplate1.wells()[i+8].bottom(1))  # mix 5 times, 100 µL, near the bottom
    #         pipette.drop_tip()



    #Uncomment this if using vial mixing plate, to ensure stocks have enough time to mix
    # protocol.delay(120)


    # Transfer samples from wellplate1 to wellplate2
    # for i in range(total_wells):
    #     pipette = pipette_200

    #     pipette.flow_rate.aspirate = 100
    #     pipette.flow_rate.dispense = 100
    #     pipette.flow_rate.blow_out = 50

    #     pipette_200.flow_rate.aspirate = 100
    #     pipette_200.flow_rate.dispense = 100
    #     pipette_200.flow_rate.blow_out = 50

    #     pipette_1000.flow_rate.aspirate = 100
    #     pipette_1000.flow_rate.dispense = 100
    #     pipette_1000.flow_rate.blow_out = 50

    #     pipette.pick_up_tip()
    #     pipette.mix(10, 200, wellplate1.wells()[i].bottom(1))
    #     for j in range(replicates-2):

    #         pipette.flow_rate.aspirate = 3
    #         pipette.flow_rate.dispense = 3
    #         pipette.flow_rate.blow_out = 50

    #         pipette_200.flow_rate.aspirate = 3
    #         pipette_200.flow_rate.dispense = 3
    #         pipette_200.flow_rate.blow_out = 50

    #         pipette_1000.flow_rate.aspirate = 3
    #         pipette_1000.flow_rate.dispense = 3
    #         pipette_1000.flow_rate.blow_out = 50

    #         dest_index = ((i) + (j) * 5)
    #         pipette.aspirate(volume=95.0, location=wellplate1.wells()[i].bottom(z=1), rate=10)
    #         pipette.touch_tip(location=wellplate1.wells()[i], radius=0.9, v_offset=-1, speed=50)
    #         pipette.dispense(volume=95.0, location=wellplate_test.wells()[dest_index].top(), rate=10)
    #         pipette.blow_out(location=wellplate_test.wells()[dest_index].top())
    #         protocol.delay(2)
    #         # pipette.touch_tip(location=wellplate2.wells()[dest_index], radius=0.9, v_offset=-0.75, speed=50)
    #     pipette.drop_tip()

    
    pipette_1000.pick_up_tip(tip1000.wells()[95])
    custom_pickup1(UV_stand["E1"].bottom(z=1), 0, 0, 0)
    custom_dropoff1(wellplate_test["A1"].bottom(z=1), 0, 0, 0)


    pipette_1000.pick_up_tip(tip1000.wells()[95])
    custom_pickup2(wellplate_test["A1"].bottom(z=1), 0, 0, 0)
    custom_dropoff2(UV_stand["E1"].bottom(z=1), 0, 0, 0)

    # sleep(300)

    # with Serial('/dev/cu.usbmodemF412FA6A25EC2', 115200) as in_port:
    #     in_port.write(b"1")
    #     sleep(6)
    #     in_port.write(b"0")

    # pipette_1000.pick_up_tip(tip1000.wells()[95])
    # custom_pickup(wellplate2["D6"].bottom(z=1), 0, 0, 0)
    # custom_dropoff2(wellplate3["D6"].bottom(z=1), 0, 0, 0)
