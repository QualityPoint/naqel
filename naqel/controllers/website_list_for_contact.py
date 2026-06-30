# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import frappe
from frappe import _


def add_role_for_portal_user(portal_user, role):
    """When a new portal user is added, give appropriate roles to user if
    posssible, else warn user to add roles."""
    if not portal_user.is_new():
        return

    user_doc = frappe.get_doc("User", portal_user.user)
    roles = {r.role for r in user_doc.roles}

    if role in roles:
        return

    if "System Manager" not in frappe.get_roles():
        frappe.msgprint(
            _("Please add {1} role to user {0}.").format(
                portal_user.user, role),
            alert=True,
        )
        return

    user_doc.add_roles(role)
    frappe.msgprint(_("Added {1} Role to User {0}.").format(
        frappe.bold(user_doc.name), role), alert=True)
