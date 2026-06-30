# Copyright (c) 2025, QualityPoint and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils.nestedset import NestedSet

# Fixed division hierarchy, ordered root -> leaf. The single source of truth for
# every parent/child rule below.
#   - Province is a root level: it has no parent (multiple Province roots allowed).
#   - City / Municipality / District each sit directly under the level above.
#   - District is the leaf level (never a group).
DIVISION_HIERARCHY = ("Province", "City", "Municipality", "District")
LEAF_CATEGORY = DIVISION_HIERARCHY[-1]


def parent_category(category):
    """Category one level above `category`; None for the root or an unknown level."""
    if category not in DIVISION_HIERARCHY:
        return None
    index = DIVISION_HIERARCHY.index(category)
    return DIVISION_HIERARCHY[index - 1] if index > 0 else None


def child_category(category):
    """Category one level below `category`; None for the leaf or an unknown level."""
    if category not in DIVISION_HIERARCHY:
        return None
    index = DIVISION_HIERARCHY.index(category)
    return DIVISION_HIERARCHY[index + 1] if index + 1 < len(DIVISION_HIERARCHY) else None


class AddressDivision(NestedSet):
    nsm_parent_field = "parent_division"

    def validate(self):
        # division_category is mandatory; bail out cleanly if it is missing (or an
        # unknown legacy value) and let the standard mandatory/options check report it.
        if self.division_category not in DIVISION_HIERARCHY:
            return
        # is_group is derived: only the leaf (District) is a non-group; every higher
        # level is a group so it can hold children.
        self.is_group = 0 if self.division_category == LEAF_CATEGORY else 1
        self.validate_parent_division()

    def validate_parent_division(self):
        expected_parent = parent_category(self.division_category)

        # Root level (Province): must not have a parent.
        if expected_parent is None:
            if self.parent_division:
                frappe.throw(
                    _("A {0} is a root division and cannot have a Parent Division.").format(
                        _(self.division_category)
                    )
                )
            return

        # Deeper levels: a parent of the level directly above is mandatory.
        if not self.parent_division:
            frappe.throw(
                _("A {0} must have a {1} as its Parent Division.").format(
                    _(self.division_category), _(expected_parent)
                )
            )

        parent = frappe.db.get_value(
            "Address Division", self.parent_division,
            ["division_category", "country"], as_dict=True,
        )
        if parent.division_category != expected_parent:
            frappe.throw(
                _("Parent Division of a {0} must be a {1}, not a {2}.").format(
                    _(self.division_category), _(expected_parent), _(parent.division_category)
                )
            )
        if parent.country != self.country:
            frappe.throw(_("Parent Division must belong to the same country."))

    # on_update / on_trash are intentionally inherited from NestedSet:
    #   - on_update keeps the tree (lft/rgt) in sync WITHOUT validate_one_root, so
    #     multiple Province roots are allowed (like Employee).
    #   - on_trash blocks deleting a division that still has children.


@frappe.whitelist()
def get_parent_division_category(division_category):
    """The category that a division of `division_category` must be parented under."""
    return parent_category(division_category)


@frappe.whitelist()
def get_child_node_info(parent):
    """Tree 'Add Child' dialog data: the parent's country and the single child
    category allowed beneath it."""
    parent_doc = frappe.db.get_value(
        "Address Division", parent, ["division_category", "country"], as_dict=True
    )
    if not parent_doc:
        frappe.throw(_("Parent Division '{0}' not found").format(parent))

    child = child_category(parent_doc.division_category)
    return {
        "country": parent_doc.country,
        "child_division_types": [child] if child else [],
    }


@frappe.whitelist()
def add_node():
    args = frappe.form_dict
    parent = args.get("parent") or ""
    if parent == "Address Division":
        parent = ""

    # is_group is derived in validate(), so it is not set here.
    doc = frappe.get_doc({
        "doctype": "Address Division",
        "division_name": args.get("division_name"),
        "parent_division": parent or None,
        "division_category": args.get("division_category"),
        "country": args.get("country"),
    })
    doc.save()
    return doc.name


@frappe.whitelist()
def get_children(doctype, parent=None, country=None, division_category=None, is_root=False, is_tree=False):
    filters = [["parent_division", "=", "" if (is_root or not parent or parent == "Address Division") else parent]]
    if country and country != "All Countries":
        filters.append(["country", "=", country])
    if division_category:
        filters.append(["division_category", "=", division_category])

    divisions = frappe.get_list(
        doctype,
        fields=["name as value", "division_name as title", "is_group", "division_category"],
        filters=filters,
        order_by="name",
    )
    for division in divisions:
        division.expandable = 1 if division.is_group else 0

    return divisions
