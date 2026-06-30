import frappe
from frappe import _


def validate_credential_types(
        doc,
        child_table_field="credentials",
        credential_type_field="credential_type",
        issue_date_field="issue_date",
        expiry_date_field="expiry_date",
):
    """Validate credential rows in a child table.

    Args:
            doc: The parent document.
            child_table_field: Field name of the child table on the parent doc.
            credential_type_field: Field name for the credential type within each row.
            issue_date_field: Field name for the issue date within each row.
            expiry_date_field: Field name for the expiry date within each row.
    """
    allowed = {"Identification Number", "License"}
    for row in doc.get(child_table_field) or []:
        cred_type = row.get(credential_type_field)
        if cred_type not in allowed:
            frappe.throw(
                _("Row #{0}: Credential Type must be one of: {1}. Got '{2}'.").format(
                    row.idx,
                    ", ".join(sorted(allowed)),
                    cred_type,
                ),
                title=_("Invalid Credential Type"),
            )

        issue_date = row.get(issue_date_field)
        expiry_date = row.get(expiry_date_field)
        if issue_date and expiry_date and expiry_date < issue_date:
            frappe.throw(
                _("Row #{0}: Expiry Date cannot be before Issue Date.").format(
                    row.idx),
                title=_("Invalid Credential Dates"),
            )


@frappe.whitelist()
def get_credential_config():
    """Return the facility credential policy from Service Settings.

    Shape:
        {
            "required": bool,         # requires_facility_credentials
            "upload_required": bool,  # upload_facility_credential
            "config": {credential_type: [document_types]},
        }

    The ``config`` map is only populated when credentials are required; otherwise
    it is empty so callers impose no credential restriction.
    """
    settings = frappe.get_single("Service Settings")
    required = bool(settings.requires_facility_credentials)

    config = {}
    if required:
        for row in settings.credentials:
            if row.credential_type:
                config.setdefault(row.credential_type, [])
                if row.document_type:
                    config[row.credential_type].append(row.document_type)

    return {
        "required": required,
        "upload_required": bool(settings.upload_facility_credential),
        "config": config,
    }
