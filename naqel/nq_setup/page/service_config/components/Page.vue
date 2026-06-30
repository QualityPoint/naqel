<template>
	<div class="sc-page">
		<ServiceConfigToolbar
			v-model:serviceType="serviceType"
			v-model:isicClassification="isicClassification"
			v-model:uom="uom"
			v-model:uomValue="uomValue"
			v-model:wasteCalcBy="wasteCalcBy"
			v-model:rateType="rateType"
			v-model:byWasteType="byWasteType"
			v-model:sortOrder="sortOrder"
			:loading="loading"
			:service-types-list="serviceTypesList"
			:uom-list="uomList"
			:show-by-waste-type-toggle="showByWasteTypeToggle"
			@refresh="loadChartData"
		/>
		<ChartCanvas
			:chart-data="chartData"
			:loading="loading"
			:data-revision="dataRevision"
			:by-waste-type="byWasteType"
			@edit="openEditor"
		/>
	</div>
</template>

<script setup>
import { ref, computed, onMounted, watch, createApp } from 'vue';
import ServiceConfigToolbar from './ServiceConfigToolbar.vue';
import ChartCanvas from './ChartCanvas.vue';
import ConfigEditor from './ConfigEditor.vue';

defineProps({
	frappePage: { type: Object, default: null },
});

// ── Filter state ─────────────────────────────────────────────────────────────
const serviceType        = ref('');
const isicClassification = ref('Section');
const uom                = ref('');
const uomValue           = ref(100);
const wasteCalcBy        = ref('generation_rate');
const rateType           = ref('mean');
const byWasteType        = ref(false);
const sortOrder          = ref('normal');

// ── Data state ───────────────────────────────────────────────────────────────
const loading          = ref(false);
const chartData        = ref([]);
const dataRevision     = ref(0);   // increments on every full reset; NOT on phase-2 append
const serviceTypesList = ref([]);
const uomList          = ref([]);

// Show the "Total | By Waste Type" toggle only when the selected Service Type
// carries multiple waste types (more than one row in its `wastes` table).
const showByWasteTypeToggle = computed(() =>
	!!serviceTypesList.value.find(s => s.name === serviceType.value)?.has_multiple_wastes
);

// Reset the toggle automatically when it becomes irrelevant.
watch(showByWasteTypeToggle, val => { if (!val) byWasteType.value = false; });

// ── Bootstrap: load dropdown lists ──────────────────────────────────────────
async function loadServiceTypes() {
	try {
		const r = await frappe.call({
			method: 'naqel.nq_setup.page.service_config.service_config.get_service_types',
		});
		serviceTypesList.value = r.message || [];
		if (serviceTypesList.value.length) serviceType.value = serviceTypesList.value[0].name;
	} catch (e) {
		console.warn('service-config: could not load service types', e);
	}
}

async function loadUoms() {
	try {
		const r = await frappe.call({
			method: 'naqel.nq_setup.page.service_config.service_config.get_uoms',
		});
		uomList.value = r.message || [];
		if (uomList.value.length) uom.value = uomList.value[0].name;
	} catch (e) {
		console.warn('service-config: could not load UOMs', e);
	}
}

// ── Two-phase chart loading ──────────────────────────────────────────────────
// A sequence counter guards against stale responses when filters change rapidly.
let chartSeq = 0;

async function loadChartData() {
	const seq = ++chartSeq;

	// ── Full reset ────────────────────────────────────────────────────────────
	loading.value    = true;
	chartData.value  = [];
	dataRevision.value++;          // tells ChartCanvas: reset zoom, don't preserve

	const args = {
		service_type:   serviceType.value        || null,
		isic_level:     isicClassification.value || null,
		uom:            uom.value                || null,
		uom_value:      uomValue.value           ?? 100,
		waste_calc_by:  wasteCalcBy.value,
		rate_type:      rateType.value,
		by_waste_type:  byWasteType.value ? 1 : 0,
		sort_order:     sortOrder.value,
	};

	// ── Phase 1: matched configs — render immediately ─────────────────────────
	try {
		const r1 = await frappe.call({
			method: 'naqel.nq_setup.page.service_config.service_config.get_chart_data',
			args: { ...args, matched_only: 1 },
		});
		if (seq !== chartSeq) return;           // stale — a newer request is running
		chartData.value = r1.message || [];
	} catch (e) {
		console.warn('service-config: phase 1 failed', e);
	} finally {
		if (seq === chartSeq) loading.value = false;
	}

	// ── Phase 2: unmatched configs — fire-and-forget, merge when ready ────────
	// Only runs when a specific UOM is selected (otherwise every config matches)
	if (!uom.value) return;

	frappe.call({
		method: 'naqel.nq_setup.page.service_config.service_config.get_chart_data',
		args: { ...args, matched_only: 0 },
		callback(r2) {
			if (seq !== chartSeq) return;       // stale
			const unmatched = r2.message || [];
			if (unmatched.length) {
				// Append — dataRevision stays the same so ChartCanvas preserves zoom
				chartData.value = [...chartData.value, ...unmatched];
			}
		},
	});
}

// ── Config editor dialog (Vue island inside a Frappe Dialog) ─────────────────
let editorApp = null;
let editorDialog = null;

function destroyEditor() {
	if (editorApp) { editorApp.unmount(); editorApp = null; }
	editorDialog = null;
}

function openEditor(name) {
	if (editorDialog) editorDialog.hide();

	editorDialog = new frappe.ui.Dialog({
		title: __('Service Configuration'),
		size: 'extra-large',
		fields: [{ fieldtype: 'HTML', fieldname: 'editor' }],
	});
	editorDialog.$wrapper.on('hidden.bs.modal', destroyEditor);
	editorDialog.show();

	const mountEl = editorDialog.get_field('editor').$wrapper.get(0);
	editorApp = createApp(ConfigEditor, {
		name,
		uomValue: uomValue.value,
		onSaved: () => loadChartData(),
		onClose: () => editorDialog?.hide(),
	});
	if (window.SetVueGlobals) window.SetVueGlobals(editorApp);
	editorApp.mount(mountEl);
}

// ── Lifecycle ────────────────────────────────────────────────────────────────
onMounted(async () => {
	await Promise.all([loadServiceTypes(), loadUoms()]);
	await loadChartData();
});

watch([serviceType, isicClassification, uom, uomValue, wasteCalcBy, rateType, byWasteType, sortOrder], loadChartData);
</script>

<style scoped>
.sc-page {
	display: flex;
	flex-direction: column;
	height: calc(100vh - 110px);
	width: 100%;
	overflow: hidden;
}
</style>
