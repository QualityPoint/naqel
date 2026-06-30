import { createApp } from "vue";
import WasteGenerationCalComponent from "../../../nq_setup/page/waste_generation_cal/components/Page.vue";

class WasteGenerationCal {
    constructor({ wrapper, page }) {
        this.$wrapper = $(wrapper);
        this.page = page;

        // --- own the Frappe page chrome (imperative side) ---
        this.page.clear_actions();
        this.page.clear_icons();
        this.page.clear_custom_actions();

        // --- boot Vue (reactive side) ---
        this.app = createApp(WasteGenerationCalComponent);
        SetVueGlobals(this.app);
        this.$component = this.app.mount(this.$wrapper.get(0));
    }

    destroy() {
        this.app?.unmount();
        this.app = null;
    }
}

frappe.provide("frappe.ui");
frappe.ui.WasteGenerationCal = WasteGenerationCal;
export default WasteGenerationCal;
