<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';

const __ = (s) => (window.__ ? window.__(s) : s);

const props = defineProps({
	// Reactive band objects (mutated in place); each: container_type, max_threshold,
	// count, total_converted_volume (the converted, canonical volume from simulate).
	bands: { type: Array, default: () => [] },
	containerTypes: { type: Array, default: () => [] }, // [{name, volume, volume_unit}]
	facilityUom: { type: String, default: '' },         // X-axis unit label (Facility UOM's default_uom)
	wholeThreshold: { type: Boolean, default: true },   // X measurements whole vs fractional
	unit: { type: String, default: '' },                // Y-axis canonical volume unit
	uomValue: { type: Number, default: 100 },           // live needle position
	selectedThreshold: { type: [Number, null], default: null }, // band the calc selected
	readOnly: { type: Boolean, default: false },
});
const emit = defineEmits(['change', 'add', 'remove']);

const flt = (v) => (typeof v === 'number' ? v : parseFloat(v) || 0);
const fmt = (v) => {
	const n = flt(v);
	return Number.isInteger(n) ? String(n) : parseFloat(n.toFixed(2)).toString();
};
// Snap a measurement (threshold) to whole or 2-decimal per the Facility UOM preference.
const snapMeasure = (v) => {
	const n = Math.max(0, flt(v));
	return props.wholeThreshold ? Math.round(n) : Math.round(n * 100) / 100;
};

const containerMap = computed(() =>
	Object.fromEntries(props.containerTypes.map((c) => [c.name, c]))
);
// Native container size + unit (for the per-bar label).
const stdVol = (b) => flt(containerMap.value[b.container_type]?.volume) || flt(b.container_standard_volume) || 0;
const unitOf = (b) => containerMap.value[b.container_type]?.volume_unit || b.container_volume_unit || '';
const nativeTotal = (b) => flt(b.count) * stdVol(b);          // native units → label
// Canonical (converted) volume drives the SHARED axis so mixed container units compare.
const convTotal = (b) => flt(b.total_converted_volume);      // default unit → height/axis
const perContainerConv = (b) => { const c = flt(b.count); return c > 0 ? convTotal(b) / c : 0; };

// ── Layout / scales ───────────────────────────────────────────────────────────
const wrapEl = ref(null);
const width = ref(760);
const HEIGHT = 360;
const PAD = { top: 30, right: 28, bottom: 84, left: 70 };
const BAR_W = 30;

let ro = null;
onMounted(() => {
	ro = new ResizeObserver((entries) => {
		width.value = Math.max(380, entries[0].contentRect.width || 760);
	});
	if (wrapEl.value) ro.observe(wrapEl.value);
});
onUnmounted(() => { ro?.disconnect(); window.removeEventListener('pointermove', onMove); });

const ordered = computed(() =>
	props.bands.map((b, i) => ({ b, i })).sort((a, z) => flt(a.b.max_threshold) - flt(z.b.max_threshold))
);

const xMax = computed(() =>
	Math.max(1, flt(props.uomValue), ...props.bands.map((b) => flt(b.max_threshold))) * 1.12
);
// Largest single-container converted volume — used to give the axis headroom so the
// tallest bar isn't pinned to the top (otherwise dragging the max bar never moves it).
const maxPerContainer = computed(() => Math.max(0, ...props.bands.map(perContainerConv)));
const yMax = computed(() => {
	const maxConv = Math.max(0, ...props.bands.map(convTotal));
	// ~2 extra containers of headroom above the tallest bar; grows dynamically.
	return Math.max(1, maxConv + 2 * (maxPerContainer.value || maxConv || 1));
});

const plot = computed(() => ({
	x0: PAD.left, x1: width.value - PAD.right,
	y0: HEIGHT - PAD.bottom, y1: PAD.top,
}));

const xPix = (v) => { const p = plot.value; return p.x0 + (flt(v) / xMax.value) * (p.x1 - p.x0); };
const yPix = (v) => { const p = plot.value; return p.y0 - (flt(v) / yMax.value) * (p.y0 - p.y1); };
const xInv = (px) => { const p = plot.value; return ((px - p.x0) / (p.x1 - p.x0)) * xMax.value; };

const barH = (b) => Math.max(2, plot.value.y0 - yPix(convTotal(b)));
const triangle = (cx, cy) => `${cx - 6},${cy + 14} ${cx + 6},${cy + 14} ${cx},${cy + 2}`;
const needleX = computed(() => xPix(props.uomValue));
const isSelected = (b) =>
	props.selectedThreshold != null &&
	Math.abs(flt(b.max_threshold) - flt(props.selectedThreshold)) < 1e-6;

const TICKS = 5;
const yTicks = computed(() => Array.from({ length: TICKS + 1 }, (_, i) => (yMax.value * i) / TICKS));
// X grid is dynamic: a line at each bin's threshold (plus the origin) so the gridding
// reflects how many bins are set and the intervals between them.
const xGrid = computed(() =>
	[0, ...new Set(props.bands.map((b) => flt(b.max_threshold)))].sort((a, z) => a - z)
);

// ── Drag (pointer events) ─────────────────────────────────────────────────────
let drag = null;
let debounceTimer = null;
const thrDragIdx = ref(null); // band currently being threshold-dragged (shows the counter)
const emitChange = () => {
	clearTimeout(debounceTimer);
	debounceTimer = setTimeout(() => emit('change'), 180);
};

const startCountDrag = (e, oi) => {
	if (props.readOnly) return;
	e.preventDefault();
	const b = props.bands[oi];
	const svg = wrapEl.value?.querySelector('svg');
	const rect = svg ? svg.getBoundingClientRect() : { top: 0 };
	const p = plot.value;
	// Capture the scale at drag start: the bar top then follows the cursor (snapping to
	// whole containers) without a feedback loop from yMax growing as the count rises.
	drag = {
		mode: 'count', oi,
		svgTop: rect.top,
		y0: p.y0,
		pxPerVol: (p.y0 - p.y1) / yMax.value,
		step: perContainerConv(b) || convTotal(b) || 1, // one container's converted volume
	};
	bindMove();
};

const startThresholdDrag = (e, oi) => {
	if (props.readOnly) return;
	e.preventDefault();
	drag = { mode: 'threshold', oi };
	thrDragIdx.value = oi;
	bindMove();
};

const onMove = (e) => {
	if (!drag) return;
	const b = props.bands[drag.oi];
	if (drag.mode === 'count') {
		// Volume under the cursor (fixed start scale) → nearest whole-container count.
		const vol = (drag.y0 - (e.clientY - drag.svgTop)) / drag.pxPerVol;
		const newCount = Math.max(1, Math.round(vol / drag.step));
		if (newCount !== flt(b.count)) {
			b.count = newCount;
			b.total_converted_volume = drag.step * newCount; // optimistic; simulate confirms
			emitChange();
		}
	} else if (drag.mode === 'threshold') {
		const svg = wrapEl.value?.querySelector('svg');
		if (!svg) return;
		const v = snapMeasure(xInv(e.clientX - svg.getBoundingClientRect().left));
		if (v !== flt(b.max_threshold)) { b.max_threshold = v; emitChange(); }
	}
};
const endDrag = () => { drag = null; thrDragIdx.value = null; window.removeEventListener('pointermove', onMove); };
const bindMove = () => {
	window.addEventListener('pointermove', onMove);
	window.addEventListener('pointerup', endDrag, { once: true });
};

const setContainer = (oi, name) => { props.bands[oi].container_type = name; emit('change'); };
</script>

<template>
	<div ref="wrapEl" class="eq-wrap">
		<svg :width="width" :height="HEIGHT" class="eq-svg">
			<!-- grid: even horizontal (volume), dynamic vertical at each bin threshold -->
			<g class="eq-grid">
				<line v-for="(t, i) in yTicks" :key="'y' + i" :x1="plot.x0" :y1="yPix(t)" :x2="plot.x1" :y2="yPix(t)" />
				<line v-for="(t, i) in xGrid" :key="'x' + i" :x1="xPix(t)" :y1="plot.y0" :x2="xPix(t)" :y2="plot.y1" class="eq-gridx" />
			</g>
			<text v-for="(t, i) in yTicks" :key="'yl' + i" :x="plot.x0 - 8" :y="yPix(t) + 4" text-anchor="end" class="eq-tick">{{ fmt(t) }}</text>

			<!-- axes -->
			<line :x1="plot.x0" :y1="plot.y0" :x2="plot.x1" :y2="plot.y0" class="eq-axis" />
			<line :x1="plot.x0" :y1="plot.y0" :x2="plot.x0" :y2="plot.y1" class="eq-axis" />
			<text :x="(plot.x0 + plot.x1) / 2" :y="HEIGHT - 42" text-anchor="middle" class="eq-axis-title">
				{{ __('Facility Measurement') }}<template v-if="facilityUom"> · {{ __(facilityUom) }}</template>
			</text>
			<text :x="16" :y="(plot.y0 + plot.y1) / 2" text-anchor="middle" class="eq-axis-title"
				:transform="`rotate(-90, 16, ${(plot.y0 + plot.y1) / 2})`">
				{{ __('Volume') }}<template v-if="unit"> · {{ __(unit) }}</template>
			</text>

			<!-- live needle -->
			<g v-if="uomValue">
				<line :x1="needleX" :y1="plot.y1 - 8" :x2="needleX" :y2="plot.y0" class="eq-needle" />
				<text :x="needleX" :y="plot.y1 - 12" text-anchor="middle" class="eq-needle-lbl">⟂ {{ uomValue }}</text>
			</g>

			<g v-for="{ b, i } in ordered" :key="i">
				<rect :x="xPix(b.max_threshold) - BAR_W / 2" :y="yPix(convTotal(b))" :width="BAR_W" :height="barH(b)" rx="6"
					class="eq-bar" :class="{ 'is-selected': isSelected(b), 'is-ro': readOnly }"
					@pointerdown="startCountDrag($event, i)" />
				<rect :x="xPix(b.max_threshold) - BAR_W / 2" :y="yPix(convTotal(b)) - 4" :width="BAR_W" height="7" rx="3.5"
					class="eq-cap" @pointerdown="startCountDrag($event, i)" />
				<!-- native container size (its own unit) on top, count inside -->
				<text :x="xPix(b.max_threshold)" :y="yPix(convTotal(b)) - 9" text-anchor="middle" class="eq-vol">
					{{ fmt(nativeTotal(b)) }}<template v-if="unitOf(b)"> {{ unitOf(b) }}</template>
				</text>
				<text :x="xPix(b.max_threshold)" :y="yPix(convTotal(b)) + 15" text-anchor="middle" class="eq-count">×{{ b.count }}</text>

				<polygon :points="triangle(xPix(b.max_threshold), plot.y0)" class="eq-thandle" @pointerdown="startThresholdDrag($event, i)" />
				<!-- always-on threshold value under the bar -->
				<text :x="xPix(b.max_threshold)" :y="plot.y0 + 31" text-anchor="middle" class="eq-thr-lbl">≤ {{ fmt(b.max_threshold) }}</text>

				<!-- live counter while dragging horizontally -->
				<foreignObject v-if="thrDragIdx === i" :x="xPix(b.max_threshold) - 90"
					:y="yPix(convTotal(b)) - 48" width="180" height="26" style="overflow: visible">
					<div xmlns="http://www.w3.org/1999/xhtml" class="eq-thr-wrap">
						<span class="eq-thr-pill">⟂ {{ fmt(b.max_threshold) }}<template v-if="facilityUom"> · {{ __(facilityUom) }}</template></span>
					</div>
				</foreignObject>

				<foreignObject :x="xPix(b.max_threshold) - 54" :y="plot.y0 + 40" width="108" height="28">
					<select class="eq-select" :value="b.container_type" :disabled="readOnly" @change="setContainer(i, $event.target.value)">
						<option v-for="c in containerTypes" :key="c.name" :value="c.name">{{ c.name }}</option>
					</select>
				</foreignObject>

				<text v-if="!readOnly" :x="xPix(b.max_threshold) + BAR_W / 2 + 7" :y="yPix(convTotal(b)) + 4"
					class="eq-remove" @click="emit('remove', i)">×</text>
			</g>
		</svg>

		<div class="eq-actions">
			<button class="eq-add" :disabled="readOnly" @click="emit('add')">＋ {{ __('Add band') }}</button>
			<span class="eq-hint">
				{{ __('Bars share one volume scale; each label shows its native container size. Drag ↕ adds/removes whole containers; drag the ◇ base to set the threshold.') }}
			</span>
		</div>
	</div>
</template>

<style scoped>
.eq-wrap { width: 100%; user-select: none; }
/* Keep the chart itself LTR even under an RTL UI: SVG doesn't mirror, so this keeps
   text-anchor alignment and the foreignObject selects/counter pill positioned correctly
   (the measurement axis reads left→right; the surrounding dialog stays RTL). */
.eq-svg { display: block; width: 100%; touch-action: none; direction: ltr; }
.eq-grid line { stroke: #eef2f6; stroke-width: 1; }
.eq-grid line.eq-gridx { stroke: #d7dee6; stroke-dasharray: 3 3; }
.eq-axis { stroke: #cbd5e1; stroke-width: 1.5; }
.eq-axis-title { font-size: 11px; font-weight: 700; fill: #64748b; text-transform: uppercase; letter-spacing: 0.03em; }
.eq-tick { font-size: 10px; fill: #94a3b8; }
.eq-needle { stroke: #0f172a; stroke-width: 1.5; stroke-dasharray: 4 4; }
.eq-needle-lbl { font-size: 11px; font-weight: 700; fill: #0f172a; }
.eq-bar { fill: #059669; cursor: ns-resize; transition: fill 0.12s; }
.eq-bar:hover { fill: #047857; }
.eq-bar.is-selected { fill: #d97706; }
.eq-bar.is-ro { cursor: default; fill: #94a3b8; }
.eq-cap { fill: #064e3b; cursor: ns-resize; }
.eq-vol { font-size: 10.5px; font-weight: 700; fill: #065f46; }
.eq-count { font-size: 11px; font-weight: 700; fill: #ffffff; }
.eq-thandle { fill: #475569; cursor: ew-resize; }
.eq-thandle:hover { fill: #0f172a; }
.eq-thr-lbl { font-size: 9.5px; fill: #94a3b8; }
.eq-thr-wrap { display: flex; justify-content: center; }
.eq-thr-pill {
	background: #0f172a; color: #fff; font-size: 11px; font-weight: 700;
	padding: 3px 10px; border-radius: 11px; white-space: nowrap;
	box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25);
}
.eq-remove { font-size: 16px; font-weight: 700; fill: #ef4444; cursor: pointer; }
.eq-select { width: 100%; font-size: 11px; padding: 3px 4px; border: 1px solid #d1d5db; border-radius: 6px; background: #fff; color: #111827; }
.eq-actions { display: flex; align-items: center; gap: 12px; padding: 4px 2px; flex-wrap: wrap; }
.eq-add { padding: 6px 12px; border: 1px solid #059669; color: #059669; background: #fff; border-radius: 8px; font-weight: 600; cursor: pointer; }
.eq-add:disabled { opacity: 0.5; cursor: not-allowed; }
.eq-hint { font-size: 12px; color: #6b7280; }
</style>
