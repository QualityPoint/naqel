<script setup>
import { computed } from 'vue';
import { __ } from './i18n';
import LinkField from './LinkField.vue';

const props = defineProps({
	serviceType: { type: String, default: '' },
	isicClassification: { type: String, default: '' },
	calculationBasedOn: { type: String, default: 'Service Configuration' },
	serviceConfiguration: { type: String, default: '' },
	divisionCategory: { type: String, default: '' },
	territory: { type: String, default: '' },
});

const emit = defineEmits([
	'update:serviceType',
	'update:isicClassification',
	'update:calculationBasedOn',
	'update:serviceConfiguration',
	'update:divisionCategory',
	'update:territory',
]);

const isRegional = computed(() => props.calculationBasedOn === 'Regional Service Configuration');

// Scope the Division picker to the chosen category (Province / City / …).
const divisionParams = computed(() =>
	props.divisionCategory ? { division_category: props.divisionCategory } : {}
);

// Reactive params for the configuration picker — when any of these change, the
// LinkField resets the chosen configuration.
const configParams = computed(() => ({
	service_type: props.serviceType,
	isic_classification: props.isicClassification,
	territory: props.territory,
	calculation_based_on: props.calculationBasedOn,
}));
</script>

<template>
	<div class="card-section">
		<h2 class="section-title">{{ __('Service Information') }}</h2>
		<div class="fields-stack">
			<LinkField
				:model-value="serviceType"
				@update:model-value="emit('update:serviceType', $event)"
				:label="__('Service Type')"
				method="naqel.api.waste_calculator.get_public_service_types"
				display-field="service_name"
				value-field="name"
				:required="true"
				:placeholder="__('Search for Service Type')"
			/>

			<LinkField
				:model-value="isicClassification"
				@update:model-value="emit('update:isicClassification', $event)"
				:label="__('ISIC Classification')"
				method="naqel.api.waste_calculator.get_public_isic_classifications"
				display-field="category_name"
				value-field="name"
				:required="true"
				:placeholder="__('Search for ISIC Classification')"
			/>

			<div class="field-wrap">
				<label class="field-label">
					<span class="text-danger">*</span> {{ __('Calculation Basis') }}
				</label>
				<select
					class="field-select"
					:value="calculationBasedOn"
					@change="emit('update:calculationBasedOn', $event.target.value)"
				>
					<option value="">{{ __('Choose Calculation Basis') }}</option>
					<option value="Service Configuration">{{ __('Service Configuration') }}</option>
					<option value="Regional Service Configuration">{{ __('Regional Service Configuration') }}</option>
				</select>
			</div>

			<div v-if="isRegional" class="field-wrap">
				<label class="field-label">
					<span class="text-danger">*</span> {{ __('Division Category') }}
				</label>
				<select
					class="field-select"
					:value="divisionCategory"
					@change="emit('update:divisionCategory', $event.target.value)"
				>
					<option value="">{{ __('Choose Division Category') }}</option>
					<option value="Province">{{ __('Province') }}</option>
					<option value="City">{{ __('City') }}</option>
					<option value="Municipality">{{ __('Municipality') }}</option>
					<option value="District">{{ __('District') }}</option>
				</select>
			</div>

			<LinkField
				v-if="isRegional"
				:model-value="territory"
				@update:model-value="emit('update:territory', $event)"
				:label="__('Division')"
				method="naqel.api.waste_calculator.get_public_address_divisions"
				:method-params="divisionParams"
				display-field="label"
				value-field="name"
				:required="true"
				:disabled="!divisionCategory"
				:placeholder="__('Search for Division')"
			/>

			<LinkField
				:model-value="serviceConfiguration"
				@update:model-value="emit('update:serviceConfiguration', $event)"
				:label="__('Configuration')"
				method="naqel.api.waste_calculator.get_public_service_configurations"
				:method-params="configParams"
				display-field="label"
				value-field="name"
				:disabled="!serviceType || (isRegional && !territory)"
				:placeholder="__('Search for Configuration')"
			/>
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
.field-select {
	width: 100%;
	padding: 9px 12px;
	border: 2px solid #d1d5db;
	border-radius: 8px;
	font-size: 14px;
	outline: none;
	background: white;
	color: #111827;
	transition: border-color 0.15s;
	cursor: pointer;
}
.field-select:focus {
	border-color: #059669;
	box-shadow: 0 0 0 3px rgba(5, 150, 105, 0.12);
}
</style>
