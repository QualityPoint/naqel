#!/usr/bin/env python3
"""
ISIC Group-Based Service Configuration Generator

This script generates industry-specific Service Configuration records for each ISIC Group
by analyzing the industry name and creating appropriate waste distributions (with is_group flag),
facility UOMs, thresholds, and container configurations.

All waste distributions include 'is_group: 1' to indicate they represent waste groups
(Organic Wastes, Recyclable Wastes, Residual Wastes) rather than specific waste types.

Usage:
    cd /home/assembahnasy/frappe-bench/apps/naqel
    python3 naqel/utils/generate_isic_group_configs.py

Output:
    /tmp/service_configuration_data_full.json
"""

import json
import re
import csv
import os

# Get the script directory to construct relative path to CSV
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(
    script_dir, '../nq_crm/doctype/isic_classification/data/isic.csv')

# Read ISIC groups from CSV file
isic_groups_dict = {}
with open(csv_path, 'r', encoding='utf-8') as f:
    csv_reader = csv.DictReader(f)
    for row in csv_reader:
        group_code = row['group_code'].strip()
        group_name = row['group_name'].strip()

        # Store unique groups by code
        if group_code and group_name and group_code not in isic_groups_dict:
            isic_groups_dict[group_code] = {
                'name': group_name,
                'code': group_code,
                'category_name': group_name,  # Use group_name as category
                'description': ''
            }

# Convert to sorted list by code
isic_groups = sorted(isic_groups_dict.values(), key=lambda x: x['code'])


def analyze_industry(name, code, category_name, description):
    """
    Analyze industry characteristics based on ISIC name and return configuration.

    Returns dict with:
        - facility_uom: Measurement unit for facilities
        - waste_dist: [Organic%, Recyclable%, Residual%]
        - thresholds: List of 4 facility size tiers
        - containers: List of (container_type, count) tuples
    """

    code_num = int(code)
    name_lower = name.lower() + ' ' + category_name.lower()

    # Default configuration (Daily basis)
    config = {
        'facility_uom': 'Area',
        'waste_dist': [30, 40, 30],
        'thresholds': [100, 250, 500, 1000],
        'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
    }

    # ============ AGRICULTURE & FORESTRY (011-024) ============
    if 11 <= code_num <= 17:
        # Crop farming - very high organic
        if 'محاصيل' in name or 'زراعة' in name:
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [80, 10, 10],  # Crop residue dominant
                'thresholds': [1000, 2500, 5000, 10000],
                'containers': [('4 yards', 1), ('6 yards', 1), ('12 yards', 1), ('20 yards', 1)]
            })
        # Plant propagation - high recyclable (plastic pots)
        elif 'إكثار' in name or 'نباتات' in name:
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [20, 60, 20],  # Plastic pots, containers
                'thresholds': [500, 1000, 2000, 5000],
                'containers': [('2 yards', 1), ('4 yards', 1), ('6 yards', 1), ('12 yards', 1)]
            })
        # Livestock - high organic (manure)
        elif 'حيواني' in name or 'ابقار' in name:
            config.update({
                'facility_uom': 'Number of Animals',
                'waste_dist': [85, 5, 10],  # Manure, bedding
                'thresholds': [50, 100, 250, 500],
                'containers': [('4 yards', 1), ('6 yards', 1), ('12 yards', 1), ('20 yards', 1)]
            })

    elif 22 <= code_num <= 24:
        # Forestry - very high organic (wood waste)
        config.update({
            'facility_uom': 'Area',
            'waste_dist': [75, 15, 10],  # Wood, branches
            'thresholds': [2000, 5000, 10000, 20000],
            'containers': [('4 yards', 1), ('6 yards', 1), ('12 yards', 1), ('20 yards', 1)]
        })

    # ============ FISHING & AQUACULTURE (031-032) ============
    elif 31 <= code_num <= 32:
        # Very high organic (fish waste, spoilage)
        config.update({
            'facility_uom': 'Area' if code_num == 31 else 'Number of Tanks',
            'waste_dist': [85, 5, 10],  # Fish parts, spoiled product
            'thresholds': [100, 250, 500, 1000] if code_num == 31 else [10, 25, 50, 100],
            'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
        })

    # ============ MINING & QUARRYING (051-099) ============
    elif 51 <= code_num <= 99:
        # Very high residual (mining waste, rock)
        config.update({
            'facility_uom': 'Area',
            'waste_dist': [5, 30, 65],  # Industrial/mineral waste
            'thresholds': [2000, 5000, 10000, 25000],
            'containers': [('4 yards', 1), ('6 yards', 1), ('12 yards', 1), ('20 yards', 1)]
        })

    # ============ FOOD MANUFACTURING (101-108) ============
    elif 101 <= code_num <= 108:
        if 'لحوم' in name or 'meat' in name_lower:
            # Meat processing - very high organic
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [75, 10, 15],  # Blood, fat, bones
                'thresholds': [100, 250, 500, 1000],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })
        elif 'سمك' in name or 'fish' in name_lower:
            # Fish processing - extremely high organic
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [85, 5, 10],
                'thresholds': [100, 250, 500, 1000],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })
        elif 'فاكهة' in name or 'خضر' in name or 'fruit' in name_lower or 'vegetable' in name_lower:
            # Fruit/veg processing - very high organic
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [70, 20, 10],  # Peels, spoilage
                'thresholds': [100, 250, 500, 1000],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })
        elif 'ألبان' in name or 'dairy' in name_lower:
            # Dairy - high organic + packaging
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [50, 35, 15],
                'thresholds': [100, 250, 500, 1000],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })
        elif 'أعلاف' in name or 'feed' in name_lower:
            # Animal feed - high organic
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [60, 25, 15],
                'thresholds': [250, 500, 1000, 2000],
                'containers': [('2 yards', 1), ('4 yards', 1), ('6 yards', 1), ('12 yards', 1)]
            })
        else:
            # Other food manufacturing
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [50, 35, 15],
                'thresholds': [100, 250, 500, 1000],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })

    # ============ BEVERAGES & TOBACCO (110-120) ============
    elif 110 <= code_num <= 120:
        if 'مشروبات' in name:
            # Beverages - high recyclable (bottles, cans)
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [15, 65, 20],
                'thresholds': [100, 250, 500, 1000],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })
        else:
            # Tobacco - high residual
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [10, 30, 60],
                'thresholds': [100, 250, 500, 1000],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })

    # ============ TEXTILES & APPAREL (131-152) ============
    elif 131 <= code_num <= 152:
        if 'جلود' in name or 'leather' in name_lower or 'فراء' in name:
            # Leather - high residual (chemical waste)
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [10, 35, 55],
                'thresholds': [100, 250, 500, 1000],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })
        else:
            # Textiles/Apparel - high recyclable (fabric scraps)
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [5, 70, 25],
                'thresholds': [100, 250, 500, 1000],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })

    # ============ WOOD & PAPER (161-182) ============
    elif 161 <= code_num <= 170:
        # Wood/Paper - very high recyclable
        config.update({
            'facility_uom': 'Area',
            'waste_dist': [10, 70, 20],  # Wood chips, paper scraps
            'thresholds': [250, 500, 1000, 2000],
            'containers': [('2 yards', 1), ('4 yards', 1), ('6 yards', 1), ('12 yards', 1)]
        })
    elif 181 <= code_num <= 182:
        # Printing - very high recyclable (paper)
        config.update({
            'facility_uom': 'Area',
            'waste_dist': [5, 80, 15],
            'thresholds': [100, 250, 500, 1000],
            'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
        })

    # ============ CHEMICALS & PHARMACEUTICALS (191-210) ============
    elif 191 <= code_num <= 210:
        # High residual (chemical/hazardous waste)
        config.update({
            'facility_uom': 'Area',
            'waste_dist': [5, 25, 70],
            'thresholds': [100, 250, 500, 1000],
            'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
        })

    # ============ PLASTICS & RUBBER (221-222) ============
    elif 221 <= code_num <= 222:
        # Very high recyclable (plastic/rubber scraps)
        config.update({
            'facility_uom': 'Area',
            'waste_dist': [5, 75, 20],
            'thresholds': [100, 250, 500, 1000],
            'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
        })

    # ============ NON-METALLIC MINERALS (231-239) ============
    elif 231 <= code_num <= 239:
        # High residual (broken materials, dust)
        config.update({
            'facility_uom': 'Area',
            'waste_dist': [5, 35, 60],
            'thresholds': [250, 500, 1000, 2000],
            'containers': [('2 yards', 1), ('4 yards', 1), ('6 yards', 1), ('12 yards', 1)]
        })

    # ============ METALS (241-259) ============
    elif 241 <= code_num <= 259:
        # High recyclable (metal scraps)
        config.update({
            'facility_uom': 'Area',
            'waste_dist': [5, 65, 30],
            'thresholds': [250, 500, 1000, 2000],
            'containers': [('2 yards', 1), ('4 yards', 1), ('6 yards', 1), ('12 yards', 1)]
        })

    # ============ ELECTRONICS & MACHINERY (261-279) ============
    elif 261 <= code_num <= 279:
        # Medium recyclable (e-waste, metal, plastic)
        config.update({
            'facility_uom': 'Area',
            'waste_dist': [5, 60, 35],
            'thresholds': [100, 250, 500, 1000],
            'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
        })

    # ============ VEHICLES (291-309) ============
    elif 291 <= code_num <= 309:
        # High recyclable (metal, rubber, plastic)
        config.update({
            'facility_uom': 'Area',
            'waste_dist': [5, 65, 30],
            'thresholds': [250, 500, 1000, 2000],
            'containers': [('2 yards', 1), ('4 yards', 1), ('6 yards', 1), ('12 yards', 1)]
        })

    # ============ FURNITURE & OTHER MANUFACTURING (310-329) ============
    elif 310 <= code_num <= 329:
        if 'أثاث' in name or 'furniture' in name_lower:
            # Furniture - high recyclable (wood scraps)
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [10, 65, 25],
                'thresholds': [100, 250, 500, 1000],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })
        else:
            # Other manufacturing
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [10, 55, 35],
                'thresholds': [100, 250, 500, 1000],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })

    # ============ UTILITIES (351-390) ============
    elif 351 <= code_num <= 390:
        if 'كهرباء' in name or 'electricity' in name_lower:
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [5, 45, 50],
                'thresholds': [500, 1000, 2000, 5000],
                'containers': [('2 yards', 1), ('4 yards', 1), ('6 yards', 1), ('12 yards', 1)]
            })
        elif 'مياه' in name or 'water' in name_lower or 'صرف' in name:
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [15, 40, 45],  # Sludge, debris
                'thresholds': [500, 1000, 2000, 5000],
                'containers': [('2 yards', 1), ('4 yards', 1), ('6 yards', 1), ('12 yards', 1)]
            })
        else:
            # Waste collection - Daily: ~5-8L/m²/day processing waste
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [30, 40, 30],  # Mixed waste
                'thresholds': [1000, 2500, 5000, 10000],
                'containers': [('4 yards', 1), ('6 yards', 1), ('12 yards', 1), ('20 yards', 1)]
            })

    # ============ CONSTRUCTION (410-439) ============
    elif 410 <= code_num <= 439:
        # High residual (construction debris) - Daily basis
        config.update({
            'facility_uom': 'Area',
            'waste_dist': [5, 45, 50],  # Concrete, wood, metal
            'thresholds': [500, 1000, 2500, 5000],
            'containers': [('4 yards', 1), ('6 yards', 1), ('12 yards', 1), ('20 yards', 1)]
        })

    # ============ MOTOR VEHICLE TRADE (451-454) ============
    elif 451 <= code_num <= 454:
        # Vehicle sales - medium recyclable
        config.update({
            'facility_uom': 'Area',
            'waste_dist': [10, 55, 35],  # Parts, packaging
            'thresholds': [250, 500, 1000, 2000],
            'containers': [('2 yards', 1), ('4 yards', 1), ('6 yards', 1), ('12 yards', 1)]
        })

    # ============ RETAIL TRADE (471-479) ============
    elif 471 <= code_num <= 479:
        # High recyclable (packaging, cardboard) - Daily: ~0.5L/m²/day
        config.update({
            'facility_uom': 'Area',
            'waste_dist': [10, 65, 25],
            'thresholds': [100, 250, 500, 1000],
            'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
        })

    # ============ TRANSPORTATION & STORAGE (491-532) ============
    elif 491 <= code_num <= 532:
        if 'بريد' in name or 'post' in name_lower or 'توزيع' in name:
            # Postal - very high recyclable (paper)
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [5, 75, 20],
                'thresholds': [100, 250, 500, 1000],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })
        else:
            # Transportation - mixed waste
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [20, 45, 35],
                'thresholds': [250, 500, 1000, 2000],
                'containers': [('2 yards', 1), ('4 yards', 1), ('6 yards', 1), ('12 yards', 1)]
            })

    # ============ ACCOMMODATION & FOOD (551-563) ============
    elif 551 <= code_num <= 563:
        if 551 <= code_num <= 552:
            # Hotels - high organic (food waste) - Daily: ~10L/room/day
            config.update({
                'facility_uom': 'Number of Rooms',
                'waste_dist': [35, 40, 25],
                'thresholds': [10, 25, 50, 100],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })
        else:
            # Restaurants - very high organic - Daily: ~1.2L/m²/day
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [45, 30, 25],
                'thresholds': [50, 100, 200, 500],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })

    # ============ INFORMATION & COMMUNICATION (581-639) ============
    elif 581 <= code_num <= 639:
        # Very high recyclable (paper, e-waste)
        config.update({
            'facility_uom': 'Area',
            'waste_dist': [5, 75, 20],
            'thresholds': [100, 250, 500, 1000],
            'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
        })

    # ============ FINANCIAL & INSURANCE (641-663) ============
    elif 641 <= code_num <= 663:
        # Very high recyclable (paper-intensive) - Daily: ~0.2L/m²/day
        config.update({
            'facility_uom': 'Area',
            'waste_dist': [5, 75, 20],
            'thresholds': [100, 250, 500, 1000],
            'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
        })

    # ============ REAL ESTATE (681-682) ============
    elif 681 <= code_num <= 682:
        # Residential/Commercial buildings - Daily: ~3-5L/unit/day, 2-4 units/floor
        config.update({
            'facility_uom': 'Number of Floors',
            'waste_dist': [25, 35, 40],  # Household/office waste
            'thresholds': [5, 10, 20, 40],
            'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
        })

    # ============ PROFESSIONAL & TECHNICAL (691-750) ============
    elif 691 <= code_num <= 750:
        if 'محاماة' in name or 'محاسبة' in name or 'legal' in name_lower or 'accounting' in name_lower:
            # Law/Accounting - very high recyclable (paper) - Daily: ~0.15L/m²/day
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [5, 80, 15],
                'thresholds': [50, 100, 250, 500],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })
        elif 'هندسة' in name or 'engineering' in name_lower or 'معمارية' in name:
            # Engineering - high recyclable (paper, models)
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [10, 65, 25],
                'thresholds': [100, 250, 500, 1000],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })
        elif 'علمية' in name or 'بحوث' in name or 'scientific' in name_lower or 'research' in name_lower:
            # Research - high residual (lab waste)
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [10, 35, 55],
                'thresholds': [100, 250, 500, 1000],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })
        else:
            # Other professional services
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [10, 65, 25],
                'thresholds': [100, 250, 500, 1000],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })

    # ============ ADMINISTRATIVE & SUPPORT (771-829) ============
    elif 771 <= code_num <= 829:
        if 'توظيف' in name or 'employment' in name_lower:
            # Employment agencies - high recyclable (paper)
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [5, 70, 25],
                'thresholds': [50, 100, 250, 500],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })
        elif 'سفر' in name or 'سياحة' in name or 'travel' in name_lower:
            # Travel agencies - medium recyclable
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [15, 55, 30],
                'thresholds': [50, 100, 250, 500],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })
        elif 'تنظيف' in name or 'cleaning' in name_lower:
            # Cleaning services - mixed waste
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [30, 35, 35],
                'thresholds': [100, 250, 500, 1000],
                'containers': [('2 yards', 1), ('4 yards', 1), ('6 yards', 1), ('12 yards', 1)]
            })
        else:
            # Other administrative
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [15, 55, 30],
                'thresholds': [100, 250, 500, 1000],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })

    # ============ EDUCATION (851-855) ============
    elif 851 <= code_num <= 855:
        if 'ابتدائي' in name or 'primary' in name_lower or 'قبل' in name:
            # Primary/pre-primary - high recyclable (paper) - Daily: ~2L/class/day
            config.update({
                'facility_uom': 'Number of Classes',
                'waste_dist': [25, 55, 20],
                'thresholds': [5, 10, 20, 40],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })
        elif 'ثانوي' in name or 'secondary' in name_lower:
            # Secondary - high recyclable (paper) - Daily: ~3L/class/day
            config.update({
                'facility_uom': 'Number of Classes',
                'waste_dist': [20, 60, 20],
                'thresholds': [10, 20, 40, 80],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })
        else:
            # Higher/other education - high recyclable (paper)
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [15, 65, 20],
                'thresholds': [500, 1000, 2000, 5000],
                'containers': [('2 yards', 1), ('4 yards', 1), ('6 yards', 1), ('12 yards', 1)]
            })

    # ============ HEALTH (861-869) ============
    elif 861 <= code_num <= 869:
        if 'مستشفيات' in name or 'hospital' in name_lower:
            # Hospitals - high residual (medical waste) - Daily: ~5L/room/day
            config.update({
                'facility_uom': 'Number of Rooms',
                'waste_dist': [25, 20, 55],  # High medical/hazardous
                'thresholds': [20, 50, 100, 200],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })
        elif 'طبية' in name or 'medical' in name_lower or 'أسنان' in name:
            # Medical/Dental - high residual - Daily: ~3L/room/day
            config.update({
                'facility_uom': 'Number of Rooms',
                'waste_dist': [15, 25, 60],
                'thresholds': [5, 10, 20, 40],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })
        else:
            # Other health services
            config.update({
                'facility_uom': 'Number of Rooms',
                'waste_dist': [20, 30, 50],
                'thresholds': [10, 25, 50, 100],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })

    # ============ SOCIAL SERVICES (871-889) ============
    elif 871 <= code_num <= 889:
        # Social care - medium organic - Daily: ~5L/bed/day
        config.update({
            'facility_uom': 'Number of Beds',
            'waste_dist': [35, 35, 30],
            'thresholds': [10, 25, 50, 100],
            'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
        })

    # ============ ARTS & ENTERTAINMENT (900-920) ============
    elif 900 <= code_num <= 920:
        if 'مكتبات' in name or 'متاحف' in name or 'library' in name_lower or 'museum' in name_lower:
            # Libraries/Museums - high recyclable (paper)
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [10, 70, 20],
                'thresholds': [100, 250, 500, 1000],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })
        elif 'قمار' in name or 'gambling' in name_lower:
            # Gambling - medium waste
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [30, 40, 30],
                'thresholds': [250, 500, 1000, 2000],
                'containers': [('2 yards', 1), ('4 yards', 1), ('6 yards', 1), ('12 yards', 1)]
            })
        else:
            # Other arts/entertainment
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [20, 50, 30],
                'thresholds': [250, 500, 1000, 2000],
                'containers': [('2 yards', 1), ('4 yards', 1), ('6 yards', 1), ('12 yards', 1)]
            })

    # ============ SPORTS (931-932) ============
    elif 931 <= code_num <= 932:
        # High recyclable (bottles, cans)
        config.update({
            'facility_uom': 'Area',
            'waste_dist': [15, 60, 25],
            'thresholds': [500, 1000, 2000, 5000],
            'containers': [('2 yards', 1), ('4 yards', 1), ('6 yards', 1), ('12 yards', 1)]
        })

    # ============ MEMBERSHIP ORGANIZATIONS (941-960) ============
    elif 941 <= code_num <= 960:
        if 'دينية' in name or 'religious' in name_lower:
            # Religious organizations - medium waste
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [25, 45, 30],
                'thresholds': [100, 250, 500, 1000],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })
        elif 'سياسية' in name or 'political' in name_lower or 'نقابات' in name:
            # Political/Unions - high recyclable (paper)
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [10, 65, 25],
                'thresholds': [50, 100, 250, 500],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })
        else:
            # Other membership organizations
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [20, 50, 30],
                'thresholds': [100, 250, 500, 1000],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })

    # ============ REPAIR SERVICES (951-952) ============
    elif 951 <= code_num <= 952:
        # Medium recyclable (parts, packaging)
        config.update({
            'facility_uom': 'Area',
            'waste_dist': [10, 55, 35],
            'thresholds': [50, 100, 250, 500],
            'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
        })

    # ============ OTHER PERSONAL SERVICES (960-990) ============
    elif 960 <= code_num <= 990:
        if 'غسيل' in name or 'laundry' in name_lower or 'تنظيف' in name:
            # Laundry - medium waste
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [15, 50, 35],
                'thresholds': [50, 100, 250, 500],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })
        elif 'جمال' in name or 'تجميل' in name or 'beauty' in name_lower or 'salon' in name_lower:
            # Beauty salons - medium waste
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [10, 45, 45],
                'thresholds': [25, 50, 100, 250],
                'containers': [('240 Litre', 3), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })
        elif 'جنائزية' in name or 'funeral' in name_lower or 'مقابر' in name:
            # Funeral services - special waste
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [50, 20, 30],
                'thresholds': [50, 100, 250, 500],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })
        else:
            # Other personal services
            config.update({
                'facility_uom': 'Area',
                'waste_dist': [20, 45, 35],
                'thresholds': [50, 100, 250, 500],
                'containers': [('240 Litre', 1), ('2 yards', 1), ('4 yards', 1), ('6 yards', 1)]
            })

    return config


# Generate configurations
print("Generating intelligent configurations for 224 ISIC Groups...")
configurations = []

for idx, isic in enumerate(isic_groups, 1):
    try:
        config_params = analyze_industry(
            isic['name'],
            isic['code'],
            isic['category_name'],
            isic['description']
        )

        config = {
            "doctype": "Service Configuration",
            "naming_series": "CONF-",
            "service_type": "Commercial Waste",
            "isic_classification_category": "Group",
            "isic_classification": f"{isic['code']} - {isic['name']}",
            "facility_uom": config_params['facility_uom'],
            "calculate_facility_wastes_by": "Cluster Classification",
            "calculate_generation_rate_by": "Mean",
            "waste_distributions": [
                {
                    "doctype": "Waste Distribution",
                    "waste_type": "Organic Wastes",
                    "is_group": 1,
                    "distribution_percentage": float(config_params['waste_dist'][0])
                },
                {
                    "doctype": "Waste Distribution",
                    "waste_type": "Recyclable Wastes",
                    "is_group": 1,
                    "distribution_percentage": float(config_params['waste_dist'][1])
                },
                {
                    "doctype": "Waste Distribution",
                    "waste_type": "Residual Wastes",
                    "is_group": 1,
                    "distribution_percentage": float(config_params['waste_dist'][2])
                }
            ],
            "generation_classification": [
                {
                    "doctype": "Waste Generation Classification",
                    "max_threshold": config_params['thresholds'][i],
                    "container_type": config_params['containers'][i][0],
                    "count": config_params['containers'][i][1]
                }
                for i in range(4)
            ]
        }

        configurations.append(config)

        if idx % 25 == 0:
            print(
                f"Progress: {idx}/224 - {isic['code']} - {isic['category_name']}")

    except Exception as e:
        print(f"ERROR processing {isic['code']} - {isic['name']}: {str(e)}")

# Write to JSON file
output_file = '/tmp/service_configuration_data_full.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(configurations, f, ensure_ascii=False, indent=4)

print(f"\n{'='*60}")
print(f"✓ Generated {len(configurations)} configurations")
print(f"✓ Output file: {output_file}")
print(f"✓ Next step: Copy to naqel/data/demo/service_configuration_data.json")
print(f"{'='*60}")
