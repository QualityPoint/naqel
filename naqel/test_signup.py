import frappe
from frappe.utils import validate_email_address

def test():
    email = "testsignup@naqel.com"
    full_name = "Test Sign Up"
    phone = "0512345678"
    password = "securepassword"
    
    validate_email_address(email, throw=True)
    if frappe.db.exists("User", email):
        frappe.delete_doc("User", email, force=True)
        frappe.db.commit()
        print("Deleted old user")
        
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
    print("Created User")
    
    # 2. Force create contact
    from frappe.core.doctype.user.user import create_contact
    create_contact(user, ignore_mandatory=True)
    print("Created Contact")
    
    # 3. Create Lead
    lead = frappe.get_doc({
        "doctype": "Lead",
        "lead_name": full_name,
        "email_id": email,
        "mobile_no": phone,
        "first_name": first_name,
        "last_name": last_name,
        "status": "Lead"
    })
    lead.flags.ignore_permissions = True
    lead.insert()
    print("Created Lead")
    
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
        print("Linked Lead to Contact")
    else:
        print("Contact not found for linking!")
        
    frappe.db.commit()
    print("Success")

