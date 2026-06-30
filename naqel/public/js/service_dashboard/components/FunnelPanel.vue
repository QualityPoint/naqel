<!-- Lifecycle funnel: Leads → Customers → Service Requests → Quotations → Contracts. -->
<template>
	<Card :title="__('Sales Funnel')" :subtitle="__('Lifecycle conversion')">
		<ChartCanvas v-if="hasData" :option="option" height="300px" />
		<div v-else class="sd-empty">{{ __('No records in this period.') }}</div>
	</Card>
</template>

<script setup>
import { computed } from 'vue';
import Card from './Card.vue';
import ChartCanvas from './ChartCanvas.vue';
import { CATEGORICAL, PALETTE, formatNumber } from '../palette';

const props = defineProps({
	funnel: { type: Array, default: () => [] },
	loading: Boolean,
});

const hasData = computed(() => props.funnel.some((s) => s.value));

const option = computed(() => ({
	tooltip: {
		trigger: 'item',
		formatter: (p) => `${p.name}<br/><b>${formatNumber(p.value)}</b>`,
		backgroundColor: '#fff', borderColor: PALETTE.line, textStyle: { color: PALETTE.ink },
	},
	series: [
		{
			type: 'funnel',
			left: 8, right: 8, top: 10, bottom: 10,
			minSize: '24%',
			sort: 'descending',
			gap: 3,
			label: {
				position: 'inside',
				color: '#fff',
				fontWeight: 600,
				fontSize: 12,
				formatter: (p) => `${p.name}  ${formatNumber(p.value)}`,
			},
			itemStyle: { borderColor: '#fff', borderWidth: 1, borderRadius: 4 },
			emphasis: { label: { fontSize: 13 } },
			data: props.funnel.map((s, i) => ({
				name: s.stage,
				value: s.value,
				itemStyle: { color: CATEGORICAL[i % CATEGORICAL.length] },
			})),
		},
	],
}));
</script>

<style scoped>
.sd-empty {
	padding: 40px 0;
	text-align: center;
	color: #9ca3af;
	font-size: 13px;
}
</style>
