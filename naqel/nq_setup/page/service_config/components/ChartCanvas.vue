<template>
	<div class="sc-canvas-wrapper">
		<!-- Phase-1 loading overlay -->
		<Transition name="fade">
			<div v-if="loading" class="sc-canvas-loading">
				<div class="sc-loading-spinner"></div>
			</div>
		</Transition>

		<!-- Empty state: shown only when no data at all after loading -->
		<div v-if="isEmpty" class="sc-canvas-empty">
			<div class="sc-empty-icon">
				<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5"
					stroke-linecap="round" stroke-linejoin="round">
					<rect x="4" y="8" width="40" height="32" rx="4"/>
					<polyline points="4 28 14 18 22 24 32 14 44 22"/>
					<circle cx="14" cy="18" r="2.5" fill="currentColor" stroke="none"/>
					<circle cx="22" cy="24" r="2.5" fill="currentColor" stroke="none"/>
					<circle cx="32" cy="14" r="2.5" fill="currentColor" stroke="none"/>
				</svg>
			</div>
			<p class="sc-empty-title">{{ $t('No configurations found') }}</p>
			<p class="sc-empty-sub">{{ $t('Adjust the filters above and click Refresh.') }}</p>
		</div>

		<!-- ECharts mount point — always in DOM so the chart can resize correctly -->
		<div ref="chartEl" class="sc-echarts-root"></div>
	</div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue';
import * as echarts from 'echarts';

const props = defineProps({
	chartData:    { type: Array,   default: () => [] },
	loading:      { type: Boolean, default: false },
	dataRevision: { type: Number,  default: 0 },
	byWasteType:  { type: Boolean, default: false },
});

const emit = defineEmits(['edit']);

// ── ISIC level colour palette ─────────────────────────────────────────────────
const ISIC_COLORS = {
	Section:  '#7c3aed',
	Division: '#0284c7',
	Group:    '#059669',
	Category: '#d97706',
	Activity: '#dc2626',
};

// ── Waste-type colour palette (stacked mode) ──────────────────────────────────
// Distinct from ISIC colours; cycles when there are more than 12 waste types.
const WASTE_TYPE_COLORS = [
	'#6366f1', '#f59e0b', '#10b981', '#ef4444', '#3b82f6',
	'#8b5cf6', '#f97316', '#14b8a6', '#ec4899', '#06b6d4',
	'#84cc16', '#a855f7',
];

const UNMATCHED_COLOR   = '#cbd5e1';
const UNMATCHED_OPACITY = 0.35;
const VISIBLE_BARS      = 50;

const $t = (s) => __(s);
const isRTL = () => frappe.utils.is_rtl();

// ── Refs ──────────────────────────────────────────────────────────────────────
const chartEl = ref(null);
let chart = null;

// Track revision so updateChart knows when to preserve vs. reset zoom
let lastRevision  = -1;
// Track previous data length so Phase-2 zoom preservation converts bar indices correctly
let lastDataLen   = 0;

// ── Computed ──────────────────────────────────────────────────────────────────
const isEmpty = computed(() => !props.loading && props.chartData.length === 0);

// ── ECharts option builder ───────────────────────────────────────────────��────
function buildOption(data) {
	// Truncate long labels so the x-axis stays readable
	const labels = data.map(d => {
		const t = d.title || d.name || '';
		return t.length > 24 ? t.slice(0, 22) + '…' : t;
	});

	const seriesData = data.map(d => {
		const matched = !!d.uom_match;
		return {
			value: matched ? (d.calculated_waste || 0) : 0,
			_raw:  d,     // kept for the tooltip formatter
			itemStyle: matched
				? {
					color: ISIC_COLORS[d.isic_level] || '#4f46e5',
					borderRadius: [4, 4, 0, 0],
				}
				: {
					color:        UNMATCHED_COLOR,
					opacity:      UNMATCHED_OPACITY,
					borderRadius: [2, 2, 0, 0],
				},
			emphasis: matched
				? { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,.18)' } }
				: { disabled: true },
		};
	});

	// Initial dataZoom window: show VISIBLE_BARS bars regardless of total count
	const endPct = data.length <= VISIBLE_BARS
		? 100
		: Math.round(VISIBLE_BARS / data.length * 100);

	return {
		backgroundColor: 'transparent',

		grid: {
			top: 24, right: 20, bottom: 78, left: 20,
			containLabel: true,
		},

		xAxis: {
			type: 'category',
			data: labels,
			inverse: isRTL(),
			axisLabel: {
				fontSize: 10,
				color: 'var(--text-muted, #64748b)',
				rotate: isRTL() ? -40 : 40,
				interval: 0,
				overflow: 'truncate',
				width: 80,
			},
			axisLine: { lineStyle: { color: 'var(--border-color, #e2e8f0)' } },
			axisTick: { show: false },
		},

		yAxis: {
			type: 'value',
			position: isRTL() ? 'right' : 'left',
			axisLabel: {
				fontSize: 10,
				color: 'var(--text-muted, #64748b)',
				formatter: v => v === 0 ? '0' : v.toFixed(2),
			},
			splitLine: {
				lineStyle: { color: 'var(--border-color, #f1f5f9)', type: 'dashed' },
			},
			axisLine: { show: false },
			axisTick: { show: false },
		},

		// ── dataZoom: slider (visible) + inside (mouse-wheel / touch) ────────
		dataZoom: [
			{
				type:          'slider',
				xAxisIndex:    0,
				bottom:        8,
				height:        20,
				start:         0,
				end:           endPct,
				fillerColor:   'rgba(79,70,229,0.08)',
				borderColor:   'var(--border-color, #e2e8f0)',
				handleStyle:   { color: '#4f46e5' },
				moveHandleStyle: { color: '#4f46e5' },
				textStyle:     { color: 'var(--text-muted, #64748b)', fontSize: 10 },
				showDetail:    false,
				brushSelect:   false,
			},
			{ type: 'inside', xAxisIndex: 0 },
		],

		// ── Tooltip ───────────────────────────────────────────────────────────
		tooltip: {
			trigger: 'axis',
			axisPointer: { type: 'shadow' },
			backgroundColor: 'transparent',
			borderWidth: 0,
			padding: 0,
			formatter(params) {
				const p = params[0];
				if (!p) return '';
				const d  = p.data._raw;
				const c  = d.uom_match
					? (ISIC_COLORS[d.isic_level] || '#4f46e5')
					: UNMATCHED_COLOR;
				const rate = (d.mean_generation_rate || 0).toFixed(4);
				const waste = d.uom_match && d.calculated_waste
					? `${(+d.calculated_waste).toFixed(4)} ${__(d.default_volume_unit || '')}`
					: null;
				const container = d.uom_match && d.suggested_container
					? `${d.suggested_container_count ? d.suggested_container_count + ' × ' : ''}${d.suggested_container}`
					: null;

				return `
<div style="
	min-width:230px;font-family:inherit;
	background:#fff;border:1.5px solid #e2e8f0;
	border-radius:12px;overflow:hidden;
	box-shadow:0 4px 20px rgba(0,0,0,.12);
	direction:${isRTL() ? 'rtl' : 'ltr'}">
  <div style="height:3px;background:${c}"></div>
  <div style="padding:10px 13px">
	<div style="font-size:12px;font-weight:700;color:#0f172a;margin-bottom:7px;line-height:1.35">
	  ${d.title || d.name}
	</div>
	<div style="display:flex;flex-direction:column;gap:4px;font-size:11px">
	  ${d.isic_level ? `
	  <div style="display:flex;justify-content:space-between;gap:16px">
		<span style="color:#94a3b8">${__('ISIC Level')}</span>
		<b style="color:${c}">${__(d.isic_level)}</b>
	  </div>` : ''}
	  <div style="display:flex;justify-content:space-between;gap:16px">
		<span style="color:#94a3b8">${__('Facility UOM')}</span>
		<b style="color:#334155">${d.facility_uom ? __(d.facility_uom) : '—'}</b>
	  </div>
	  <div style="display:flex;justify-content:space-between;gap:16px">
		<span style="color:#94a3b8">${__('Mean Rate')}</span>
		<b style="color:#334155">${rate}</b>
	  </div>
	  <div style="margin-top:5px;padding-top:5px;border-top:1px solid #e2e8f0;display:flex;flex-direction:column;gap:4px">
		<div style="display:flex;justify-content:space-between;gap:16px">
		  <span style="color:#94a3b8">${__('Calculated Waste')}</span>
		  ${waste
			? `<b style="color:${c}">${waste}</b>`
			: `<span style="color:#f59e0b;font-size:10px">⚠ ${__('UOM mismatch')}</span>`
		  }
		</div>
		${container ? `
		<div style="display:flex;justify-content:space-between;gap:16px">
		  <span style="color:#94a3b8">${__('Container')}</span>
		  <b style="color:#334155">${container}</b>
		</div>` : ''}
	  </div>
	</div>
  </div>
</div>`;
			},
		},

		// ── Single series, per-item styling ───────────────────────────────────
		series: [
			{
				type:            'bar',
				data:            seriesData,
				barMaxWidth:     40,
				barMinHeight:    4,    // unmatched (value=0) still render as 4px stubs
				barCategoryGap:  '28%',
				large:           true,  // ECharts canvas optimisation for large datasets
				largeThreshold:  400,
			},
		],
	};
}

// ── Stacked-by-waste-type option builder ──────────────────────────────────────
function buildStackedOption(data) {
	const labels = data.map(d => {
		const t = d.title || d.name || '';
		return t.length > 24 ? t.slice(0, 22) + '…' : t;
	});

	// Collect all unique waste types, preserving first-seen order.
	const seenWt = new Set();
	const allWasteTypes = [];
	for (const d of data) {
		for (const w of (d.waste_distributions || [])) {
			if (!seenWt.has(w.waste_type)) {
				seenWt.add(w.waste_type);
				allWasteTypes.push(w.waste_type);
			}
		}
	}

	const hasUnclassified = data.some(d => !d.waste_distributions?.length);

	// One series per waste type.
	const series = allWasteTypes.map((wt, idx) => {
		const color = WASTE_TYPE_COLORS[idx % WASTE_TYPE_COLORS.length];
		return {
			name:           wt,
			type:           'bar',
			stack:          'waste',
			barMaxWidth:    40,
			barCategoryGap: '28%',
			large:          true,
			largeThreshold: 400,
			itemStyle:      { color },
			data: data.map(d => {
				const matched = !!d.uom_match;
				const dists   = d.waste_distributions || [];
				// Config has no distributions → handled by the Unclassified series.
				if (!dists.length) return { value: 0, _raw: d };
				const dist = dists.find(w => w.waste_type === wt);
				if (!dist) return { value: 0, _raw: d };
				return {
					value:     matched ? (d.calculated_waste * dist.pct / 100) : 0,
					_raw:      d,
					_pct:      dist.pct,
					itemStyle: matched
						? { color }
						: { color: UNMATCHED_COLOR, opacity: UNMATCHED_OPACITY },
					emphasis:  matched
						? { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,.18)' } }
						: { disabled: true },
				};
			}),
		};
	});

	// Configs with no distributions fall through to this series, preserving
	// the single-bar current behaviour (ISIC colour, barMinHeight stub).
	if (hasUnclassified) {
		series.push({
			name:           __('Unclassified'),
			type:           'bar',
			stack:          'waste',
			barMaxWidth:    40,
			barCategoryGap: '28%',
			barMinHeight:   4,
			large:          true,
			largeThreshold: 400,
			data: data.map(d => {
				if (d.waste_distributions?.length) return { value: 0, _raw: d };
				const matched = !!d.uom_match;
				return {
					value:     matched ? (d.calculated_waste || 0) : 0,
					_raw:      d,
					itemStyle: matched
						? { color: ISIC_COLORS[d.isic_level] || '#4f46e5', borderRadius: [4, 4, 0, 0] }
						: { color: UNMATCHED_COLOR, opacity: UNMATCHED_OPACITY, borderRadius: [2, 2, 0, 0] },
					emphasis:  matched
						? { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,.18)' } }
						: { disabled: true },
				};
			}),
		});
	}

	const endPct = data.length <= VISIBLE_BARS
		? 100
		: Math.round(VISIBLE_BARS / data.length * 100);

	return {
		backgroundColor: 'transparent',

		grid: {
			top: 24, right: 20, bottom: 108, left: 20,
			containLabel: true,
		},

		legend: {
			show:            true,
			type:            'scroll',
			bottom:          36,
			height:          32,
			itemWidth:       10,
			itemHeight:      10,
			borderRadius:    5,
			textStyle:       { fontSize: 10, color: 'var(--text-muted, #64748b)' },
			pageTextStyle:   { color: 'var(--text-muted, #64748b)', fontSize: 10 },
			pageIconColor:   '#4f46e5',
			pageIconInactiveColor: 'var(--border-color, #e2e8f0)',
			formatter: name => __(name),
		},

		xAxis: {
			type: 'category',
			data: labels,
			inverse: isRTL(),
			axisLabel: {
				fontSize: 10,
				color: 'var(--text-muted, #64748b)',
				rotate: isRTL() ? -40 : 40,
				interval: 0,
				overflow: 'truncate',
				width: 80,
			},
			axisLine: { lineStyle: { color: 'var(--border-color, #e2e8f0)' } },
			axisTick: { show: false },
		},

		yAxis: {
			type: 'value',
			position: isRTL() ? 'right' : 'left',
			axisLabel: {
				fontSize: 10,
				color: 'var(--text-muted, #64748b)',
				formatter: v => v === 0 ? '0' : v.toFixed(2),
			},
			splitLine: {
				lineStyle: { color: 'var(--border-color, #f1f5f9)', type: 'dashed' },
			},
			axisLine: { show: false },
			axisTick: { show: false },
		},

		dataZoom: [
			{
				type:          'slider',
				xAxisIndex:    0,
				bottom:        8,
				height:        20,
				start:         0,
				end:           endPct,
				fillerColor:   'rgba(79,70,229,0.08)',
				borderColor:   'var(--border-color, #e2e8f0)',
				handleStyle:   { color: '#4f46e5' },
				moveHandleStyle: { color: '#4f46e5' },
				textStyle:     { color: 'var(--text-muted, #64748b)', fontSize: 10 },
				showDetail:    false,
				brushSelect:   false,
			},
			{ type: 'inside', xAxisIndex: 0 },
		],

		tooltip: {
			trigger: 'axis',
			axisPointer: { type: 'shadow' },
			backgroundColor: 'transparent',
			borderWidth: 0,
			padding: 0,
			formatter(params) {
				if (!params?.length) return '';
				// params[0] is enough to get _raw; all params share the same config.
				const raw = params.find(p => p.data?._raw)?.data._raw;
				if (!raw) return '';

				const matched   = !!raw.uom_match;
				const dists     = raw.waste_distributions || [];
				const total     = raw.calculated_waste || 0;
				const isicColor = ISIC_COLORS[raw.isic_level] || '#4f46e5';
				const headerC   = matched ? isicColor : UNMATCHED_COLOR;
				const container = matched && raw.suggested_container
					? `${raw.suggested_container_count ? raw.suggested_container_count + ' × ' : ''}${raw.suggested_container}`
					: null;

				const distRows = dists.map((w) => {
					const globalIdx = allWasteTypes.indexOf(w.waste_type);
					const c = globalIdx >= 0
						? WASTE_TYPE_COLORS[globalIdx % WASTE_TYPE_COLORS.length]
						: WASTE_TYPE_COLORS[0];
					const amount = matched ? (total * w.pct / 100) : 0;
					return `
					<div style="display:flex;justify-content:space-between;gap:16px;align-items:center">
						<span style="display:flex;align-items:center;gap:5px;color:#94a3b8">
							<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${c};flex-shrink:0"></span>
							${__(w.waste_type)}
						</span>
						<b style="color:#334155">${w.pct}% &nbsp;·&nbsp; ${amount.toFixed(4)}</b>
					</div>`;
				}).join('');

				return `
<div style="min-width:240px;font-family:inherit;background:#fff;border:1.5px solid #e2e8f0;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,.12);direction:${isRTL() ? 'rtl' : 'ltr'}">
  <div style="height:3px;background:${headerC}"></div>
  <div style="padding:10px 13px">
    <div style="font-size:12px;font-weight:700;color:#0f172a;margin-bottom:7px;line-height:1.35">${raw.title || raw.name}</div>
    <div style="display:flex;flex-direction:column;gap:4px;font-size:11px">
      ${raw.isic_level ? `<div style="display:flex;justify-content:space-between;gap:16px"><span style="color:#94a3b8">${__('ISIC Level')}</span><b style="color:${isicColor}">${__(raw.isic_level)}</b></div>` : ''}
      <div style="display:flex;justify-content:space-between;gap:16px">
        <span style="color:#94a3b8">${__('Total Waste')}</span>
        ${matched
			? `<b style="color:#334155">${total.toFixed(4)} ${__(raw.default_volume_unit || '')}</b>`
			: `<span style="color:#f59e0b;font-size:10px">⚠ ${__('UOM mismatch')}</span>`}
      </div>
      ${container ? `
      <div style="display:flex;justify-content:space-between;gap:16px">
        <span style="color:#94a3b8">${__('Container')}</span>
        <b style="color:#334155">${container}</b>
      </div>` : ''}
      ${dists.length ? `
      <div style="margin-top:5px;padding-top:5px;border-top:1px solid #e2e8f0">
        <div style="color:#94a3b8;margin-bottom:4px;font-size:10px;text-transform:uppercase;letter-spacing:.05em">${__('Waste Breakdown')}</div>
        ${distRows}
      </div>` : ''}
    </div>
  </div>
</div>`;
			},
		},

		series,
	};
}

// ── Chart lifecycle ───────────────────────────────────────────────────────────
function initChart() {
	if (!chartEl.value) return;
	if (chart) { chart.dispose(); chart = null; }
	chart = echarts.init(chartEl.value, null, { renderer: 'canvas' });
	// Click a bar → open the configuration editor for that config.
	chart.on('click', (params) => {
		const raw = params?.data?._raw;
		if (raw?.name) emit('edit', raw.name);
	});
}

function updateChart() {
	if (!chart) { initChart(); }
	if (!chart) return;

	if (!props.chartData.length) {
		chart.clear();
		return;
	}

	const newOpt = props.byWasteType
		? buildStackedOption(props.chartData)
		: buildOption(props.chartData);

	const isFullReset = props.dataRevision !== lastRevision;
	lastRevision = props.dataRevision;

	if (!isFullReset) {
		// Phase-2 append: preserve the user's scroll position but recalculate the
		// window size in bar-index space so that adding ~2700 unmatched bars does
		// not squash the chart when Phase 1 returned few rows (≤ VISIBLE_BARS).
		//
		// The old code preserved the *percentage* window, which is wrong when Phase 1
		// returned e.g. 20 bars (end=100%) and Phase 2 appends 2780 more: the
		// preserved 100% window would show all 2800 bars squashed together.
		//
		// The fix: convert Phase-1 percentages → absolute bar indices → back to
		// percentages relative to the new total N.
		const curOpt = chart.getOption();
		const dz     = Array.isArray(curOpt?.dataZoom) ? curOpt.dataZoom[0] : null;
		if (dz?.start !== undefined && lastDataLen > 0) {
			const newN      = props.chartData.length;
			const startBar  = (dz.start / 100) * lastDataLen;
			const endBar    = (dz.end   / 100) * lastDataLen;
			// Ensure the window shows at least VISIBLE_BARS bars in the new dataset
			const minEndBar = startBar + VISIBLE_BARS;
			newOpt.dataZoom[0].start = (startBar / newN) * 100;
			newOpt.dataZoom[0].end   = Math.min(100, (Math.max(endBar, minEndBar) / newN) * 100);
		}
	}

	lastDataLen = props.chartData.length;
	chart.setOption(newOpt, { notMerge: true, lazyUpdate: false });
}

function resizeChart() {
	chart?.resize();
}

onMounted(async () => {
	await nextTick();
	initChart();
	window.addEventListener('resize', resizeChart, { passive: true });
});

onBeforeUnmount(() => {
	window.removeEventListener('resize', resizeChart);
	if (chart) { chart.dispose(); chart = null; }
});

// Shallow watch: we replace the array reference, not mutate it
watch(() => props.chartData, updateChart);
</script>

<style scoped>
.sc-canvas-wrapper {
	flex: 1;
	min-height: 0;
	overflow: hidden;
	position: relative;
	display: flex;
	flex-direction: column;
	background: var(--bg-color, #fff);
}

.sc-echarts-root {
	flex: 1;
	width: 100%;
	min-height: 0;
}

/* ── Loading overlay ─────────────────────────────────────── */
.sc-canvas-loading {
	position: absolute;
	inset: 0;
	z-index: 20;
	background: color-mix(in srgb, var(--bg-color, #fff) 85%, transparent);
	display: flex;
	align-items: center;
	justify-content: center;
	backdrop-filter: blur(2px);
}
.sc-loading-spinner {
	width: 28px;
	height: 28px;
	border: 2.5px solid var(--border-color, #e2e8f0);
	border-top-color: var(--primary, #4f46e5);
	border-radius: 50%;
	animation: sc-spin .65s linear infinite;
}
@keyframes sc-spin { to { transform: rotate(360deg); } }

.fade-enter-active, .fade-leave-active { transition: opacity .2s; }
.fade-enter-from,  .fade-leave-to      { opacity: 0; }

/* ── Empty state ────────────────────────────���────────────── */
.sc-canvas-empty {
	position: absolute;
	inset: 0;
	z-index: 5;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	gap: 6px;
	pointer-events: none;
}
.sc-empty-icon {
	width: 56px;
	height: 56px;
	color: var(--text-muted, #c4cdd6);
	margin-bottom: 4px;
}
.sc-empty-icon svg { width: 100%; height: 100%; }
.sc-empty-title {
	font-size: 14px;
	font-weight: 700;
	color: var(--text-color, #334155);
	margin: 0;
}
.sc-empty-sub {
	font-size: 12px;
	color: var(--text-muted, #94a3b8);
	margin: 0;
}
</style>
