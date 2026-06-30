<script setup>
import { ref, reactive, computed } from 'vue';
import { __ } from './i18n';
import ServiceSelection from './ServiceSelection.vue';
import FacilitySpecs from './FacilitySpecs.vue';
import WasteBins from './WasteBins.vue';
import CalculationResults from './CalculationResults.vue';

defineProps({ frappePage: { type: Object, default: null } });

// ── Form state ───────────────────────────────────────────────────────────────
const formData = reactive({
	service_type: '',
	is_milestone_based: 0,   // duration is applied by default; check to disable it
	isic_classification: '',
	service_configuration: '',
	calculation_based_on: 'Service Configuration',
	division_category: '',
	territory: '',
	allocate_container_for_each_waste_type: 0,
	facility_uom: '',
	is_composite_uom: 0,
	must_be_whole_number: 0,
	facility_measurement: 0,
	facility_measurements: [],
	facility_rating: 0,
	waste_types: [],    // WasteDistribution[]
	wastes: [],         // { waste_type: string }[]
});

// The Service Configuration resolved for the current service_type + ISIC (SC mode).
// Cached so switching the calculation basis can re-apply it without re-fetching.
const resolvedServiceConfiguration = ref('');

const calculationResult = ref(null);
const calculating = ref(false);
const loadingWasteTypes = ref(false);

// selectedWastes: Map<groupName, string[]> — use a plain object for reactivity
const selectedWastes = reactive({});

// wasteTypesCache: Record<groupName, WasteType[]>
const wasteTypesCache = reactive({});

// droppedItems: Record<containerKey, WasteType[]>
const droppedItems = reactive({});

// ── Helpers ──────────────────────────────────────────────────────────────────
const alert = (message, indicator = 'blue') =>
	frappe.show_alert({ message, indicator }, 4);

// ── API: Service Type ─────────────────────────────────────────────────────────
const handleServiceTypeChange = (value) => {
	formData.service_type = value;
	if (!value) return;

	if (formData.isic_classification) {
		fetchWasteTypes(formData.isic_classification, value);
	}
};

// ── Configuration auto-resolution ─────────────────────────────────────────────
// Auto-populate the chosen configuration's default Facility UOM (the first allowed
// entry). The server resolves a Regional Service Configuration to the config it
// computes from, so the UOM stays consistent with the calculation.
const applyDefaultFacilityUom = () => {
	if (!formData.service_configuration) return;
	frappe.call({
		method: 'naqel.api.waste_calculator.get_allowed_facility_uoms',
		args: { service_configuration: formData.service_configuration },
		callback: (r) => {
			const allowed = r?.message || [];
			if (allowed.length) handleFacilityUOMChange(allowed[0]);
		},
		error: () => alert(__('Failed to load the facility unit of measure'), 'red'),
	});
};

// Resolve and auto-select the applicable Regional Service Configuration for the
// current service type / ISIC / territory (the first/best match), so the user
// doesn't have to pick it manually.
const resolveRegionalConfiguration = () => {
	if (!formData.service_type || !formData.territory) {
		formData.service_configuration = '';
		return;
	}
	frappe.call({
		method: 'naqel.api.waste_calculator.get_public_service_configurations',
		args: {
			service_type: formData.service_type,
			isic_classification: formData.isic_classification,
			territory: formData.territory,
			calculation_based_on: 'Regional Service Configuration',
		},
		callback: (r) => {
			const list = r?.message?.data || [];
			formData.service_configuration = list.length ? list[0].name : '';
			applyDefaultFacilityUom();
		},
		error: () => alert(__('Failed to resolve the regional service configuration'), 'red'),
	});
};

// Auto-populate the configuration field based on the current calculation basis.
const autoPopulateConfiguration = () => {
	if (formData.calculation_based_on === 'Regional Service Configuration') {
		resolveRegionalConfiguration();
	} else {
		// SC mode: the resolved Service Configuration is already known from fetchWasteTypes.
		formData.service_configuration = resolvedServiceConfiguration.value || '';
		applyDefaultFacilityUom();
	}
};

// ── Calculation basis / configuration choice ──────────────────────────────────
const handleCalculationBasisChange = (value) => {
	formData.calculation_based_on = value;
	// The chosen config is basis-specific; clear it then auto-populate for the new basis.
	formData.service_configuration = '';
	if (value !== 'Regional Service Configuration') {
		formData.division_category = '';
		formData.territory = '';
	}
	autoPopulateConfiguration();
};

// ── Manual configuration pick ─────────────────────────────────────────────────
const handleServiceConfigurationChange = (value) => {
	formData.service_configuration = value;
	applyDefaultFacilityUom();
};

// ── Territory (Regional mode) ─────────────────────────────────────────────────
const handleTerritoryChange = (value) => {
	formData.territory = value;
	if (formData.calculation_based_on === 'Regional Service Configuration') {
		resolveRegionalConfiguration();
	}
};

// ── API: ISIC ─────────────────────────────────────────────────────────────────
const handleISICChange = (value) => {
	formData.isic_classification = value;
	if (value && formData.service_type) {
		fetchWasteTypes(value, formData.service_type);
	}
};

// Pre-drop each category's configured default waste items into its bin so the user
// starts from a sensible selection (they can still add/remove). `default_waste_item`
// is a comma-joined list of Waste Type names on the Waste Distribution row.
const prefillDefaultWasteItems = (distributions, cache) => {
	distributions.forEach((dist) => {
		const defaults = (dist.default_waste_item || '')
			.split(/\s*[\n,]\s*/)
			.filter(Boolean);
		if (!defaults.length) return;

		const available = cache[dist.waste_type] || [];
		const matched = available.filter((type) => defaults.includes(type.name));
		if (matched.length) {
			droppedItems[dist.waste_type] = matched;
			selectedWastes[dist.waste_type] = matched.map((type) => type.name);
		}
	});
};

// ── API: Fetch waste distributions + waste types per group ────────────────────
const fetchWasteTypes = (isic, serviceType) => {
	loadingWasteTypes.value = true;

	frappe.call({
		method: 'naqel.api.waste_calculator.get_service_configuration',
		args: { isic_classification: isic, service_type: serviceType },
		callback: (r) => {
			const data = r?.message;
			if (!data) { loadingWasteTypes.value = false; return; }

			// Reset UOM fields
			formData.facility_uom = '';
			formData.is_composite_uom = 0;
			formData.must_be_whole_number = 0;
			formData.facility_measurement = 0;
			formData.facility_measurements = [];

			// Cache the resolved Service Configuration, then auto-populate the config
			// field for the active basis (SC: this config; Regional: matching RSC).
			resolvedServiceConfiguration.value = data.service_configuration || '';
			autoPopulateConfiguration();
			formData.allocate_container_for_each_waste_type = data.allocate_container_for_each_waste_type || 0;

			const distributions = data.waste_distributions || [];
			formData.waste_types = distributions;

			// Reset selection state
			distributions.forEach((dist) => {
				selectedWastes[dist.waste_type] = [];
			});
			Object.keys(droppedItems).forEach((k) => delete droppedItems[k]);

			if (distributions.length === 0) {
				loadingWasteTypes.value = false;
				return;
			}

			// Fetch allowed leaf waste types for each distribution group
			let pending = distributions.length;
			const newCache = {};

			distributions.forEach((dist) => {
				frappe.call({
					method: 'naqel.api.waste_calculator.get_allowed_waste_types',
					args: { waste_types: JSON.stringify([dist.waste_type]) },
					callback: (r2) => {
						const types = r2?.message;
						if (Array.isArray(types)) {
							newCache[dist.waste_type] = types;
						}
						pending--;
						if (pending === 0) {
							// Merge into reactive cache
							Object.keys(wasteTypesCache).forEach((k) => delete wasteTypesCache[k]);
							Object.assign(wasteTypesCache, newCache);
							prefillDefaultWasteItems(distributions, newCache);
							loadingWasteTypes.value = false;
						}
					},
					error: () => {
						pending--;
						alert(__('Failed to load waste types for: ') + dist.waste_name, 'red');
						if (pending === 0) loadingWasteTypes.value = false;
					},
				});
			});
		},
		error: () => {
			loadingWasteTypes.value = false;
			alert(__('Failed to load service configuration'), 'red');
		},
	});
};

// ── API: Facility UOM ─────────────────────────────────────────────────────────
const handleFacilityUOMChange = (value) => {
	formData.facility_uom = value;
	if (!value) return;

	frappe.call({
		method: 'naqel.api.waste_calculator.get_facility_uom_details',
		args: { facility_uom: value },
		callback: (r) => {
			const data = r?.message;
			if (data) {
				formData.must_be_whole_number = data.must_be_whole_number || 0;
				formData.is_composite_uom = data.is_composite_uom || 0;
			}
		},
		error: () => alert(__('Failed to load the unit of measure details'), 'red'),
	});

	frappe.call({
		method: 'naqel.api.waste_calculator.get_facility_uom_hierarchy',
		args: { facility_uom: value },
		callback: (r) => {
			const hierarchy = r?.message;
			if (Array.isArray(hierarchy)) {
				formData.facility_measurements = hierarchy.map((item) => ({
					uom: item.uom,
					uom_value: 0,
					must_be_whole_number: item.must_be_whole_number || 0,
				}));
			}
		},
		error: () => alert(__('Failed to load the unit of measure hierarchy'), 'red'),
	});
};

// ── Waste selection (called when bins drop items) ────────────────────────────
const handleWasteSelection = (groupName, wasteTypeNames) => {
	selectedWastes[groupName] = wasteTypeNames;
	// Rebuild formData.wastes from the full selectedWastes map
	const all = [];
	Object.values(selectedWastes).forEach((names) => {
		names.forEach((name) => all.push({ waste_type: name }));
	});
	formData.wastes = all;
};

// ── Bin events ────────────────────────────────────────────────────────────────
const handleBinDrop = ({ item, containerKey, groupName }) => {
	if (!droppedItems[containerKey]) droppedItems[containerKey] = [];
	if (droppedItems[containerKey].some((d) => d.name === item.name)) return;
	droppedItems[containerKey].push(item);
	const current = selectedWastes[groupName] || [];
	handleWasteSelection(groupName, [...current, item.name]);
};

const handleRemoveItem = ({ containerKey, itemName, groupName }) => {
	if (droppedItems[containerKey]) {
		droppedItems[containerKey] = droppedItems[containerKey].filter((i) => i.name !== itemName);
	}
	const current = selectedWastes[groupName] || [];
	handleWasteSelection(groupName, current.filter((n) => n !== itemName));
};

const handleClearAll = () => {
	Object.keys(droppedItems).forEach((k) => delete droppedItems[k]);
	formData.waste_types.forEach((dist) => handleWasteSelection(dist.waste_type, []));
};

// ── Calculate ─────────────────────────────────────────────────────────────────
const handleCalculate = () => {
	if (!formData.service_type) {
		return alert(__('Please select a service type'), 'red');
	}
	if (!formData.isic_classification) {
		return alert(__('Please select an ISIC classification'), 'red');
	}
	if (!formData.facility_uom) {
		return alert(__('Please select a facility unit of measure'), 'red');
	}
	if (!formData.calculation_based_on) {
		return alert(__('Please select a calculation basis'), 'red');
	}
	if (formData.is_composite_uom) {
		if (!formData.facility_measurements?.length) {
			return alert(__('Please enter the facility measurements'), 'red');
		}
	} else if (!formData.facility_measurement || formData.facility_measurement <= 0) {
		return alert(__('Please enter the facility measurement'), 'red');
	}

	// Build wastes from current droppedItems
	const allWastes = [];
	Object.entries(droppedItems).forEach(([, items]) => {
		items.forEach((item) => allWastes.push({ waste_type: item.name }));
	});

	if (allWastes.length === 0) {
		return alert(__('Please select at least one waste type'), 'red');
	}

	calculating.value = true;
	frappe.call({
		method: 'naqel.api.waste_calculator.calculate_waste',
		args: {
			// Duration is applied by default; a milestone-based service disables it.
			// Frappe's Rating fieldtype stores a fraction of the max, so convert the
			// selected star count before sending to match Rating Classification thresholds.
			doc: {
				...formData,
				wastes: allWastes,
				apply_service_duration: formData.is_milestone_based ? 0 : 1,
				facility_rating: formData.facility_rating
					? formData.facility_rating / (window.naqel?.RATING_MAX_STARS || 5)
					: 0,
			},
			language: frappe.boot?.lang || 'en',
		},
		callback: (r) => {
			calculating.value = false;
			const data = r?.message;
			if (data) {
				calculationResult.value = data;
				alert(__('Waste calculated successfully'), 'green');
				// Scroll to results
				setTimeout(() => {
					document.querySelector('.results-section')?.scrollIntoView({ behavior: 'smooth' });
				}, 100);
			}
		},
		error: () => {
			calculating.value = false;
			alert(__('An error occurred during calculation'), 'red');
		},
	});
};

// ── Clear ─────────────────────────────────────────────────────────────────────
const handleClear = () => {
	Object.assign(formData, {
		service_type: '',
		is_milestone_based: 0,
		isic_classification: '',
		service_configuration: '',
		calculation_based_on: 'Service Configuration',
		division_category: '',
		territory: '',
		allocate_container_for_each_waste_type: 0,
		facility_uom: '',
		is_composite_uom: 0,
		must_be_whole_number: 0,
		facility_measurement: 0,
		facility_measurements: [],
		facility_rating: 0,
		waste_types: [],
		wastes: [],
	});
	resolvedServiceConfiguration.value = '';
	calculationResult.value = null;
	Object.keys(selectedWastes).forEach((k) => delete selectedWastes[k]);
	Object.keys(wasteTypesCache).forEach((k) => delete wasteTypesCache[k]);
	Object.keys(droppedItems).forEach((k) => delete droppedItems[k]);
	alert(__('Data cleared'));
};

// wasteTypesCache as a plain object for prop passing (reactive works fine)
const wasteTypesCacheObj = computed(() => ({ ...wasteTypesCache }));
const droppedItemsObj = computed(() => ({ ...droppedItems }));
</script>

<template>
	<div class="wc-page">
		<!-- Header -->
		<div class="wc-header">
			<div class="wc-header-icon">♻️</div>
			<h1 class="wc-title">{{ __('Waste Calculator') }}</h1>
			<p class="wc-subtitle">
				{{ __('Calculate expected waste quantity for your facility based on activity type and specifications') }}
			</p>
		</div>

		<!-- Two-column form cards -->
		<div class="form-grid">
			<ServiceSelection
				:service-type="formData.service_type"
				:isic-classification="formData.isic_classification"
				:calculation-based-on="formData.calculation_based_on"
				:service-configuration="formData.service_configuration"
				:division-category="formData.division_category"
				:territory="formData.territory"
				@update:service-type="handleServiceTypeChange"
				@update:isic-classification="handleISICChange"
				@update:calculation-based-on="handleCalculationBasisChange"
				@update:service-configuration="handleServiceConfigurationChange"
				@update:division-category="formData.division_category = $event"
				@update:territory="handleTerritoryChange"
			/>
			<FacilitySpecs
				:facility-u-o-m="formData.facility_uom"
				:is-composite-u-o-m="formData.is_composite_uom"
				:must-be-whole-number="formData.must_be_whole_number"
				:facility-measurement="formData.facility_measurement"
				:facility-measurements="formData.facility_measurements"
				:facility-rating="formData.facility_rating"
				:allocate-container-for-each-waste-type="formData.allocate_container_for_each_waste_type"
				:is-milestone-based="formData.is_milestone_based"
				:service-configuration="formData.service_configuration"
				@update:facility-u-o-m="handleFacilityUOMChange"
				@update:facility-measurement="formData.facility_measurement = $event"
				@update:facility-measurements="formData.facility_measurements = $event"
				@update:facility-rating="formData.facility_rating = $event"
				@update:allocate-container-for-each-waste-type="formData.allocate_container_for_each_waste_type = $event"
				@update:is-milestone-based="formData.is_milestone_based = $event"
			/>
		</div>

		<!-- Waste bins (shown when distributions are loaded) -->
		<WasteBins
			v-if="formData.waste_types.length > 0"
			:waste-types="formData.waste_types"
			:waste-types-cache="wasteTypesCacheObj"
			:dropped-items="droppedItemsObj"
			:loading-waste-types="loadingWasteTypes"
			@drop="handleBinDrop"
			@remove-item="handleRemoveItem"
			@clear-all="handleClearAll"
		/>

		<!-- Action buttons -->
		<div class="action-row">
			<button class="btn-calculate" :disabled="calculating" @click="handleCalculate">
				<span v-if="calculating" class="btn-spinner"></span>
				{{ calculating ? __('Calculating...') : __('Calculate Waste') }}
			</button>
			<button class="btn-clear" @click="handleClear">{{ __('Clear') }}</button>
		</div>

		<!-- Results -->
		<div v-if="calculationResult" class="results-section">
			<h2 class="section-heading">{{ __('Calculation Results') }}</h2>
			<CalculationResults
				:result="calculationResult"
				:waste-distributions="formData.waste_types"
				:dropped-items="droppedItemsObj"
			/>
		</div>

		<!-- Info box -->
		<div class="info-box">
			<h3 class="info-title">ℹ️ {{ __('Important Information') }}</h3>
			<ul class="info-list">
				<li>• {{ __('All calculations are based on approved standards and classifications') }}</li>
				<li>• {{ __('Results are estimates and may vary depending on the actual nature of the activity') }}</li>
				<li>• {{ __('You can apply facility rating for more accurate results') }}</li>
				<li>• {{ __('Suggested containers are based on calculated generation rates') }}</li>
			</ul>
		</div>
	</div>
</template>

<style scoped>
.wc-page {
	padding: 20px 24px;
	max-width: 1200px;
	margin: 0 auto;
	display: flex;
	flex-direction: column;
	gap: 28px;
}
.wc-header {
	text-align: center;
}
.wc-header-icon {
	font-size: 48px;
	margin-bottom: 8px;
}
.wc-title {
	font-size: 32px;
	font-weight: 800;
	color: #064e3b;
	margin: 0 0 8px 0;
}
.wc-subtitle {
	font-size: 15px;
	color: #6b7280;
	margin: 0;
}
.form-grid {
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: 20px;
}
@media (max-width: 768px) {
	.form-grid {
		grid-template-columns: 1fr;
	}
}
.action-row {
	display: flex;
	gap: 12px;
}
.btn-calculate {
	flex: 1;
	padding: 14px;
	background: #059669;
	color: white;
	border: none;
	border-radius: 10px;
	font-size: 16px;
	font-weight: 700;
	cursor: pointer;
	transition: background 0.15s;
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 8px;
}
.btn-calculate:hover:not(:disabled) {
	background: #047857;
}
.btn-calculate:disabled {
	opacity: 0.65;
	cursor: not-allowed;
}
.btn-spinner {
	width: 16px;
	height: 16px;
	border: 2px solid rgba(255, 255, 255, 0.4);
	border-top-color: white;
	border-radius: 50%;
	animation: spin 0.7s linear infinite;
	flex-shrink: 0;
}
@keyframes spin {
	to { transform: rotate(360deg); }
}
.btn-clear {
	padding: 14px 28px;
	background: white;
	color: #059669;
	border: 2px solid #059669;
	border-radius: 10px;
	font-size: 16px;
	font-weight: 700;
	cursor: pointer;
	transition: background 0.15s;
}
.btn-clear:hover {
	background: #f0fdf4;
}
.section-heading {
	font-size: 26px;
	font-weight: 700;
	color: #064e3b;
	margin: 0 0 16px 0;
}
.results-section {
	display: flex;
	flex-direction: column;
}
.info-box {
	background: #f0fdf4;
	border: 2px solid #a7f3d0;
	border-radius: 14px;
	padding: 20px 24px;
}
.info-title {
	font-size: 18px;
	font-weight: 700;
	color: #064e3b;
	margin: 0 0 12px 0;
}
.info-list {
	list-style: none;
	margin: 0;
	padding: 0;
	display: flex;
	flex-direction: column;
	gap: 6px;
}
.info-list li {
	font-size: 14px;
	color: #065f46;
}
</style>
