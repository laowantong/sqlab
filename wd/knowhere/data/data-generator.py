import csv

def generate_knowhere_data():
    # 1. Define the Nodes (Brokers)
    # Every broker now has 3 items. Quest items remain in the 'part' column 
    # so existing DuckPGQ queries won't break.
    brokers = [
        {"id": 1, "name": "Kraglin", "part": "Deflector Shield", "extra_part_1": "Hydraulic Pump", "extra_part_2": "Scrap Metal"},
        {"id": 2, "name": "Yondu", "part": "Ion Thruster", "extra_part_1": "Yaka Arrow Fin", "extra_part_2": "Navigation Chip"},
        {"id": 3, "name": "Stakar", "part": "Plasma Regulator", "extra_part_1": "Starship Paint", "extra_part_2": "Coolant Fluid"},
        {"id": 4, "name": "Aleta", "part": "Quantum Flux Coil", "extra_part_1": "Light-speed Module", "extra_part_2": "Ration Packs"},
        {"id": 5, "name": "Tullk", "part": "Thermal Exhaust", "extra_part_1": "Comms Array", "extra_part_2": "Laser Battery"},
        {"id": 6, "name": "Oblo", "part": "Gravity Generator", "extra_part_1": "Sensor Array", "extra_part_2": "Hyperdrive Casing"},
        {"id": 7, "name": "Martinex", "part": "Crystal Matrix", "extra_part_1": "Plasma Torch", "extra_part_2": "Warp Core"},
        {"id": 8, "name": "Charlie-27", "part": "Heavy Blaster", "extra_part_1": "Hull Plating", "extra_part_2": "Thruster Valve"},
        {"id": 9, "name": "Mainframe", "part": "Processing Unit", "extra_part_1": "Data Drive", "extra_part_2": "Logic Board"},
        {"id": 10, "name": "Krugarr", "part": "Mystic Relic", "extra_part_1": "Energy Conduit", "extra_part_2": "Aether Container"},
        {"id": 11, "name": "Blurp", "part": "Saki Chew Toy", "extra_part_1": "Furry Blanket", "extra_part_2": "Snack Rations"}
    ]

    # 2. Define the Edges (Trades)
    trades = [
        # Ion Thruster Routes (Target: Yondu/2)
        {"source_id": 1, "target_id": 2, "cost": 1000}, 
        {"source_id": 7, "target_id": 2, "cost": 800},
        {"source_id": 1, "target_id": 5, "cost": 100},
        {"source_id": 5, "target_id": 6, "cost": 150},
        {"source_id": 6, "target_id": 2, "cost": 200},

        # Plasma Regulator Routes (Target: Stakar/3)
        {"source_id": 8, "target_id": 3, "cost": 700},
        {"source_id": 8, "target_id": 9, "cost": 200},
        {"source_id": 9, "target_id": 3, "cost": 300},

        # Quantum Flux Coil Connections (Target: Aleta/4)
        {"source_id": 10, "target_id": 4, "cost": 500},
        {"source_id": 11, "target_id": 4, "cost": 450},
        {"source_id": 5, "target_id": 4, "cost": 600},

        # Background Noise
        {"source_id": 1, "target_id": 8, "cost": 300},
        {"source_id": 2, "target_id": 1, "cost": 900},
        {"source_id": 6, "target_id": 9, "cost": 120},
        {"source_id": 9, "target_id": 11, "cost": 50},
        {"source_id": 3, "target_id": 7, "cost": 400}
    ]

    # 3. Export Brokers to TSV
    for b in brokers:
        b['hash'] = 0
    for t in trades:
        t['hash'] = 0

    with open('broker.tsv', mode='w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=brokers[0].keys(), delimiter='\t')
        writer.writerows(brokers)
    print("Successfully generated broker.tsv with expanded inventories!")

    with open('trade.tsv', mode='w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=trades[0].keys(), delimiter='\t')
        writer.writerows(trades)
    print("Successfully generated trade.tsv!")

if __name__ == "__main__":
    generate_knowhere_data()
