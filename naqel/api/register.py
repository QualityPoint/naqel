import frappe
from frappe import _
from frappe.utils import validate_email_address

@frappe.whitelist(allow_guest=True, methods=["POST"])
def signup(email, full_name, phone, password):
    validate_email_address(email, throw=True)
    if frappe.db.exists("User", email):
        frappe.throw(_("User account already exists. Please login instead."))
        
    # Split full_name
    parts = full_name.strip().split()
    first_name = parts[0]
    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
    
    # 1. Create User
    user = frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "mobile_no": phone,
        "enabled": 1,
        "user_type": "Website User",
        "send_welcome_email": 0
    })
    user.flags.ignore_permissions = True
    user.insert()
    
    from frappe.utils.password import update_password
    update_password(user=email, pwd=password)
    
    # 2. Force create contact immediately (since User's on_update enqueues it asynchronously)
    from frappe.core.doctype.user.user import create_contact as create_user_contact
    create_user_contact(user, ignore_mandatory=True)
    
    # 3. Create Lead
    lead = frappe.get_doc({
        "doctype": "Lead",
        "lead_name": full_name,
        "email_id": email,
        "mobile_no": phone,
        "first_name": first_name,
        "last_name": last_name,
        "status": "Lead" # Standard CRM status
    })
    lead.flags.ignore_permissions = True
    lead.insert()
    
    # 4. Link Lead to Contact
    from frappe.contacts.doctype.contact.contact import get_contact_name
    contact_name = get_contact_name(email)
    if contact_name:
        contact = frappe.get_doc("Contact", contact_name)
        contact.append("links", {
            "link_doctype": "Lead",
            "link_name": lead.name
        })
        contact.flags.ignore_permissions = True
        contact.save()
        
    frappe.db.commit()
    
    return {
        "success": True,
        "message": _("User created successfully")
    }
