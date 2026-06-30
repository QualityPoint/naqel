# Copyright (c) 2025, QuailtyPoint and contributors
# For license information, please see license.txt


import frappe
from frappe import _, qb
from frappe.utils import cint
from frappe.utils.nestedset import NestedSet


class ISICClassification(NestedSet):
    def autoname(self):
        """Set document name as: category_code - category_name"""
        if self.category_code and self.category_name:
            self.name = f"{self.category_code} - {self.category_name}"
        else:
            frappe.throw(
                _("Category Code and Category Name are required to generate document name"))

    def before_validate(self):
        self.clear_parent_category()
        self.set_is_group()

    def clear_parent_category(self):
        """Clear parent_category if classification is Section"""
        if self.category_classification == "Section":
            self.parent_category = None

    def set_is_group(self):
        """Set is_group based on category_classification"""
        if self.category_classification == "Activity":
            self.is_group = 0
        else:
            self.is_group = 1

    def validate(self):
        self.validate_activity_group()
        self.validate_parent_category_for_non_section()
        self.validate_parent_category_hierarchy()
        self.validate_category_code_per_category_class()
        self.validate_unique_category_name_per_category_class()

    def validate_activity_group(self):
        """Only Activity can be non-group, all others must be groups"""
        if self.is_group and self.category_classification == "Activity":
            frappe.throw(
                _("'Activity' classification cannot be a Group category."))

    def validate_parent_category_for_non_section(self):
        """All classifications except Section must have a parent"""
        if not self.parent_category and self.category_classification != "Section":
            frappe.throw(
                _("Only 'Section' classification can have no parent category."))

    def validate_parent_category_hierarchy(self):
        """Validate that parent category belongs to the correct level in hierarchy"""
        if not self.parent_category or self.category_classification == "Section":
            return

        expected_parent_class = PARENT_CLASSIFICATION.get(self.category_classification)

        if expected_parent_class:
            parent_doc = frappe.get_doc(
                "ISIC Classification", self.parent_category)

            # Check if parent has correct classification
            if parent_doc.category_classification != expected_parent_class:
                frappe.throw(
                    _(
                        "Parent Category must be of type '{0}' for a '{1}' classification. Selected parent is '{2}'."
                    ).format(
                        expected_parent_class,
                        self.category_classification,
                        parent_doc.category_classification,
                    )
                )

            # Check if parent is a group
            if not parent_doc.is_group:
                frappe.throw(
                    _("Parent Category must be a Group category. '{0}' is not a group.").format(
                        parent_doc.category_name
                    )
                )

    def validate_category_code_per_category_class(self):
        """Ensure category code is unique within the same classification"""
        if frappe.db.exists(
                "ISIC Classification",
                {
                    "category_classification": self.category_classification,
                    "category_code": self.category_code,
                    "name": ["!=", self.name],
                },
        ):
            frappe.throw(
                _("Category Code '{0}' already exists under Category '{1}'").format(
                    self.category_code, self.category_classification
                )
            )

    def validate_unique_category_name_per_category_class(self):
        """Ensure category name is unique within the same classification"""
        if frappe.db.exists(
                "ISIC Classification",
                {
                    "category_classification": self.category_classification,
                    "category_name": self.category_name,
                    "name": ["!=", self.name],
                },
        ):
            frappe.throw(
                _("Category Name '{0}' already exists under Category '{1}'").format(
                    self.category_name, self.category_classification
                )
            )


# Expected parent classification for each non-root level. Section is the root and
# has no parent, so it is intentionally absent.
PARENT_CLASSIFICATION = {
    "Division": "Section",
    "Group": "Division",
    "Category": "Group",
    "Activity": "Category",
}


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_parent_categories(doctype, txt, searchfield, start, page_len, filters):
    """Link-query for parent_category: only group nodes one level above the current
    classification are valid parents."""
    category_classification = (filters or {}).get("category_classification")
    expected_parent = PARENT_CLASSIFICATION.get(category_classification)
    if not expected_parent:
        return []

    isic = qb.DocType("ISIC Classification")
    return (
        frappe.qb.from_(isic)
        .select(isic.name, isic.category_name)
        .where(isic.category_classification == expected_parent)
        .where(isic.is_group == 1)
        .where(isic[searchfield].like(f"%{txt}%"))
        .orderby(isic.category_code)
        .limit(page_len)
        .offset(start)
        .run()
    )


@frappe.whitelist()
def get_children(doctype, parent=None, is_root=False, **kwargs):
    """
    Get children for tree view.
    Root nodes are Sections (which have no parent_category).
    """
    isic = qb.DocType("ISIC Classification")

    # Base query
    query = (
        frappe.qb.from_(isic)
        .select(isic.name.as_("value"), isic.is_group.as_("expandable"))
        .where(isic.docstatus < 2)
        .orderby(isic.category_code)
    )

    # Get root nodes (Sections) or children of a parent
    if is_root or not parent:
        query = query.where(
            (isic.parent_category.isnull()) | (
                isic.parent_category == "")
        )
    else:
        query = query.where(isic.parent_category == parent)
        query = query.select(isic.parent_category.as_("parent"))

    categories = query.run(as_dict=True)

    return categories
