from frappe import _


def get_data():
    return {
        "fieldname": "facility",
        "non_standard_fieldnames": {
            "Service Request": "facility",
            "Service Quotation": "facility",
        },
        "transactions": [
            {
                "label": _("Service Management"),
                "items": [
                    "Service Request",
                    "Service Quotation",
                ]
            }
        ],
    }
