app_name = "naqel"
app_title = "Naqel"
app_publisher = "QualityPoint"
app_description = "Naqel — Complete Waste Management solution for agreements, contracts, collection and compliance on Frappe."
app_email = "erp@qp.sa"
app_license = "gpl-3.0"
# app_logo_url = "/assets/erpnext/images/logo.svg"
app_home = "/naqel"

# Apps
# ------------------

required_apps = ["erpnext"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
#     {
#         "name": "naqel",
#         "logo": "/assets/naqel/images/logo.svg",
#                 "title": app_title,
#                 "route": app_home,
#                 "has_permission": "naqel.api.permission.has_app_permission"
#     }
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = [
    "/assets/naqel/css/naqel.css",
]
app_include_js = [
    "address.bundle.js",
    "naqel.bundle.js",
]

# include js, css files in header of web template
# web_include_css = "/assets/naqel/css/naqel.css"
# web_include_js = "/assets/naqel/js/naqel.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "naqel/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "naqel/public/icons.svg"

# Home Pages
# ----------

# home_page = "frontend"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
jinja = {
    "methods": ["naqel.utils.contract.jinja_methods"],
}

# Installation
# ------------

# before_install = "naqel.install.before_install"
after_install = "naqel.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "naqel.uninstall.before_uninstall"
# after_uninstall = "naqel.uninstall.after_uninstall"

# Site Migration
# --------------

# before_migrate = "naqel.install.before_install"
after_migrate = "naqel.install.after_install"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "naqel.utils.before_app_install"
# after_app_install = "naqel.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "naqel.utils.before_app_uninstall"
# after_app_uninstall = "naqel.utils.after_app_uninstall"

# Boot
# ----
# Extend the desk bootinfo handed to every client (see naqel/boot.py).
extend_bootinfo = "naqel.boot.boot_session"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "naqel.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

permission_query_conditions = {
    "Facility": "naqel.nq_crm.doctype.facility.facility.get_permission_query_conditions",
}

has_permission = {
    "Facility": "naqel.nq_crm.doctype.facility.facility.has_permission",
}

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }
override_doctype_class = {
    "Company": "naqel.overrides.company.NaqelCompany",
    "Project": "naqel.overrides.project.NaqelProject",
}
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "Address": {
        "validate": "naqel.overrides.address.validate",
    },
    "Payment Entry": {
        "on_submit": "naqel.overrides.payment_entry.update_contract_payment_status",
        "on_cancel": "naqel.overrides.payment_entry.update_contract_payment_status",
    },
    "Journal Entry": {
        "on_submit": "naqel.overrides.journal_entry.update_contract_payment_status_from_je",
        "on_cancel": "naqel.overrides.journal_entry.update_contract_payment_status_from_je",
    },
    "Sales Order": {
        "on_submit": "naqel.overrides.sales_order.update_service_quotation_status",
        "on_cancel": "naqel.overrides.sales_order.update_service_quotation_status",
    },
}

# Scheduled Tasks
# ---------------

scheduler_events = {
    "daily": [
        "naqel.nq_crm.doctype.service_quotation.service_quotation.set_expired_status",
        "naqel.utils.contract.payment.update_overdue_installments",
        "naqel.utils.contract.contract_status.update_status_for_contracts",
    ],
}

# Testing
# -------

# before_tests = "naqel.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "naqel.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "naqel.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["naqel.utils.before_request"]
# after_request = ["naqel.utils.after_request"]

# Job Events
# ----------
# before_job = ["naqel.utils.before_job"]
# after_job = ["naqel.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"naqel.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# website_route_rules = []
