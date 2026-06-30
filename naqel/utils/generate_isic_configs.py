#!/usr/bin/env python3
import json

# Read ISIC groups from file
with open('/tmp/isic_groups.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()[1:]  # Skip header

isic_groups = []
for line in lines:
    parts = line.strip().split('\t')
    if len(parts) >= 2:
        name = parts[0].strip()
        code = parts[1].strip()
        if name and code:
            isic_groups.append({'name': name, 'code': code})

# Define industry sector patterns and their defaults
sector_defaults = {
    # Agriculture, Forestry, Fishing (011-032)
    'agriculture': {
        'range': (11, 32),
        'facility_uom': 'Area',
        'waste_dist': [60, 30, 10],  # Organic, Recyclable, Residual
        'thresholds': [500, 1000, 2000, 5000],
        'containers': [
            ('2 yards', 3),
            ('4 yards', 2),
            ('6 yards', 2),
            ('12 yards', 2)
        ]
    },
    # Mining and Quarrying (051-099)
    'mining': {
        'range': (51, 99),
        'facility_uom': 'Area',
        'waste_dist': [10, 40, 50],
        'thresholds': [1000, 2500, 5000, 10000],
        'containers': [
            ('4 yards', 4),
            ('6 yards', 3),
            ('12 yards', 3),
            ('12 yards', 5)
        ]
    },
    # Manufacturing - Food/Beverages (101-120)
    'food_manufacturing': {
        'range': (101, 120),
        'facility_uom': 'Area',
        'waste_dist': [50, 30, 20],
        'thresholds': [100, 250, 500, 1000],
        'containers': [
            ('2 yards', 5),
            ('4 yards', 4),
            ('6 yards', 3),
            ('12 yards', 3)
        ]
    },
    # Manufacturing - Textiles/Apparel (131-152)
    'textile_manufacturing': {
        'range': (131, 152),
        'facility_uom': 'Area',
        'waste_dist': [10, 60, 30],
        'thresholds': [100, 250, 500, 1000],
        'containers': [
            ('2 yards', 4),
            ('4 yards', 3),
            ('6 yards', 2),
            ('12 yards', 2)
        ]
    },
    # Manufacturing - Wood/Paper (161-182)
    'paper_manufacturing': {
        'range': (161, 182),
        'facility_uom': 'Area',
        'waste_dist': [20, 50, 30],
        'thresholds': [100, 250, 500, 1000],
        'containers': [
            ('2 yards', 4),
            ('4 yards', 3),
            ('6 yards', 3),
            ('12 yards', 2)
        ]
    },
    # Manufacturing - Chemicals (191-210)
    'chemical_manufacturing': {
        'range': (191, 210),
        'facility_uom': 'Area',
        'waste_dist': [5, 35, 60],
        'thresholds': [100, 250, 500, 1000],
        'containers': [
            ('2 yards', 3),
            ('4 yards', 3),
            ('6 yards', 2),
            ('12 yards', 2)
        ]
    },
    # Manufacturing - Plastics/Rubber (221-222)
    'plastic_manufacturing': {
        'range': (221, 222),
        'facility_uom': 'Area',
        'waste_dist': [5, 65, 30],
        'thresholds': [100, 250, 500, 1000],
        'containers': [
            ('2 yards', 4),
            ('4 yards', 3),
            ('6 yards', 2),
            ('12 yards', 2)
        ]
    },
    # Manufacturing - Non-metallic minerals (231-239)
    'mineral_manufacturing': {
        'range': (231, 239),
        'facility_uom': 'Area',
        'waste_dist': [5, 40, 55],
        'thresholds': [250, 500, 1000, 2000],
        'containers': [
            ('4 yards', 3),
            ('6 yards', 3),
            ('12 yards', 2),
            ('12 yards', 3)
        ]
    },
    # Manufacturing - Metals (241-259)
    'metal_manufacturing': {
        'range': (241, 259),
        'facility_uom': 'Area',
        'waste_dist': [5, 50, 45],
        'thresholds': [250, 500, 1000, 2000],
        'containers': [
            ('4 yards', 4),
            ('6 yards', 3),
            ('12 yards', 3),
            ('12 yards', 4)
        ]
    },
    # Manufacturing - Machinery/Electronics (261-279)
    'electronics_manufacturing': {
        'range': (261, 279),
        'facility_uom': 'Area',
        'waste_dist': [10, 55, 35],
        'thresholds': [100, 250, 500, 1000],
        'containers': [
            ('2 yards', 3),
            ('4 yards', 2),
            ('6 yards', 2),
            ('12 yards', 1)
        ]
    },
    # Manufacturing - Vehicles (291-309)
    'vehicle_manufacturing': {
        'range': (291, 309),
        'facility_uom': 'Area',
        'waste_dist': [5, 55, 40],
        'thresholds': [250, 500, 1000, 2000],
        'containers': [
            ('4 yards', 4),
            ('6 yards', 3),
            ('12 yards', 3),
            ('12 yards', 4)
        ]
    },
    # Manufacturing - Furniture/Other (310-329)
    'furniture_manufacturing': {
        'range': (310, 329),
        'facility_uom': 'Area',
        'waste_dist': [15, 50, 35],
        'thresholds': [100, 250, 500, 1000],
        'containers': [
            ('2 yards', 3),
            ('4 yards', 3),
            ('6 yards', 2),
            ('12 yards', 2)
        ]
    },
    # Utilities (351-390)
    'utilities': {
        'range': (351, 390),
        'facility_uom': 'Area',
        'waste_dist': [10, 45, 45],
        'thresholds': [500, 1000, 2000, 5000],
        'containers': [
            ('4 yards', 3),
            ('6 yards', 3),
            ('12 yards', 3),
            ('12 yards', 4)
        ]
    },
    # Construction (410-439)
    'construction': {
        'range': (410, 439),
        'facility_uom': 'Area',
        'waste_dist': [10, 45, 45],
        'thresholds': [500, 1000, 2000, 5000],
        'containers': [
            ('4 yards', 4),
            ('6 yards', 4),
            ('12 yards', 3),
            ('12 yards', 5)
        ]
    },
    # Retail - General (451-479)
    'retail': {
        'range': (451, 479),
        'facility_uom': 'Area',
        'waste_dist': [15, 55, 30],
        'thresholds': [100, 250, 500, 1000],
        'containers': [
            ('2 yards', 3),
            ('4 yards', 2),
            ('6 yards', 2),
            ('12 yards', 2)
        ]
    },
    # Transportation (491-532)
    'transportation': {
        'range': (491, 532),
        'facility_uom': 'Area',
        'waste_dist': [20, 45, 35],
        'thresholds': [250, 500, 1000, 2000],
        'containers': [
            ('2 yards', 4),
            ('4 yards', 3),
            ('6 yards', 3),
            ('12 yards', 2)
        ]
    },
    # Accommodation and Food (551-563)
    'hospitality': {
        'range': (551, 563),
        'facility_uom': 'Area',
        'waste_dist': [40, 35, 25],
        'thresholds': [50, 100, 200, 500],
        'containers': [
            ('240 Litre', 8),
            ('2 yards', 4),
            ('4 yards', 3),
            ('12 yards', 2)
        ]
    },
    # Information and Communication (581-639)
    'information': {
        'range': (581, 639),
        'facility_uom': 'Area',
        'waste_dist': [10, 65, 25],
        'thresholds': [100, 250, 500, 1000],
        'containers': [
            ('240 Litre', 4),
            ('2 yards', 2),
            ('4 yards', 2),
            ('6 yards', 1)
        ]
    },
    # Financial (641-663)
    'financial': {
        'range': (641, 663),
        'facility_uom': 'Area',
        'waste_dist': [5, 70, 25],
        'thresholds': [100, 250, 500, 1000],
        'containers': [
            ('240 Litre', 3),
            ('2 yards', 2),
            ('4 yards', 1),
            ('6 yards', 1)
        ]
    },
    # Real Estate (681-682)
    'real_estate': {
        'range': (681, 682),
        'facility_uom': 'Number of Floors',
        'waste_dist': [20, 35, 45],
        'thresholds': [5, 10, 20, 40],
        'containers': [
            ('240 Litre', 10),
            ('2 yards', 5),
            ('4 yards', 4),
            ('12 yards', 2)
        ]
    },
    # Professional/Scientific (691-750)
    'professional': {
        'range': (691, 750),
        'facility_uom': 'Area',
        'waste_dist': [10, 60, 30],
        'thresholds': [100, 250, 500, 1000],
        'containers': [
            ('240 Litre', 4),
            ('2 yards', 2),
            ('4 yards', 2),
            ('6 yards', 1)
        ]
    },
    # Administrative Services (771-829)
    'administrative': {
        'range': (771, 829),
        'facility_uom': 'Area',
        'waste_dist': [15, 50, 35],
        'thresholds': [100, 250, 500, 1000],
        'containers': [
            ('2 yards', 3),
            ('4 yards', 2),
            ('6 yards', 2),
            ('12 yards', 1)
        ]
    },
    # Education (851-855)
    'education': {
        'range': (851, 855),
        'facility_uom': 'Number of Classes',
        'waste_dist': [30, 50, 20],
        'thresholds': [5, 10, 20, 40],
        'containers': [
            ('240 Litre', 5),
            ('2 yards', 3),
            ('4 yards', 2),
            ('6 yards', 2)
        ]
    },
    # Health (861-869)
    'health': {
        'range': (861, 869),
        'facility_uom': 'Number of Rooms',
        'waste_dist': [30, 25, 45],
        'thresholds': [20, 50, 100, 200],
        'containers': [
            ('2 yards', 5),
            ('4 yards', 4),
            ('6 yards', 3),
            ('12 yards', 3)
        ]
    },
    # Arts/Recreation (900-932)
    'recreation': {
        'range': (900, 932),
        'facility_uom': 'Area',
        'waste_dist': [20, 50, 30],
        'thresholds': [500, 1000, 2000, 5000],
        'containers': [
            ('2 yards', 4),
            ('4 yards', 3),
            ('6 yards', 3),
            ('12 yards', 3)
        ]
    },
    # Other Services (941-990)
    'other_services': {
        'range': (941, 990),
        'facility_uom': 'Area',
        'waste_dist': [25, 45, 30],
        'thresholds': [100, 250, 500, 1000],
        'containers': [
            ('2 yards', 3),
            ('4 yards', 2),
            ('6 yards', 2),
            ('12 yards', 1)
        ]
    }
}

def get_sector_defaults(code_num):
    """Get defaults for a given ISIC code"""
    for sector_name, config in sector_defaults.items():
        if config['range'][0] <= code_num <= config['range'][1]:
            return config
    # Default fallback
    return {
        'facility_uom': 'Area',
        'waste_dist': [30, 40, 30],
        'thresholds': [100, 250, 500, 1000],
        'containers': [
            ('2 yards', 3),
            ('4 yards', 2),
            ('6 yards', 2),
            ('12 yards', 1)
        ]
    }

# Generate configurations
configurations = []

for isic in isic_groups:
    code_num = int(isic['code'])
    defaults = get_sector_defaults(code_num)
    
    config = {
        "doctype": "Service Configuration",
        "naming_series": "CONF-",
        "service_type": "Commercial Waste",
        "isic_classification_category": "Group",
        "isic_classification": isic['name'],
        "facility_uom": defaults['facility_uom'],
        "calculate_facility_wastes_by": "Cluster Classification",
        "calculate_generation_rate_by": "Mean",
        "waste_distributions": [
            {
                "doctype": "Waste Distribution",
                "waste_group": "Organic Wastes",
                "distribution_percentage": float(defaults['waste_dist'][0])
            },
            {
                "doctype": "Waste Distribution",
                "waste_group": "Recyclable Wastes",
                "distribution_percentage": float(defaults['waste_dist'][1])
            },
            {
                "doctype": "Waste Distribution",
                "waste_group": "Residual Wastes",
                "distribution_percentage": float(defaults['waste_dist'][2])
            }
        ],
        "generation_classification": [
            {
                "doctype": "Waste Generation Classification",
                "max_threshold": defaults['thresholds'][i],
                "container_type": defaults['containers'][i][0],
                "count": defaults['containers'][i][1]
            }
            for i in range(4)
        ]
    }
    
    configurations.append(config)

# Write to JSON file
output_file = '/tmp/service_configuration_data_full.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(configurations, f, ensure_ascii=False, indent=4)

print(f"Generated {len(configurations)} configurations")
print(f"Output file: {output_file}")
