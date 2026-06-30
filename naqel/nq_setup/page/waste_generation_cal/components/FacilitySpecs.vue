<script setup>
import { computed } from 'vue';
import { __ } from './i18n';
import LinkField from './LinkField.vue';
import StarRating from './StarRating.vue';

const props = defineProps({
	facilityUOM: { type: String, default: '' },
	isCompositeUOM: { type: Number, default: 0 },
	mustBeWholeNumber: { type: Number, default: 0 },
	facilityMeasurement: { type: Number, default: 0 },
	facilityMeasurements: { type: Array, default: () => [] },
	facilityRating: { type: Number, default: 0 },
	allocateContainerForEachWasteType: { type: Number, default: 0 },
	isMilestoneBased: { type: Number, default: 0 },
	serviceConfiguration: { type: String, default: '' },
});

const emit = defineEmits([
	'update:facilityUOM',
	'update:facilityMeasurement',
	'update:facilityMeasurements',
	'update:facilityRating',
	'update:allocateContainerForEachWasteType',
	'update:isMilestoneBased',
]);

// When a composite measurement input changes, recalculate total
const handleMeasurementChange = (index, raw) => {
	const val = parseFloat(raw) || 0;
	const updated = props.facilityMeasurements.map((m, i) =>
		i === index ? { ...m, uom_value: val } : m
	);
	emit('update:facilityMeasurements', updated);
	// Total is product of all uom_values
	const total = updated.reduce((acc, m) => acc * (m.uom_value || 1), 1);
	emit('update:facilityMeasurement', total);
};

const uomMethodParams = computed(() =>
	props.serviceConfiguration ? { service_configuration: props.serviceConfiguration } : {}
);

// Force-remount LinkField when service configuration changes by using it as a key
const uomKey = computed(() => props.serviceConfiguration || '__none__');
</script>

<template>
	<div class="card-section">
		<h2 class="section-title">{{ __('Facility Specifications') }}</h2>
		<div class="fields-stack">
			<!-- Facility UOM -->
			<LinkField
				:key="uomKey"
				:model-value="facilityUOM"
				@update:model-value="emit('update:facilityUOM', $event)"
				:label="__('Facility UOM')"
				method="naqel.api.waste_calculator.get_public_facility_uoms"
				:method-params="uomMethodParams"
				display-field="uom_name"
				value-field="name"
				:required="true"
				:placeholder="__('Search for UOM')"
				:disabled="!serviceConfiguration"
			/>
			<p v-if="!serviceConfiguration" class="hint-text">
				{{ __('Please select service type and ISIC classification first') }}
			</p>

			<!-- Composite UOM measurements -->
			<template v-if="isCompositeUOM === 1 && facilityMeasurements.length > 0">
				<div v-for="(m, index) in facilityMeasurements" :key="index" class="field-wrap">
					<label class="field-label">
						<span class="text-danger">*</span> {{ m.uom }}
					</label>
					<input
						class="field-input"
						type="number"
						min="0"
						:step="m.must_be_whole_number ? '1' : '0.01'"
						:value="m.uom_value || ''"
						@input="handleMeasurementChange(index, $event.target.value)"
					/>
					<span v-if="m.must_be_whole_number" class="hint-text">{{ __('Must be a whole number') }}</span>
				</div>
				<div class="total-box">
					<span class="total-label">{{ __('Grand Total Measurement') }}:</span>
					<strong class="total-value">{{ facilityMeasurement.toFixed(2) }}</strong>
				</div>
			</template>

			<!-- Simple measurement -->
			<div v-else class="field-wrap">
				<label class="field-label">
					<span class="text-danger">*</span> {{ __('Facility Measurement') }}
				</label>
				<input
					class="field-input"
					type="number"
					min="0"
					:step="mustBeWholeNumber ? '1' : '0.01'"
					:value="facilityMeasurement || ''"
					:disabled="isCompositeUOM === 1"
					@input="emit('update:facilityMeasurement', parseFloat($event.target.value) || 0)"
				/>
				<span v-if="mustBeWholeNumber" class="hint-text">{{ __('Must be a whole number') }}</span>
			</div>

			<!-- Facility rating: always available. When set, the configuration's
			     matching rating applies a safety factor; otherwise it has no effect. -->
			<div class="divider"></div>
			<div class="field-wrap">
				<label class="field-label">{{ __('Facility Rating') }}</label>
				<StarRating
					:model-value="facilityRating"
					@update:model-value="emit('update:facilityRating', $event)"
				/>
				<span class="hint-text">{{ __('Optionally, choose a rating from 1 to 5 stars') }}</span>
			</div>

			<label class="check-wrap">
				<input
					type="checkbox"
					:checked="!!allocateContainerForEachWasteType"
					@change="emit('update:allocateContainerForEachWasteType', $event.target.checked ? 1 : 0)"
				/>
				<span>{{ __('Allocate One Container For Each Waste Type') }}</span>
			</label>

			<div class="check-field">
				<label class="check-wrap">
					<input
						type="checkbox"
						:checked="!!isMilestoneBased"
						@change="emit('update:isMilestoneBased', $event.target.checked ? 1 : 0)"
					/>
					<span>{{ __('Is Milestone-Based Service') }}</span>
				</label>
				<p class="check-desc">
					{{ __('Enable if the service relies strictly on milestone completion. Leave unchecked if it depends on a standard contract expiry timeline.') }}
				</p>
			</div>
		</div>
	</div>
</template>

<style scoped>
.card-section {
	background: white;
	border: 2px solid #059669;
	border-radius: 16px;
	padding: 24px;
	box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}
.section-title {
	font-size: 20px;
	font-weight: 700;
	color: #064e3b;
	margin: 0 0 20px 0;
}
.fields-stack {
	display: flex;
	flex-direction: column;
	gap: 16px;
}
.field-wrap {
	display: flex;
	flex-direction: column;
	gap: 4px;
}
.field-label {
	font-size: 12px;
	font-weight: 600;
	color: #374151;
	text-transform: uppercase;
	letter-spacing: 0.03em;
}
.field-input {
	width: 100%;
	padding: 9px 12px;
	border: 2px solid #d1d5db;
	border-radius: 8px;
	font-size: 14px;
	outline: none;
	box-sizing: border-box;
	transition: border-color 0.15s;
}
.field-input:focus {
	border-color: #059669;
	box-shadow: 0 0 0 3px rgba(5, 150, 105, 0.12);
}
.field-input:disabled {
	background: #f3f4f6;
	cursor: not-allowed;
}
.hint-text {
	font-size: 12px;
	color: #6b7280;
}
.total-box {
	background: #f0fdf4;
	border: 1px solid #a7f3d0;
	border-radius: 8px;
	padding: 10px 14px;
	display: flex;
	align-items: center;
	gap: 8px;
}
.total-label {
	font-size: 13px;
	font-weight: 600;
	color: #065f46;
}
.total-value {
	font-size: 15px;
	color: #047857;
}
.divider {
	border-top: 1px solid #e5e7eb;
}
.check-wrap {
	display: flex;
	align-items: center;
	gap: 8px;
	font-size: 13px;
	color: #374151;
	cursor: pointer;
}
.check-wrap input {
	width: 16px;
	height: 16px;
	accent-color: #059669;
	cursor: pointer;
}
.check-field {
	display: flex;
	flex-direction: column;
	gap: 4px;
}
.check-desc {
	margin: 0;
	padding-inline-start: 24px;
	font-size: 12px;
	color: #6b7280;
	line-height: 1.5;
}
</style>
