// Service Dashboard — Pattern 3 (lazy bundle + shared store).
// The page controller is a plain script; it lazy-loads the compiled Vue bundle via
// frappe.require (cached after first open) and instantiates the bundle class, which
// boots Vue and drives the page chrome. No CustomEvent / window.* bridge needed.

frappe.pages['service-dashboard'].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Service Dashboard'),
		single_column: true,
	});

	// Dev hot reload: re-mount when the bundle changes (bench build --hard-link).
	if (frappe.boot.developer_mode) {
		frappe.hot_update = frappe.hot_update || [];
		frappe.hot_update.push(() => load_dashboard(wrapper));
	}
};

// on_page_show fires every time the page is shown; pair it with on_page_hide teardown.
frappe.pages['service-dashboard'].on_page_show = function (wrapper) {
	load_dashboard(wrapper);
};

frappe.pages['service-dashboard'].on_page_hide = function () {
	frappe.service_dashboard?.destroy?.();
	frappe.service_dashboard = null;
};

function load_dashboard(wrapper) {
	const $parent = $(wrapper).find('.layout-main-section');
	$parent.empty(); // clear before (re-)mount

	frappe.require('service_dashboard.bundle.js').then(() => {
		frappe.service_dashboard = new frappe.ui.ServiceDashboard({
			wrapper: $parent,
			page: wrapper.page,
		});
	});
}
