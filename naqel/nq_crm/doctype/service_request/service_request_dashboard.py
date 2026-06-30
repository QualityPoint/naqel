from frappe import _


def get_data():
    return {
        "fieldname": "service_order",
        "non_standard_fieldnames": {
            "Waste Quotation": "service_order",
        },
        "transactions": [
            {
                "label": _("Service Management"),
                "items": [
                    "Waste Quotation",
                ]
            }
        ],
    }
