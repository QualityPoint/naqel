import { createApp } from "vue";
import ServiceConfigComponent from "../../../nq_setup/page/service_config/components/Page.vue";

class ServiceConfig {
    constructor({ wrapper, page }) {
        this.$wrapper = $(wrapper);
        this.page = page;

        // --- own the Frappe page chrome (imperative side) ---
        this.page.clear_actions();
        this.page.clear_icons();
        this.page.clear_custom_actions();

        // --- boot Vue (reactive side) ---
        this.app = createApp(ServiceConfigComponent);
        SetVueGlobals(this.app);
        this.$component = this.app.mount(this.$wrapper.get(0));
    }

    destroy() {
        this.app?.unmount();
        this.app = null;
    }
}

frappe.provide("frappe.ui");
frappe.ui.ServiceConfig = ServiceConfig;
export default ServiceConfig;
