frappe.pages['service-config'].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Service Configuration'),
		single_column: true,
	});

	// hot reload in development
	if (frappe.boot.developer_mode) {
		frappe.hot_update = frappe.hot_update || [];
		frappe.hot_update.push(() => load_service_config(wrapper));
	}
};

frappe.pages['service-config'].on_page_show = function (wrapper) {
	// Re-register the breadcrumb for this Page on every show (Frappe sets a page's
	// breadcrumb only once, keyed by route — mirrors print.js).
	frappe.breadcrumbs.add({
		type: "Custom",
		label: __("Service Configuration"),
		route: "service-config",
	});
	pin_sidebar();
	load_service_config(wrapper);
};

// Keep the desk Workspace Sidebar in sync. Frappe resolves the active sidebar
// reliably for DocType routes but not for this Page: its module ("NQ Setup")
// doesn't equal the sidebar title ("Naqel Setup"), so the module fallback misses
// and the active item isn't reliably highlighted. Pin it explicitly.
function pin_sidebar() {
	const sb = frappe.app?.sidebar;
	if (!sb) return;
	if (sb.sidebar_title !== "Naqel Setup") sb.setup("Naqel Setup");
	sb.set_active_workspace_item();
}

frappe.pages['service-config'].on_page_hide = function () {
	frappe.service_config?.destroy?.();
	frappe.service_config = null;
};

function load_service_config(wrapper) {
	let $parent = $(wrapper).find('.layout-main-section');

	// tear down any previous instance before re-mounting
	frappe.service_config?.destroy?.();
	frappe.service_config = null;
	$parent.empty();

	frappe.require('service_config.bundle.js').then(() => {
		frappe.service_config = new frappe.ui.ServiceConfig({
			wrapper: $parent,
			page: wrapper.page,
		});
	});
}
