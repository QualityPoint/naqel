<!-- Status mix across the lifecycle, one donut per doctype. -->
<template>
	<div class="sd-grid sd-status-grid">
		<Card v-for="d in donuts" :key="d.key" :title="d.title">
			<ChartCanvas v-if="d.rows.length" :option="optionFor(d.rows)" height="210px" />
			<div v-else class="sd-empty">{{ __('No data') }}</div>
		</Card>
	</div>
</template>

<script setup>
import { computed } from 'vue';
import Card from './Card.vue';
import ChartCanvas from './ChartCanvas.vue';
import { PALETTE, statusColor, formatNumber } from '../palette';

const props = defineProps({
	status: { type: Object, default: () => ({}) },
	loading: Boolean,
});

const donuts = computed(() => [
	{ key: 'lead', title: __('Lead Status'), rows: props.status.lead || [] },
	{ key: 'customer_type', title: __('Customers by Type'), rows: props.status.customer_type || [] },
	{ key: 'service_request', title: __('Request Status'), rows: props.status.service_request || [] },
	{ key: 'quotation', title: __('Quotation Status'), rows: props.status.quotation || [] },
	{ key: 'contract', title: __('Contract Status'), rows: props.status.contract || [] },
	{ key: 'payment', title: __('Payment Status'), rows: props.status.payment || [] },
]);

function optionFor(rows) {
	const total = rows.reduce((s, r) => s + (r.value || 0), 0);
	return {
		tooltip: {
			trigger: 'item',
			formatter: (p) => `${p.name}<br/><b>${formatNumber(p.value)}</b> (${p.percent}%)`,
			backgroundColor: '#fff', borderColor: PALETTE.line, textStyle: { color: PALETTE.ink },
		},
		legend: {
			type: 'scroll', orient: 'horizontal', bottom: 0, left: 'center',
			icon: 'circle', itemWidth: 9, itemHeight: 9,
			textStyle: { color: PALETTE.muted, fontSize: 11 },
		},
		graphic: {
			type: 'text', left: 'center', top: '38%',
			style: { text: formatNumber(total), fill: PALETTE.ink, fontSize: 20, fontWeight: 700, textAlign: 'center' },
		},
		series: [
			{
				type: 'pie',
				radius: ['54%', '78%'],
				center: ['50%', '44%'],
				avoidLabelOverlap: true,
				label: { show: false },
				labelLine: { show: false },
				itemStyle: { borderColor: '#fff', borderWidth: 2 },
				data: rows.map((r, i) => ({
					name: __(r.name),
					value: r.value,
					itemStyle: { color: statusColor(r.name, i) },
				})),
			},
		],
	};
}
</script>

<style scoped>
.sd-grid { display: grid; gap: 14px; margin-top: 14px; }
.sd-status-grid {
	grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
}
.sd-empty {
	padding: 40px 0;
	text-align: center;
	color: #9ca3af;
	font-size: 13px;
}
</style>
