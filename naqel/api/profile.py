import frappe
from frappe import _

@frappe.whitelist()
def get_profile():
    if frappe.session.user == "Guest":
        frappe.throw(_("Not logged in"))
        
    user = frappe.get_doc("User", frappe.session.user)
    
    # Get Contact
    from frappe.contacts.doctype.contact.contact import get_contact_name
    contact_name = get_contact_name(user.email)
    
    emails = []
    phones = []
    
    if contact_name:
        contact = frappe.get_doc("Contact", contact_name)
        for e in contact.email_ids:
            emails.append({"email_id": e.email_id, "is_primary": e.is_primary})
        for p in contact.phone_nos:
            phones.append({"phone": p.phone, "is_primary_phone": p.is_primary_phone, "is_primary_mobile_no": p.is_primary_mobile_no})
    else:
        # Fallback if no contact found
        emails.append({"email_id": user.email, "is_primary": 1})
        if user.mobile_no:
            phones.append({"phone": user.mobile_no, "is_primary_mobile_no": 1, "is_primary_phone": 0})
        elif user.phone:
            phones.append({"phone": user.phone, "is_primary_phone": 1, "is_primary_mobile_no": 0})
            
    return {
        "first_name": user.first_name,
        "middle_name": user.middle_name,
        "last_name": user.last_name,
        "gender": user.gender,
        "emails": emails,
        "phones": phones,
        "user_image": user.user_image
    }

@frappe.whitelist()
def update_profile(data):
    if frappe.session.user == "Guest":
        frappe.throw(_("Not logged in"))
        
    if isinstance(data, str):
        import json
        data = json.loads(data)
        
    user = frappe.get_doc("User", frappe.session.user)
    
    # Ensure primary email isn't modified
    primary_email = user.email
    
    # Find primary mobile and phone from the data
    primary_mobile = ""
    primary_phone = ""
    for p in data.get("phones", []):
        if p.get("is_primary_mobile_no"):
            primary_mobile = p.get("phone")
        if p.get("is_primary_phone"):
            primary_phone = p.get("phone")
            
    # Step 1: Update User
    user.first_name = data.get("first_name")
    user.middle_name = data.get("middle_name")
    user.last_name = data.get("last_name")
    user.gender = data.get("gender")
    user.mobile_no = primary_mobile
    user.phone = primary_phone
    user.flags.ignore_permissions = True
    user.save()
    
    # Step 2: Force-Sync Contact
    from frappe.contacts.doctype.contact.contact import get_contact_name
    contact_name = get_contact_name(user.email)
    if contact_name:
        contact = frappe.get_doc("Contact", contact_name)
        
        # Frappe misses middle_name in default sync
        contact.middle_name = data.get("middle_name")
        
        # Wipe and rebuild emails (ensuring primary email is kept)
        contact.set("email_ids", [])
        has_primary_email = False
        for e in data.get("emails", []):
            if e.get("email_id") == primary_email:
                contact.append("email_ids", {"email_id": primary_email, "is_primary": 1})
                has_primary_email = True
            else:
                contact.append("email_ids", {"email_id": e.get("email_id"), "is_primary": 0})
        
        if not has_primary_email:
            contact.append("email_ids", {"email_id": primary_email, "is_primary": 1})
            
        # Wipe and rebuild phones
        contact.set("phone_nos", [])
        for p in data.get("phones", []):
            contact.append("phone_nos", {
                "phone": p.get("phone"),
                "is_primary_phone": p.get("is_primary_phone", 0),
                "is_primary_mobile_no": p.get("is_primary_mobile_no", 0)
            })
            
        contact.flags.ignore_permissions = True
        contact.save()
        
        # Step 3: Sync Lead Document
        lead_name_link = None
        for link in contact.links:
            if link.link_doctype == "Lead":
                lead_name_link = link.link_name
                break
                
        if lead_name_link:
            lead = frappe.get_doc("Lead", lead_name_link)
            lead.first_name = user.first_name
            lead.middle_name = user.middle_name
            lead.last_name = user.last_name
            
            # Reconstruct lead_name
            full_name = " ".join(filter(None, [user.first_name, user.middle_name, user.last_name]))
            if not full_name:
                full_name = user.email.split("@")[0]
            lead.lead_name = full_name
            lead.gender = user.gender
            lead.mobile_no = user.mobile_no
            lead.phone = user.phone
            
            lead.flags.ignore_permissions = True
            lead.save()
            
    frappe.db.commit()
    return {"success": True, "message": _("Profile updated successfully")}


@frappe.whitelist()
def update_avatar(file_url):
    if frappe.session.user == "Guest":
        frappe.throw(_("Not logged in"))

    user = frappe.get_doc("User", frappe.session.user)
    user.user_image = file_url
    user.flags.ignore_permissions = True
    user.save()
    frappe.db.commit()
    return {"success": True}
