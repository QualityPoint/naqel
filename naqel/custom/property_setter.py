import frappe
from frappe.custom.doctype.property_setter.property_setter import delete_property_setter, make_property_setter


def property_setter():
	"""Create property setters for customizing DocTypes and fields."""

	return [
		# Address
		{
		    "doctype": "Address",
		    "fieldname": "county",
		    "property": "hidden",
		    "value": "1",
		    "property_type": "Check",
		    "for_doctype": False,
		},
		{
		    "doctype": "Address",
		    "fieldname": "state",
		    "property": "hidden",
		    "value": "1",
		    "property_type": "Check",
		    "for_doctype": False,
		},
	]


def create_property_setter():
	"""Create property setters based on the definitions in property_setter()."""

	for prop in property_setter():
		make_property_setter(
			prop["doctype"],
			prop["fieldname"],
			prop["property"],
			prop["value"],
			prop["property_type"],
			for_doctype=prop.get("for_doctype"),
			validate_fields_for_doctype=False,
		)


def remove_property_setter(doctype, fieldname, property):
	"""Delete a property setter."""

	for prop in property_setter():
		delete_property_setter(
			prop["doctype"],
			prop["property"],
			prop["fieldname"],
		)


def get_meta_field_options(doctype, fieldname, custom_options):
	"""Get original options and add custom ones without duplicates."""
	meta = frappe.get_meta(doctype)
	original_options = meta.get_field(fieldname).options or ""

	all_options = original_options.split("\n") + custom_options

	# Remove duplicates while preserving order
	unique_options = []
	for option in all_options:
		if option and option not in unique_options:
			unique_options.append(option)

	return "\n" + "\n".join(unique_options)
