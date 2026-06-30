frappe.pages['containers'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Containers',
		single_column: true
	});
}