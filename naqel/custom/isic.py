import frappe
from frappe import _
from frappe.desk.page.setup_wizard.setup_wizard import make_records
import csv
import os


def make_isic_fixtures():
    """Import ISIC classification data from CSV"""
    # Check if ISIC data already exists
    if frappe.db.count("ISIC Classification") > 0:
        print("ISIC Classification data already exists. Skipping import.")
        return

    # Find CSV file in doctype data folder
    csv_path = os.path.join(
        frappe.get_app_path("naqel"),
        "nq_setup",
        "doctype",
        "isic_classification",
        "data",
        "isic.csv"
    )

    if not os.path.exists(csv_path):
        print(f"ISIC CSV file not found at: {csv_path}")
        frappe.log_error(f"ISIC CSV file not found at: {csv_path}")
        return

    print("Starting ISIC Classification import...")
    process_isic_hierarchy(csv_path)
    print("ISIC Classification import completed!")


def process_isic_hierarchy(csv_path):
    """Process ISIC data ensuring parent records exist before children"""
    from collections import defaultdict

    # Group data by level
    level_data = defaultdict(list)

    try:
        # Try different encodings for CSV
        encodings = ['utf-8', 'utf-8-sig',
                     'cp1256', 'windows-1256', 'iso-8859-6']
        rows = None

        for encoding in encodings:
            try:
                with open(csv_path, 'r', encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)

                    # Verify we got readable data
                    if rows and rows[0].get('section_name'):
                        # Check if Arabic text is readable (not question marks)
                        sample_text = rows[0].get('section_name', '')
                        if sample_text and not sample_text.startswith('?'):
                            print(
                                f"Successfully read CSV with encoding: {encoding}")
                            break
            except (UnicodeDecodeError, UnicodeError):
                continue

        if not rows:
            frappe.throw(
                _("Failed to read CSV file with any supported encoding"))

        # Process rows and collect data by level
        for row in rows:
            # Collect unique records for each level
            add_to_level(level_data, row, 'Section')
            add_to_level(level_data, row, 'Division')
            add_to_level(level_data, row, 'Group')
            add_to_level(level_data, row, 'Category')
            add_to_level(level_data, row, 'Activity')

        # Create records in hierarchical order
        print(f"Creating {len(level_data['Section'])} Sections...")
        create_level_records(level_data['Section'], 'Section')

        print(f"Creating {len(level_data['Division'])} Divisions...")
        create_level_records(level_data['Division'], 'Division')

        print(f"Creating {len(level_data['Group'])} Groups...")
        create_level_records(level_data['Group'], 'Group')

        print(f"Creating {len(level_data['Category'])} Categories...")
        create_level_records(level_data['Category'], 'Category')

        print(f"Creating {len(level_data['Activity'])} Activities...")
        create_level_records(level_data['Activity'], 'Activity')

        frappe.db.commit()

    except Exception as e:
        print(f"Error in process_isic_hierarchy: {e}")
        frappe.log_error(f"Error importing ISIC data: {str(e)}")
        raise


def add_to_level(level_data, row, level):
    """Add unique record to level data"""
    level_mappings = {
        'Section': {
            'code_field': 'section_code',
            'name_field': 'section_name',
            'classification': 'Section'
        },
        'Division': {
            'code_field': 'division_code',
            'name_field': 'division_name',
            'classification': 'Division'
        },
        'Group': {
            'code_field': 'group_code',
            'name_field': 'group_name',
            'classification': 'Group'
        },
        'Category': {
            'code_field': 'category_code',
            'name_field': 'category_name',
            'classification': 'Category'
        },
        'Activity': {
            'code_field': 'activity_code',
            'name_field': 'activity_name',
            'classification': 'Activity'
        }
    }

    mapping = level_mappings[level]
    code = (row.get(mapping['code_field']) or '').strip()
    name = (row.get(mapping['name_field']) or '').strip()

    if not code or not name:
        return

    # Check if already added
    existing_codes = {r['category_code'] for r in level_data[level]}
    if code not in existing_codes:
        # Truncate name to prevent docname overflow
        # DocName format: "code - name" (max 140 chars)
        # Reserve: len(code) + 3 (" - ") = available for name
        max_name_length = 137 - len(code)  # 140 - 3 for " - "

        if len(name) > max_name_length:
            # Truncate at a safe point (avoid cutting mid-word if possible)
            name = name[:max_name_length].strip()
            # Remove any incomplete Arabic character at the end
            while name and ord(name[-1]) > 127 and len(name) > 0:
                # If last char is non-ASCII (Arabic), check if it's safe
                try:
                    # Try to encode it to verify it's complete
                    name.encode('utf-8')
                    break
                except UnicodeEncodeError:
                    name = name[:-1]

        level_data[level].append({
            'category_code': code,
            'category_name': name,
            'category_classification': mapping['classification'],
            'description': (row.get('description') or '').strip(),
            'parent_info': get_parent_info(row, level)
        })


def get_parent_info(row, level):
    """Get parent information for the current level"""
    parent_mappings = {
        'Division': ('section_code', 'section_name'),
        'Group': ('division_code', 'division_name'),
        'Category': ('group_code', 'group_name'),
        'Activity': ('category_code', 'category_name')
    }

    if level not in parent_mappings:
        return None

    parent_code_field, parent_name_field = parent_mappings[level]
    parent_code = (row.get(parent_code_field) or '').strip()
    parent_name = (row.get(parent_name_field) or '').strip()

    if not parent_code or not parent_name:
        return None

    # Apply same truncation logic as main records
    max_parent_name_length = 137 - len(parent_code)
    if len(parent_name) > max_parent_name_length:
        parent_name = parent_name[:max_parent_name_length].strip()
        # Clean incomplete Arabic characters
        while parent_name and ord(parent_name[-1]) > 127:
            try:
                parent_name.encode('utf-8')
                break
            except UnicodeEncodeError:
                parent_name = parent_name[:-1]

    return {'code': parent_code, 'name': parent_name}


def create_level_records(records, level):
    """Create records for a specific level"""
    created_count = 0
    skipped_count = 0

    for record in records:
        try:
            # Construct document name
            doc_name = f"{record['category_code']} - {record['category_name']}"

            # Check if already exists
            if frappe.db.exists("ISIC Classification", doc_name):
                skipped_count += 1
                continue

            # Find parent if needed
            parent_name = None
            if record['parent_info']:
                parent_code = record['parent_info']['code']
                parent_name = f"{parent_code} - {record['parent_info']['name']}"
                # No need to check if parent exists - it's guaranteed by processing order!

            # Prepare document data
            doc_record = {
                "doctype": "ISIC Classification",
                "category_classification": record['category_classification'],
                "category_code": record['category_code'],
                "category_name": record['category_name'],
                "description": record['description'] if record['description'] else None,
                "is_group": 0 if record['category_classification'] == 'Activity' else 1,
            }

            if parent_name:
                doc_record["parent_category"] = parent_name

            # Create record
            make_records([doc_record])
            created_count += 1

        except Exception as e:
            frappe.log_error(
                f"Error creating {level} {record['category_code']}: {str(e)}",
                "ISIC Import Error"
            )
            skipped_count += 1
            continue

    print(f"  {level}: Created {created_count}, Skipped {skipped_count}")
