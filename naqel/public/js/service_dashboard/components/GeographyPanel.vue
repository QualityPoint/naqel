<!-- Geography: interactive facility map + territory / country breakdowns. -->
<template>
	<div class="sd-grid sd-geo">
		<Card :title="__('Facility Locations')" :subtitle="mapSubtitle">
			<MapCanvas :points="points" />
		</Card>

		<div class="sd-geo-side">
			<Card :title="__('Facilities by Territory')">
				<ChartCanvas v-if="territory.length" :option="barOption(territory)" :height="barHeight(territory)" />
				<div v-else class="sd-empty">{{ __('No territory data') }}</div>
			</Card>
			<Card :title="__('Facilities by Country')">
				<ChartCanvas v-if="country.length" :option="barOption(country, true)" :height="barHeight(country)" />
				<div v-else class="sd-empty">{{ __('No country data') }}</div>
			</Card>
		</div>
	</div>
</template>

<script setup>
import { computed } from 'vue';
import Card from './Card.vue';
import ChartCanvas from './ChartCanvas.vue';
import MapCanvas from './MapCanvas.vue';
import { PALETTE, formatNumber } from '../palette';

const props = defineProps({
	geography: { type: Object, default: () => ({}) },
	currency: { type: String, default: 'SAR' },
	loading: Boolean,
});

const points = computed(() => props.geography.map_points || []);
const territory = computed(() => (props.geography.by_territory || []).slice(0, 12));
const country = computed(() => (props.geography.by_country || []).slice(0, 8));

const mapSubtitle = computed(() =>
	__('{0} facilities geolocated', [formatNumber(points.value.length)]));

function barHeight(rows) {
	return Math.max(180, rows.length * 26 + 40) + 'px';
}

function barOption(rows, accentCyan = false) {
	// Sort ascending so the largest bar sits at the top of a horizontal bar chart.
	const sorted = [...rows].sort((a, b) => a.value - b.value);
	const color = accentCyan ? PALETTE.cyan : PALETTE.primary;
	return {
		grid: { left: 8, right: 28, top: 8, bottom: 8, containLabel: true },
		tooltip: {
			trigger: 'axis', axisPointer: { type: 'shadow' },
			formatter: (p) => `${p[0].name}<br/><b>${formatNumber(p[0].value)}</b>`,
			backgroundColor: '#fff', borderColor: PALETTE.line, textStyle: { color: PALETTE.ink },
		},
		xAxis: {
			type: 'value', splitLine: { lineStyle: { color: PALETTE.bgSoft } },
			axisLabel: { color: PALETTE.muted, fontSize: 11 },
		},
		yAxis: {
			type: 'category',
			data: sorted.map((r) => r.name),
			axisLine: { lineStyle: { color: PALETTE.line } },
			axisTick: { show: false },
			axisLabel: { color: PALETTE.ink, fontSize: 11, width: 120, overflow: 'truncate' },
		},
		series: [
			{
				type: 'bar',
				data: sorted.map((r) => r.value),
				barWidth: '58%',
				itemStyle: {
					borderRadius: [0, 6, 6, 0],
					color: { type: 'linear', x: 0, y: 0, x2: 1, y2: 0, colorStops: [
						{ offset: 0, color: accentCyan ? '#22d3ee' : '#1a5c3a' },
						{ offset: 1, color: color },
					] },
				},
				label: { show: true, position: 'right', color: PALETTE.muted, fontSize: 11, formatter: (p) => formatNumber(p.value) },
			},
		],
	};
}
</script>

<style scoped>
.sd-grid { display: grid; gap: 14px; margin-top: 14px; }
.sd-geo { grid-template-columns: 1.5fr 1fr; align-items: stretch; }
.sd-geo-side { display: flex; flex-direction: column; gap: 14px; }
@media (max-width: 1100px) {
	.sd-geo { grid-template-columns: 1fr; }
}
.sd-empty {
	padding: 36px 0; text-align: center; color: #9ca3af; font-size: 13px;
}
</style>
