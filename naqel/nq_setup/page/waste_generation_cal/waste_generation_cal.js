frappe.pages['waste-generation-cal'].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Waste Calculator'),
		single_column: true,
	});

	// hot reload in development
	if (frappe.boot.developer_mode) {
		frappe.hot_update = frappe.hot_update || [];
		frappe.hot_update.push(() => load_waste_generation_cal(wrapper));
	}
};

frappe.pages['waste-generation-cal'].on_page_show = function (wrapper) {
	load_waste_generation_cal(wrapper);
};

frappe.pages['waste-generation-cal'].on_page_hide = function () {
	frappe.waste_generation_cal?.destroy?.();
	frappe.waste_generation_cal = null;
};

function load_waste_generation_cal(wrapper) {
	let $parent = $(wrapper).find('.layout-main-section');

	// tear down any previous instance before re-mounting
	frappe.waste_generation_cal?.destroy?.();
	frappe.waste_generation_cal = null;
	$parent.empty();

	frappe.require('waste_generation_cal.bundle.js').then(() => {
		frappe.waste_generation_cal = new frappe.ui.WasteGenerationCal({
			wrapper: $parent,
			page: wrapper.page,
		});
	});
}