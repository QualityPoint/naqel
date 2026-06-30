<!-- Top KPI strip: revenue headline cards + lifecycle counts. -->
<template>
	<div class="sd-kpis">
		<div
			v-for="c in cards"
			:key="c.key"
			class="sd-kpi"
			:class="{ skeleton: loading && !hasData }"
			:style="{ '--accent': c.accent }"
		>
			<div class="sd-kpi-top">
				<span class="sd-kpi-label">{{ c.label }}</span>
				<span class="sd-kpi-dot"></span>
			</div>
			<div class="sd-kpi-value" :title="c.title || ''">{{ c.value }}</div>
			<div v-if="c.sub" class="sd-kpi-sub">{{ c.sub }}</div>
		</div>
	</div>
</template>

<script setup>
import { computed } from 'vue';
import { PALETTE, formatNumber, formatCurrency, formatFullCurrency } from '../palette';

const props = defineProps({
	kpis: { type: Object, default: () => ({}) },
	loading: Boolean,
});

const hasData = computed(() => Object.keys(props.kpis).length > 0);

const cards = computed(() => {
	const k = props.kpis || {};
	const cur = k.currency || 'SAR';
	return [
		{
			key: 'contracted', label: __('Contracted Revenue'), accent: PALETTE.primary,
			value: formatCurrency(k.contracted_revenue, cur), title: formatFullCurrency(k.contracted_revenue, cur),
			sub: __('{0} active contracts', [formatNumber(k.active_contracts)]),
		},
		{
			key: 'pipeline', label: __('Pipeline Value'), accent: PALETTE.cyan,
			value: formatCurrency(k.pipeline_value, cur), title: formatFullCurrency(k.pipeline_value, cur),
			sub: __('Open & accepted quotations'),
		},
		{
			key: 'collected', label: __('Collected'), accent: PALETTE.emerald,
			value: formatCurrency(k.collected, cur), title: formatFullCurrency(k.collected, cur),
			sub: __('Of contracted revenue'),
		},
		{
			key: 'outstanding', label: __('Outstanding'), accent: PALETTE.amber,
			value: formatCurrency(k.outstanding, cur), title: formatFullCurrency(k.outstanding, cur),
			sub: __('Amount due'),
		},
		{
			key: 'leads', label: __('Leads'), accent: PALETTE.teal,
			value: formatNumber(k.leads),
			sub: __('{0}% converted', [k.lead_to_customer_conversion ?? 0]),
		},
		{
			key: 'customers', label: __('Customers'), accent: PALETTE.lime,
			value: formatNumber(k.customers),
			sub: __('{0} from leads', [formatNumber(k.customers_converted)]),
		},
		{
			key: 'facilities', label: __('Facilities'), accent: PALETTE.indigo,
			value: formatNumber(k.facilities),
		},
		{
			key: 'requests', label: __('Service Requests'), accent: PALETTE.slate,
			value: formatNumber(k.service_requests),
		},
		{
			key: 'quotations', label: __('Quotations'), accent: PALETTE.cyan,
			value: formatNumber(k.quotations),
			sub: __('{0}% won', [k.sq_to_sc_conversion ?? 0]),
		},
		{
			key: 'contracts', label: __('Contracts'), accent: PALETTE.primary,
			value: formatNumber(k.contracts),
		},
	];
});
</script>

<style scoped>
.sd-kpis {
	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(168px, 1fr));
	gap: 12px;
	margin-top: 14px;
}
.sd-kpi {
	position: relative;
	background: #fff;
	border: 1px solid #eef1f0;
	border-radius: 14px;
	padding: 14px 15px;
	box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
	overflow: hidden;
	transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.sd-kpi::before {
	content: '';
	position: absolute;
	left: 0; top: 0; bottom: 0;
	width: 4px;
	background: var(--accent);
}
.sd-kpi:hover {
	transform: translateY(-2px);
	box-shadow: 0 8px 22px rgba(16, 24, 40, 0.10);
}
.sd-kpi-top {
	display: flex;
	align-items: center;
	justify-content: space-between;
}
.sd-kpi-label {
	font-size: 11px;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.04em;
	color: #6b7280;
}
.sd-kpi-dot {
	width: 8px; height: 8px;
	border-radius: 50%;
	background: var(--accent);
	opacity: 0.85;
}
.sd-kpi-value {
	margin-top: 8px;
	font-size: 24px;
	font-weight: 750;
	color: #0f172a;
	line-height: 1.1;
	white-space: nowrap;
}
.sd-kpi-sub {
	margin-top: 4px;
	font-size: 11.5px;
	color: #6b7280;
}
.sd-kpi.skeleton .sd-kpi-value,
.sd-kpi.skeleton .sd-kpi-sub {
	color: transparent;
	background: linear-gradient(90deg, #eef1f0, #f6f8f7, #eef1f0);
	border-radius: 6px;
}
</style>
