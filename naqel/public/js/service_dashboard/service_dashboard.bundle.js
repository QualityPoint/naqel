// Service Dashboard bundle entry — the class that boots Vue (Pattern 3).
// Lazy-loaded by the page controller via frappe.require; it owns the Frappe page
// chrome (title, refresh action) and mounts the Vue app, exposing destroy() for the
// page controller to call on hide.

import { createApp } from 'vue';
import App from './components/App.vue';
import { createDashboardStore } from './store';

class ServiceDashboard {
	constructor({ wrapper, page }) {
		this.$wrapper = $(wrapper);
		this.page = page;
		this.store = createDashboardStore();

		// Page chrome — a Refresh action wired to the store.
		this.page.set_secondary_action(__('Refresh'), () => this.store.refresh(), 'refresh');

		this.app = createApp(App);
		if (window.SetVueGlobals) window.SetVueGlobals(this.app); // inject `frappe` + `__`
		this.app.provide('store', this.store);
		this.$component = this.app.mount(this.$wrapper.get(0));
	}

	destroy() {
		this.app?.unmount();
		this.app = null;
	}
}

frappe.provide('frappe.ui');
frappe.ui.ServiceDashboard = ServiceDashboard;
export default ServiceDashboard;
