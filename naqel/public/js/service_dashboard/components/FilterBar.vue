<!-- Global filters: date-range presets (+ custom), Company, Service Type, Territory.
     Every change re-fetches via the shared store. -->
<template>
	<div class="sd-filterbar">
		<div class="sd-presets">
			<button
				v-for="p in presets"
				:key="p.key"
				class="sd-pill"
				:class="{ active: activePreset === p.key }"
				@click="applyPreset(p)"
			>{{ p.label }}</button>
		</div>

		<div class="sd-fields">
			<label class="sd-field sd-dates" :class="{ on: activePreset === 'custom' }">
				<span class="sd-field-label">{{ __('From') }}</span>
				<input type="date" v-model="filters.from_date" @change="onCustomDate" />
			</label>
			<label class="sd-field sd-dates">
				<span class="sd-field-label">{{ __('To') }}</span>
				<input type="date" v-model="filters.to_date" @change="onCustomDate" />
			</label>

			<label class="sd-field">
				<span class="sd-field-label">{{ __('Company') }}</span>
				<select v-model="filters.company" @change="reload">
					<option :value="null">{{ __('All') }}</option>
					<option v-for="c in options.companies" :key="c.name" :value="c.name">{{ c.name }}</option>
				</select>
			</label>

			<label class="sd-field">
				<span class="sd-field-label">{{ __('Service Type') }}</span>
				<select v-model="filters.service_type" @change="reload">
					<option :value="null">{{ __('All') }}</option>
					<option v-for="s in options.service_types" :key="s.name" :value="s.name">
						{{ s.service_name || s.name }}
					</option>
				</select>
			</label>

			<label class="sd-field">
				<span class="sd-field-label">{{ __('Territory') }}</span>
				<select v-model="filters.territory" @change="reload">
					<option :value="null">{{ __('All') }}</option>
					<option v-for="t in options.territories" :key="t.name" :value="t.name">
						{{ (t.division_name || t.name) + (t.division_category ? ' · ' + t.division_category : '') }}
					</option>
				</select>
			</label>
		</div>
	</div>
</template>

<script setup>
import { inject, ref, computed } from 'vue';

const store = inject('store');
const filters = store.filters;
const options = computed(() => store.options.value);

const activePreset = ref('ytd');

const presets = [
	{ key: 'mtd', label: __('This Month') },
	{ key: 'qtd', label: __('This Quarter') },
	{ key: 'ytd', label: __('This Year') },
	{ key: 'l12', label: __('Last 12 Months') },
	{ key: 'all', label: __('All Time') },
];

function isoToday() {
	return store.options.value.today || frappe.datetime.get_today();
}

function applyPreset(p) {
	activePreset.value = p.key;
	const today = isoToday();
	const d = new Date(today + 'T00:00:00');
	let from = null;
	if (p.key === 'mtd') from = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-01`;
	else if (p.key === 'qtd') {
		const q = Math.floor(d.getMonth() / 3) * 3;
		from = `${d.getFullYear()}-${pad(q + 1)}-01`;
	} else if (p.key === 'ytd') from = `${d.getFullYear()}-01-01`;
	else if (p.key === 'l12') from = frappe.datetime.add_months(today, -12);
	else if (p.key === 'all') { from = null; }

	filters.from_date = from;
	filters.to_date = p.key === 'all' ? null : today;
	store.fetch();
}

function onCustomDate() {
	activePreset.value = 'custom';
	if (filters.from_date && filters.to_date) store.fetch();
}

function reload() {
	store.fetch();
}

function pad(n) {
	return String(n).padStart(2, '0');
}
</script>

<style scoped>
.sd-filterbar {
	display: flex;
	flex-wrap: wrap;
	align-items: flex-end;
	gap: 14px 18px;
	padding: 14px 16px;
	background: #fff;
	border: 1px solid #eef1f0;
	border-radius: 14px;
	box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
}
.sd-presets {
	display: flex;
	flex-wrap: wrap;
	gap: 6px;
}
.sd-pill {
	border: 1px solid #d8e3dd;
	background: #f3f7f5;
	color: #2f4a3f;
	font-size: 12px;
	font-weight: 600;
	padding: 6px 12px;
	border-radius: 999px;
	cursor: pointer;
	transition: all 0.15s ease;
}
.sd-pill:hover { background: #e8f3ed; }
.sd-pill.active {
	background: linear-gradient(135deg, #1a5c3a, #059669);
	border-color: transparent;
	color: #fff;
	box-shadow: 0 2px 8px rgba(5, 150, 105, 0.28);
}
.sd-fields {
	display: flex;
	flex-wrap: wrap;
	gap: 10px 14px;
	align-items: flex-end;
}
.sd-field {
	display: flex;
	flex-direction: column;
	gap: 4px;
}
.sd-field-label {
	font-size: 11px;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.04em;
	color: #6b7280;
}
.sd-field select,
.sd-field input {
	height: 32px;
	min-width: 150px;
	border: 1px solid #d8e3dd;
	border-radius: 8px;
	padding: 0 10px;
	font-size: 13px;
	color: #111827;
	background: #fff;
	outline: none;
}
.sd-field select:focus,
.sd-field input:focus {
	border-color: #059669;
	box-shadow: 0 0 0 3px rgba(5, 150, 105, 0.12);
}
.sd-dates input { min-width: 140px; }
</style>
