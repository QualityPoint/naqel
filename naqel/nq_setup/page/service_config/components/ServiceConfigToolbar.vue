<template>
	<div class="sc-toolbar">
		<!-- Left: linked filters + inputs -->
		<div class="sc-toolbar__left">

			<!-- Service Type -->
			<select
				class="sc-select"
				:value="serviceType"
				@change="$emit('update:serviceType', $event.target.value)"
			>
				<option v-for="s in serviceTypesList" :key="s.name" :value="s.name">
					{{ s.service_name || s.name }}
				</option>
			</select>

			<div class="sc-vr"></div>

			<!-- ISIC Classification -->
			<span class="sc-filter-label">{{ $t('ISIC Category') }}</span>
			<select
				class="sc-select"
				:value="isicClassification"
				@change="$emit('update:isicClassification', $event.target.value)"
			>
				<option value="Section">{{ $t('Section') }}</option>
				<option value="Division">{{ $t('Division') }}</option>
				<option value="Group">{{ $t('Group') }}</option>
				<option value="Category">{{ $t('Category') }}</option>
				<option value="Activity">{{ $t('Activity') }}</option>
			</select>

			<div class="sc-vr"></div>

			<!-- UOM -->
			<span class="sc-filter-label">{{ $t('UOM') }}</span>
			<select
				class="sc-select"
				:value="uom"
				@change="$emit('update:uom', $event.target.value)"
			>
				<option v-for="u in uomList" :key="u.name" :value="u.name">
					{{ u.uom_name || u.name }}
				</option>
			</select>

			<div class="sc-vr"></div>

			<!-- UOM Value -->
			<span class="sc-filter-label">{{ $t('UOM Value') }}</span>
			<input
				type="number"
				class="sc-number-input"
				:value="uomValue"
				min="0"
				step="any"
				:placeholder="$t('Default: 100')"
				@input="$emit('update:uomValue', $event.target.value === '' ? null : parseFloat($event.target.value))"
			/>

			<div class="sc-vr"></div>

			<!-- Calculate Facility Wastes By -->
			<span class="sc-filter-label">{{ $t('Calculate Facility Wastes By') }}</span>
			<select
				class="sc-select"
				:value="wasteCalcBy"
				@change="$emit('update:wasteCalcBy', $event.target.value)"
			>
				<option value="generation_rate">{{ $t('Generation Rate') }}</option>
				<option value="cluster_classification">{{ $t('Cluster Classification') }}</option>
			</select>

			<div class="sc-vr"></div>

			<!-- Calculate Generation Rate By -->
			<span class="sc-filter-label">{{ $t('Calculate Generation Rate By') }}</span>
			<select
				class="sc-select"
				:value="rateType"
				@change="$emit('update:rateType', $event.target.value)"
			>
				<option value="mean">{{ $t('Mean') }}</option>
				<option value="median">{{ $t('Median') }}</option>
			</select>
		</div>

		<!-- Center: analyze-by toggle (conditional) + sort pill group -->
		<div class="sc-toolbar__center">
			<!-- "Total | By Waste Type" radio — only when the service type has multiple waste types -->
			<Transition name="sc-fade">
				<div v-if="showByWasteTypeToggle" class="sc-analyze-group">
					<span class="sc-filter-label">{{ $t('Analyze By') }}</span>
					<div class="sc-pill-group" role="radiogroup" :aria-label="$t('Analyze By')">
						<button
							v-for="opt in analyzeByOptions"
							:key="String(opt.value)"
							class="sc-pill"
							:class="{ 'is-active': byWasteType === opt.value }"
							@click="$emit('update:byWasteType', opt.value)"
						>
							{{ $t(opt.label) }}
						</button>
						<div class="sc-pill-track" :style="analyzeTrackStyle"></div>
					</div>
				</div>
			</Transition>

			<div class="sc-pill-group" role="group">
				<button
					v-for="s in sortOptions"
					:key="s.value"
					class="sc-pill"
					:class="{ 'is-active': sortOrder === s.value }"
					@click="$emit('update:sortOrder', s.value)"
				>
					{{ $t(s.label) }}
				</button>
				<div class="sc-pill-track" :style="trackStyle"></div>
			</div>
		</div>

		<!-- Right: refresh -->
		<div class="sc-toolbar__right">
			<button
				class="sc-refresh-btn"
				:class="{ 'is-spinning': loading }"
				:disabled="loading"
				:title="$t('Refresh')"
				@click="$emit('refresh')"
			>
				<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8"
					stroke-linecap="round" stroke-linejoin="round">
					<path d="M13.5 2.5A6.5 6.5 0 1 0 15 8"/>
					<polyline points="10.5 1 15 1 15 5.5"/>
				</svg>
				<span>{{ $t('Refresh') }}</span>
			</button>
		</div>
	</div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
	serviceType:      { type: String,  default: '' },
	isicClassification:{ type: String, default: '' },
	uom:              { type: String,  default: '' },
	uomValue:         { type: [Number, null], default: null },
	wasteCalcBy:           { type: String,  default: 'generation_rate' },
	rateType:              { type: String,  default: 'mean' },
	byWasteType:           { type: Boolean, default: false },
	showByWasteTypeToggle: { type: Boolean, default: false },
	sortOrder:             { type: String,  default: 'normal' },
	loading:          { type: Boolean, default: false },
	serviceTypesList: { type: Array,   default: () => [] },
	uomList:          { type: Array,   default: () => [] },
});

defineEmits([
	'update:serviceType', 'update:isicClassification',
	'update:uom', 'update:uomValue',
	'update:wasteCalcBy', 'update:rateType',
	'update:byWasteType',
	'update:sortOrder',
	'refresh',
]);

const $t = (s) => __(s);

const sortOptions = [
	{ value: 'desc',   label: 'DESC'   },
	{ value: 'normal', label: 'Normal' },
	{ value: 'asc',    label: 'ASC'    },
];

const trackStyle = computed(() => {
	const idx    = sortOptions.findIndex(s => s.value === props.sortOrder);
	const n      = sortOptions.length;
	const isRtl  = document.documentElement.dir === 'rtl';
	const dir    = isRtl ? -1 : 1;
	return { width: `calc((100% - 6px) / ${n})`, transform: `translateX(${dir * idx * 100}%)` };
});

// "Total | By Waste Type" radio toggle — only rendered when showByWasteTypeToggle is true
const analyzeByOptions = [
	{ value: false, label: 'Total'         },
	{ value: true,  label: 'Waste Type' },
];

const analyzeTrackStyle = computed(() => {
	const idx   = props.byWasteType ? 1 : 0;
	const isRtl = document.documentElement.dir === 'rtl';
	const dir   = isRtl ? -1 : 1;
	return { width: 'calc((100% - 6px) / 2)', transform: `translateX(${dir * idx * 100}%)` };
});
</script>

<style scoped>
/* ── Toolbar shell ─────────────────────────────────────────── */
.sc-toolbar {
	display: flex;
	align-items: center;
	gap: 12px;
	padding: 9px 20px;
	background: var(--fg-color, #ffffff);
	border-bottom: 1px solid var(--border-color, #e8ecf0);
	box-shadow: 0 1px 0 0 rgba(0,0,0,.04), 0 2px 8px rgba(0,0,0,.04);
	flex-wrap: wrap;
	position: relative;
	z-index: 10;
	min-height: 52px;
}

.sc-toolbar__left   { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.sc-toolbar__center { display: flex; align-items: center; flex: 1; justify-content: center; gap: 12px; }
.sc-toolbar__right  { display: flex; align-items: center; gap: 10px; margin-left: auto; }

/* ── Analyze-by group ────────────────────────────────────── */
.sc-analyze-group {
	display: flex;
	align-items: center;
	gap: 6px;
}
/* Force the two analyze pills to equal width via grid so the sliding track
   aligns correctly regardless of text length difference (Total vs Waste Type) */
.sc-analyze-group .sc-pill-group {
	display: grid;
	grid-template-columns: 1fr 1fr;
}

/* Fade transition for the analyze-by toggle */
.sc-fade-enter-active, .sc-fade-leave-active { transition: opacity .2s, transform .2s; }
.sc-fade-enter-from, .sc-fade-leave-to       { opacity: 0; transform: scale(.95); }

/* ── Divider ─────────────────────────────────────────────── */
.sc-vr { width: 1px; height: 22px; background: var(--border-color, #e2e8f0); flex-shrink: 0; }

/* ── Inline filter label ─────────────────────────────────── */
.sc-filter-label {
	font-size: 11px;
	font-weight: 600;
	color: var(--text-muted, #64748b);
	white-space: nowrap;
	user-select: none;
}

/* ── Select ──────────────────────────────────────────────── */
.sc-select {
	padding: 5px 10px;
	font-size: 12.5px;
	font-weight: 500;
	color: var(--text-color, #1e293b);
	background: var(--control-bg, #f6f8fa);
	border: 1.5px solid var(--border-color, #e2e8f0);
	border-radius: 9px;
	cursor: pointer;
	outline: none;
	min-width: 140px;
	transition: border-color .15s, box-shadow .15s;
}
.sc-select:focus,
.sc-select:hover {
	border-color: var(--primary, #4f46e5);
	box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary, #4f46e5) 10%, transparent);
}
[data-theme="dark"] .sc-select:focus,
[data-theme="dark"] .sc-select:hover {
	border-color: var(--text-muted, #94a3b8);
	box-shadow: 0 0 0 3px rgba(255,255,255,0.08);
}

/* ── UOM Value number input ──────────────────────────────── */
.sc-number-input {
	padding: 5px 10px;
	font-size: 12.5px;
	font-weight: 500;
	color: var(--text-color, #1e293b);
	background: var(--control-bg, #f6f8fa);
	border: 1.5px solid var(--border-color, #e2e8f0);
	border-radius: 9px;
	outline: none;
	width: 100px;
	transition: border-color .15s, box-shadow .15s;
	font-family: inherit;
}
.sc-number-input::placeholder { color: var(--text-muted, #94a3b8); }
.sc-number-input:focus,
.sc-number-input:hover {
	border-color: var(--primary, #4f46e5);
	box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary, #4f46e5) 10%, transparent);
}
/* hide browser spin arrows */
.sc-number-input::-webkit-outer-spin-button,
.sc-number-input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
.sc-number-input[type=number] { -moz-appearance: textfield; }

/* ── Sort pill group ─────────────────────────────────────── */
.sc-pill-group {
	display: flex;
	position: relative;
	padding: 3px;
	background: var(--control-bg, #f1f5f9);
	border: 1.5px solid var(--border-color, #e2e8f0);
	border-radius: 10px;
	gap: 0;
}
.sc-pill-track {
	position: absolute;
	top: 3px;
	left: 3px;
	height: calc(100% - 6px);
	background: var(--fg-color, #fff);
	border-radius: 7px;
	box-shadow: 0 1px 4px rgba(0,0,0,.10);
	transition: transform .2s cubic-bezier(.34,1.28,.64,1), width .2s;
	pointer-events: none;
	z-index: 0;
}
[dir="rtl"] .sc-pill-track { left: auto; right: 3px; }
.sc-pill {
	position: relative;
	z-index: 1;
	flex: 1;
	padding: 4px 20px;
	border: none; background: transparent; border-radius: 7px;
	font-size: 12px; font-weight: 500; color: var(--text-muted, #64748b);
	cursor: pointer;
	transition: color .15s;
	white-space: nowrap;
	text-align: center;
	font-family: inherit;
}
.sc-pill:hover:not(.is-active) { color: var(--text-color, #1e293b); }
.sc-pill.is-active {
	color: var(--primary, #4f46e5);
	font-weight: 700;
}
[data-theme="dark"] .sc-pill.is-active { color: #fff; }

/* ── Refresh button ──────────────────────────────────────── */
.sc-refresh-btn {
	display: inline-flex;
	align-items: center;
	gap: 6px;
	height: 32px;
	padding: 0 12px 0 10px;
	border: 1.5px solid var(--border-color, #e2e8f0);
	border-radius: 9px;
	background: var(--fg-color, #fff);
	cursor: pointer;
	font-size: 12px;
	font-weight: 600;
	color: var(--text-muted, #64748b);
	font-family: inherit;
	transition: background .15s, border-color .15s, color .15s, box-shadow .15s;
	white-space: nowrap;
}
.sc-refresh-btn svg { width: 13px; height: 13px; flex-shrink: 0; }
.sc-refresh-btn:hover:not(:disabled) {
	background: var(--control-bg, #f1f5f9);
	border-color: var(--primary, #4f46e5);
	color: var(--primary, #4f46e5);
	box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary, #4f46e5) 10%, transparent);
}
.sc-refresh-btn:disabled { opacity: .5; cursor: not-allowed; }
.sc-refresh-btn.is-spinning svg { animation: sc-spin .7s linear infinite; }
@keyframes sc-spin { to { transform: rotate(360deg); } }
</style>
