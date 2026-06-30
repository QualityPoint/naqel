<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import EqualizerCanvas from './EqualizerCanvas.vue';

const __ = (s) => (window.__ ? window.__(s) : s);

const props = defineProps({
	name: { type: String, required: true },
	uomValue: { type: Number, default: 100 },
	onSaved: { type: Function, default: null },
	onClose: { type: Function, default: null },
});

const M = 'naqel.nq_setup.page.service_config.service_config';

const loading = ref(true);
const saving = ref(false);
const errorMsg = ref('');
const activeTab = ref('classification');
const tabs = [
	{ id: 'uoms', label: 'UOMs' },
	{ id: 'classification', label: 'Classification' },
	{ id: 'settings', label: 'Settings' },
	{ id: 'ratings', label: 'Ratings' },
];

const config = reactive({
	name: props.name, title: '', facility_uom: '', default_volume_unit: '',
	uoms: [], generation_classification: [],
	calculate_facility_wastes_by: 'Generation Rate',
	calculate_generation_rate_by: 'Mean',
	allocate_container_for_each_waste_type: 0,
	ratings: [], stats: {}, can_write: false,
});
const options = reactive({ facility_uoms: [], container_types: [] });
const preview = ref({});
const baselineWaste = ref(null);

const canWrite = computed(() => !!config.can_write);
const readOnly = computed(() => !canWrite.value);
const flt = (v) => (typeof v === 'number' ? v : parseFloat(v) || 0);
const fmt = (v) => {
	const n = flt(v);
	return Number.isFinite(n) ? n.toFixed(2) : '--';
};
const unitLabel = computed(() => preview.value.default_volume_unit || config.default_volume_unit || '');

// Selected Facility UOM's preferences (drives the X-axis label + whole/fraction rule).
const facilityUomMeta = computed(() => options.facility_uoms.find((u) => u.name === config.facility_uom) || {});
const uomLabel = computed(() => facilityUomMeta.value.default_uom || config.facility_uom || '');
const wholeThreshold = computed(() => !!facilityUomMeta.value.must_be_whole_number);

// ── Load ──────────────────────────────────────────────────────────────────────
onMounted(async () => {
	try {
		const [opt, cfg] = await Promise.all([
			frappe.call(`${M}.get_editor_options`),
			frappe.call(`${M}.get_config_for_edit`, { name: props.name }),
		]);
		Object.assign(options, opt.message || {});
		Object.assign(config, cfg.message || {});
		await runSimulate();
		baselineWaste.value = flt(preview.value.calculated_waste);
	} catch (e) {
		errorMsg.value = (e && e.message) || __('Failed to load the configuration');
	} finally {
		loading.value = false;
	}
});

// ── Simulate (debounced live preview) ────────────────────────────────────────
let simTimer = null;
const scheduleSimulate = () => {
	clearTimeout(simTimer);
	simTimer = setTimeout(runSimulate, 200);
};

async function runSimulate() {
	try {
		const r = await frappe.call(`${M}.simulate_config`, {
			payload: JSON.stringify(config),
			uom_value: props.uomValue,
		});
		const res = r.message || {};
		preview.value = res;
		// Merge recomputed volumes back so the equalizer heights are accurate.
		if (Array.isArray(res.generation_classification)) {
			res.generation_classification.forEach((b, i) => {
				if (config.generation_classification[i]) {
					config.generation_classification[i].total_converted_volume = b.total_converted_volume;
					config.generation_classification[i].container_standard_volume = b.container_standard_volume;
					config.generation_classification[i].container_volume_unit = b.container_volume_unit;
				}
			});
		}
		if (res.stats) config.stats = res.stats;
	} catch (e) {
		errorMsg.value = (e && e.message) || __('Simulation failed');
	}
}

// ── Band ops ──────────────────────────────────────────────────────────────────
function addBand() {
	const def = options.container_types[0];
	const lastThr = Math.max(0, ...config.generation_classification.map((b) => flt(b.max_threshold)));
	config.generation_classification.push({
		container_type: def ? def.name : '',
		max_threshold: lastThr + 100,
		count: 1,
		total_converted_volume: 0,
	});
	scheduleSimulate();
}
function removeBand(i) {
	config.generation_classification.splice(i, 1);
	scheduleSimulate();
}

// ── UOM table ops ─────────────────────────────────────────────────────────────
function addUom() {
	config.uoms.push({ subsidiary_uom: '', conversion_factor: 1 });
}
function removeUom(i) { config.uoms.splice(i, 1); }

// ── Rating table ops ──────────────────────────────────────────────────────────
function addRating() { config.ratings.push({ rating: 0.2, safety_factor: 1 }); }
function removeRating(i) { config.ratings.splice(i, 1); }
const stars = (rating) => Math.round(flt(rating) * 5);
function setStars(row, n) { row.rating = n / 5; }

// ── Save ──────────────────────────────────────────────────────────────────────
async function save() {
	if (!canWrite.value) return;
	saving.value = true;
	errorMsg.value = '';
	try {
		await frappe.call(`${M}.save_config`, { name: props.name, payload: JSON.stringify(config) });
		frappe.show_alert({ message: __('Configuration saved'), indicator: 'green' }, 4);
		props.onSaved && props.onSaved();
		props.onClose && props.onClose();
	} catch (e) {
		errorMsg.value = (e && e.message) || __('Save failed');
	} finally {
		saving.value = false;
	}
}
</script>

<template>
	<div class="ce-root">
		<div v-if="loading" class="ce-state">{{ __('Loading…') }}</div>

		<template v-else>
			<!-- Live preview header -->
			<div class="ce-preview">
				<div class="ce-pv-item">
					<span class="ce-pv-label">{{ __('Calculated Waste') }} @ {{ uomValue }}</span>
					<span class="ce-pv-value">
						<template v-if="baselineWaste !== null && Math.abs(baselineWaste - flt(preview.calculated_waste)) > 0.01">
							<s class="ce-pv-old">{{ fmt(baselineWaste) }}</s> →
						</template>
						<b>{{ fmt(preview.calculated_waste) }}</b> {{ __(unitLabel) }}
					</span>
				</div>
				<div class="ce-pv-item">
					<span class="ce-pv-label">{{ __('Suggested Container') }}</span>
					<span class="ce-pv-value">
						<b>{{ preview.suggested_container ? __(preview.suggested_container) : '—' }}</b>
						<template v-if="preview.suggested_container_count">× {{ preview.suggested_container_count }}</template>
					</span>
				</div>
				<div class="ce-pv-cfg">{{ config.title }}</div>
			</div>

			<div v-if="errorMsg" class="ce-error">{{ errorMsg }}</div>
			<div v-if="readOnly" class="ce-ro">{{ __('You have read-only access to this configuration.') }}</div>

			<!-- Tabs -->
			<div class="ce-tabs">
				<button v-for="t in tabs" :key="t.id" class="ce-tab"
					:class="{ active: activeTab === t.id }" @click="activeTab = t.id">
					{{ __(t.label) }}
				</button>
			</div>

			<div class="ce-body">
				<!-- UOMs -->
				<section v-show="activeTab === 'uoms'" class="ce-pane">
					<label class="ce-field">
						<span>{{ __('Facility UOM') }}</span>
						<select v-model="config.facility_uom" :disabled="readOnly" @change="scheduleSimulate">
							<option value="">—</option>
							<option v-for="u in options.facility_uoms" :key="u.name" :value="u.name">
								{{ u.uom_name || u.name }}
							</option>
						</select>
					</label>

					<div class="ce-tbl-head">
						<span>{{ __('Subsidiary UOM') }}</span><span>{{ __('Conversion Factor') }}</span><span></span>
					</div>
					<div v-for="(row, i) in config.uoms" :key="i" class="ce-tbl-row">
						<select v-model="row.subsidiary_uom" :disabled="readOnly">
							<option value="">—</option>
							<option v-for="u in options.facility_uoms" :key="u.name" :value="u.name">
								{{ u.uom_name || u.name }}
							</option>
						</select>
						<input type="number" step="any" v-model.number="row.conversion_factor" :disabled="readOnly" />
						<button class="ce-x" :disabled="readOnly" @click="removeUom(i)">×</button>
					</div>
					<button class="ce-add" :disabled="readOnly" @click="addUom">＋ {{ __('Add UOM') }}</button>
				</section>

				<!-- Classification (the equalizer) -->
				<section v-show="activeTab === 'classification'" class="ce-pane">
					<EqualizerCanvas
						:bands="config.generation_classification"
						:container-types="options.container_types"
						:facility-uom="uomLabel"
						:whole-threshold="wholeThreshold"
						:unit="unitLabel"
						:uom-value="uomValue"
						:selected-threshold="preview.selected_threshold"
						:read-only="readOnly"
						@change="scheduleSimulate"
						@add="addBand"
						@remove="removeBand"
					/>
				</section>

				<!-- Settings -->
				<section v-show="activeTab === 'settings'" class="ce-pane">
					<label class="ce-field">
						<span>{{ __('Calculate Facility Wastes By') }}</span>
						<select v-model="config.calculate_facility_wastes_by" :disabled="readOnly" @change="scheduleSimulate">
							<option value="Generation Rate">{{ __('Generation Rate') }}</option>
							<option value="Cluster Classification">{{ __('Cluster Classification') }}</option>
						</select>
					</label>
					<label class="ce-field">
						<span>{{ __('Calculate Generation Rate By') }}</span>
						<select v-model="config.calculate_generation_rate_by" :disabled="readOnly" @change="scheduleSimulate">
							<option value="Mean">{{ __('Mean') }}</option>
							<option value="Median">{{ __('Median') }}</option>
						</select>
					</label>
					<label class="ce-field">
						<span>{{ __('Default Volume Unit') }}</span>
						<input class="ce-ro-input" :value="config.default_volume_unit || '—'" disabled />
						<small class="ce-hint-sm">{{ __('Set globally in Naqel Settings.') }}</small>
					</label>
					<label class="ce-check">
						<input type="checkbox" :checked="!!config.allocate_container_for_each_waste_type"
							:disabled="readOnly"
							@change="config.allocate_container_for_each_waste_type = $event.target.checked ? 1 : 0" />
						<span>{{ __('Allocate one container for each waste type') }}</span>
					</label>

					<div class="ce-stats">
						<h4>{{ __('Derived statistics') }}</h4>
						<div class="ce-stats-grid">
							<div><span>{{ __('Mean Rate') }}</span><b>{{ fmt(config.stats.mean_generation_rate) }}</b></div>
							<div><span>{{ __('Median Rate') }}</span><b>{{ fmt(config.stats.median_generation_rate) }}</b></div>
							<div><span>{{ __('Mean Threshold') }}</span><b>{{ fmt(config.stats.mean_threshold) }}</b></div>
							<div><span>{{ __('Median Threshold') }}</span><b>{{ fmt(config.stats.median_threshold) }}</b></div>
							<div><span>{{ __('Mean Volume') }}</span><b>{{ fmt(config.stats.mean_volume) }}</b></div>
							<div><span>{{ __('Median Volume') }}</span><b>{{ fmt(config.stats.median_volume) }}</b></div>
						</div>
					</div>
				</section>

				<!-- Ratings -->
				<section v-show="activeTab === 'ratings'" class="ce-pane">
					<div class="ce-tbl-head">
						<span>{{ __('Rating') }}</span><span>{{ __('Safety Factor') }}</span><span></span>
					</div>
					<div v-for="(row, i) in config.ratings" :key="i" class="ce-tbl-row">
						<div class="ce-stars">
							<button v-for="s in 5" :key="s" type="button" class="ce-star"
								:class="{ on: s <= stars(row.rating) }" :disabled="readOnly"
								@click="setStars(row, s)">★</button>
						</div>
						<input type="number" step="any" v-model.number="row.safety_factor" :disabled="readOnly" />
						<button class="ce-x" :disabled="readOnly" @click="removeRating(i)">×</button>
					</div>
					<button class="ce-add" :disabled="readOnly" @click="addRating">＋ {{ __('Add Rating') }}</button>
					<p class="ce-note">{{ __('Safety factor multiplies the generated waste (1 = no effect).') }}</p>
				</section>
			</div>

			<!-- Footer -->
			<div class="ce-footer">
				<button class="ce-btn ce-cancel" @click="props.onClose && props.onClose()">{{ __('Close') }}</button>
				<button class="ce-btn ce-save" :disabled="readOnly || saving" @click="save">
					{{ saving ? __('Saving…') : __('Save') }}
				</button>
			</div>
		</template>
	</div>
</template>

<style scoped>
.ce-root { display: flex; flex-direction: column; gap: 12px; min-height: 460px; }
.ce-state { padding: 40px; text-align: center; color: #6b7280; }
.ce-preview {
	display: flex; align-items: center; gap: 24px; flex-wrap: wrap;
	background: #f0fdf4; border: 1px solid #a7f3d0; border-radius: 10px; padding: 10px 16px;
}
.ce-pv-item { display: flex; flex-direction: column; }
.ce-pv-label { font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.03em; }
.ce-pv-value { font-size: 15px; color: #064e3b; }
.ce-pv-old { color: #9ca3af; }
.ce-pv-cfg { margin-inline-start: auto; font-size: 13px; font-weight: 700; color: #064e3b; }
.ce-error { background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; padding: 8px 12px; border-radius: 8px; font-size: 13px; }
.ce-ro { background: #fffbeb; border: 1px solid #fde68a; color: #92400e; padding: 6px 12px; border-radius: 8px; font-size: 12px; }
.ce-tabs { display: flex; gap: 4px; border-bottom: 2px solid #e5e7eb; }
.ce-tab {
	padding: 8px 18px; border: none; background: none; cursor: pointer;
	font-weight: 600; color: #6b7280; border-bottom: 2px solid transparent; margin-bottom: -2px;
}
.ce-tab.active { color: #059669; border-bottom-color: #059669; }
.ce-body { flex: 1; }
.ce-pane { display: flex; flex-direction: column; gap: 12px; padding: 8px 2px; }
.ce-field { display: flex; flex-direction: column; gap: 4px; max-width: 360px; }
.ce-field > span { font-size: 12px; font-weight: 600; color: #374151; }
.ce-field select, .ce-tbl-row select, .ce-tbl-row input {
	padding: 8px 10px; border: 2px solid #d1d5db; border-radius: 8px; font-size: 14px; background: #fff;
}
.ce-ro-input { padding: 8px 10px; border: 2px solid #e5e7eb; border-radius: 8px; font-size: 14px; background: #f9fafb; color: #6b7280; }
.ce-hint-sm { font-size: 11px; color: #9ca3af; }
.ce-check { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #374151; }
.ce-tbl-head, .ce-tbl-row { display: grid; grid-template-columns: 1fr 1fr 40px; gap: 10px; align-items: center; }
.ce-tbl-head { font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase; }
.ce-x { background: none; border: none; color: #ef4444; font-size: 18px; cursor: pointer; }
.ce-add {
	align-self: flex-start; padding: 6px 12px; border: 1px solid #059669; color: #059669;
	background: #fff; border-radius: 8px; font-weight: 600; cursor: pointer;
}
.ce-add:disabled, .ce-x:disabled { opacity: 0.5; cursor: not-allowed; }
.ce-stars { display: flex; gap: 2px; }
.ce-star { background: none; border: none; font-size: 20px; color: #d1d5db; cursor: pointer; padding: 0; }
.ce-star.on { color: #f59e0b; }
.ce-stats { margin-top: 8px; border-top: 1px solid #e5e7eb; padding-top: 10px; }
.ce-stats h4 { margin: 0 0 8px; font-size: 13px; color: #374151; }
.ce-stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.ce-stats-grid div { display: flex; flex-direction: column; background: #f9fafb; border-radius: 8px; padding: 8px 10px; }
.ce-stats-grid span { font-size: 11px; color: #6b7280; }
.ce-stats-grid b { font-size: 15px; color: #111827; }
.ce-note { font-size: 12px; color: #6b7280; margin: 0; }
.ce-footer { display: flex; justify-content: flex-end; gap: 10px; border-top: 1px solid #e5e7eb; padding-top: 12px; }
.ce-btn { padding: 9px 22px; border-radius: 8px; font-weight: 700; cursor: pointer; border: none; }
.ce-cancel { background: #fff; border: 2px solid #d1d5db; color: #374151; }
.ce-save { background: #059669; color: #fff; }
.ce-save:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
