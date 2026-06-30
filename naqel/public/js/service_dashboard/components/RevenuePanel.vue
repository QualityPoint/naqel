<!-- Revenue: monthly contracted vs pipeline trend + a collected/outstanding split. -->
<template>
	<Card :title="__('Revenue Trend')" :subtitle="__('Contracted vs pipeline, by month')">
		<ChartCanvas v-if="hasTrend" :option="option" height="300px" />
		<div v-else class="sd-empty">{{ __('No revenue in this period.') }}</div>

		<div class="sd-split">
			<div class="sd-split-bar">
				<div class="seg collected" :style="{ width: collectedPct + '%' }"></div>
				<div class="seg outstanding" :style="{ width: (100 - collectedPct) + '%' }"></div>
			</div>
			<div class="sd-split-legend">
				<span><i class="dot collected"></i>{{ __('Collected') }} · {{ money(collected) }}</span>
				<span><i class="dot outstanding"></i>{{ __('Outstanding') }} · {{ money(outstanding) }}</span>
			</div>
		</div>
	</Card>
</template>

<script setup>
import { computed } from 'vue';
import Card from './Card.vue';
import ChartCanvas from './ChartCanvas.vue';
import { PALETTE, formatFullCurrency } from '../palette';

const props = defineProps({
	data: { type: Object, default: null },
	loading: Boolean,
});

const trend = computed(() => props.data?.revenue_trend || []);
const hasTrend = computed(() => trend.value.some((r) => r.contracted || r.pipeline));
const currency = computed(() => props.data?.kpis?.currency || 'SAR');

const collected = computed(() => props.data?.collections?.collected || 0);
const outstanding = computed(() => props.data?.collections?.outstanding || 0);
const collectedPct = computed(() => {
	const total = collected.value + outstanding.value;
	return total ? Math.round((collected.value / total) * 100) : 0;
});

function money(v) {
	return formatFullCurrency(v, currency.value);
}

function monthLabel(m) {
	// "2026-01" → "Jan 26"
	const [y, mo] = (m || '').split('-');
	const names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
	return mo ? `${names[parseInt(mo, 10) - 1]} ${String(y).slice(2)}` : m;
}

const option = computed(() => ({
	grid: { left: 8, right: 16, top: 28, bottom: 24, containLabel: true },
	legend: { data: [__('Contracted'), __('Pipeline')], top: 0, right: 0, icon: 'roundRect', itemWidth: 12, itemHeight: 8, textStyle: { color: PALETTE.muted, fontSize: 11 } },
	tooltip: {
		trigger: 'axis',
		valueFormatter: (v) => formatFullCurrency(v, currency.value),
		backgroundColor: '#fff', borderColor: PALETTE.line, textStyle: { color: PALETTE.ink },
	},
	xAxis: {
		type: 'category',
		data: trend.value.map((r) => monthLabel(r.month)),
		axisLine: { lineStyle: { color: PALETTE.line } },
		axisLabel: { color: PALETTE.muted, fontSize: 11 },
		axisTick: { show: false },
	},
	yAxis: {
		type: 'value',
		splitLine: { lineStyle: { color: PALETTE.bgSoft } },
		axisLabel: { color: PALETTE.muted, fontSize: 11, formatter: (v) => compact(v) },
	},
	series: [
		area(__('Contracted'), trend.value.map((r) => r.contracted), PALETTE.primary, 'rgba(26,92,58,0.18)'),
		area(__('Pipeline'), trend.value.map((r) => r.pipeline), PALETTE.cyan, 'rgba(8,145,178,0.14)'),
	],
}));

function area(name, data, color, fill) {
	return {
		name, type: 'line', smooth: true, showSymbol: false,
		lineStyle: { width: 2.5, color },
		itemStyle: { color },
		areaStyle: { color: fill },
		data,
	};
}

function compact(v) {
	const n = Number(v || 0);
	if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(1) + 'M';
	if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(0) + 'K';
	return n;
}
</script>

<style scoped>
.sd-empty {
	padding: 40px 0;
	text-align: center;
	color: #9ca3af;
	font-size: 13px;
}
.sd-split { margin-top: 14px; }
.sd-split-bar {
	display: flex;
	height: 10px;
	border-radius: 999px;
	overflow: hidden;
	background: #eef1f0;
}
.seg.collected { background: linear-gradient(90deg, #1a5c3a, #059669); }
.seg.outstanding { background: #f59e0b; }
.sd-split-legend {
	display: flex;
	flex-wrap: wrap;
	gap: 16px;
	margin-top: 8px;
	font-size: 12px;
	color: #4b5563;
}
.sd-split-legend .dot {
	display: inline-block;
	width: 9px; height: 9px;
	border-radius: 50%;
	margin-right: 6px;
}
.dot.collected { background: #059669; }
.dot.outstanding { background: #f59e0b; }
</style>
