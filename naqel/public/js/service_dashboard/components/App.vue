<!-- Service Dashboard root. Loads filter options + default date range, fetches data,
     and lays out the sections. State comes from the injected shared store. -->
<template>
	<div class="sd-app">
		<FilterBar />

		<div v-if="error" class="sd-state sd-error">{{ error }}</div>

		<template v-else>
			<KpiCards :kpis="kpis" :loading="loading" />

			<div class="sd-grid sd-grid-2">
				<RevenuePanel :data="data" :loading="loading" />
				<FunnelPanel :funnel="funnel" :loading="loading" />
			</div>

			<StatusBreakdowns :status="status" :loading="loading" />

			<GeographyPanel :geography="geography" :currency="currency" :loading="loading" />

			<TopLists :top="top" :currency="currency" :loading="loading" />
		</template>

		<div v-if="loading" class="sd-loading-bar"><span></span></div>
	</div>
</template>

<script setup>
import { inject, computed, onMounted } from 'vue';
import FilterBar from './FilterBar.vue';
import KpiCards from './KpiCards.vue';
import RevenuePanel from './RevenuePanel.vue';
import FunnelPanel from './FunnelPanel.vue';
import StatusBreakdowns from './StatusBreakdowns.vue';
import GeographyPanel from './GeographyPanel.vue';
import TopLists from './TopLists.vue';

const store = inject('store');

const data = computed(() => store.data.value);
const loading = computed(() => store.loading.value);
const error = computed(() => store.error.value);

const kpis = computed(() => data.value?.kpis || {});
const funnel = computed(() => data.value?.funnel || []);
const status = computed(() => data.value?.status || {});
const geography = computed(() => data.value?.geography || {});
const top = computed(() => data.value?.top || {});
const currency = computed(() => kpis.value.currency || 'SAR');

onMounted(async () => {
	await store.loadOptions();
	// Default window: start of the current year → today.
	const today = store.options.value.today || frappe.datetime.get_today();
	store.filters.to_date = today;
	store.filters.from_date = today.slice(0, 4) + '-01-01';
	store.fetch();
});
</script>

<style scoped>
.sd-app {
	padding: 14px 16px 40px;
	background:
		radial-gradient(1200px 360px at 12% -8%, #eef7f1 0%, rgba(238, 247, 241, 0) 60%),
		#f6f8f7;
	min-height: calc(100vh - 120px);
	font-feature-settings: 'tnum' 1;
}
.sd-grid {
	display: grid;
	gap: 14px;
	margin-top: 14px;
}
.sd-grid-2 {
	grid-template-columns: 1.4fr 1fr;
}
@media (max-width: 1100px) {
	.sd-grid-2 { grid-template-columns: 1fr; }
}
.sd-state {
	padding: 28px;
	text-align: center;
	border-radius: 12px;
	font-size: 13px;
}
.sd-error {
	background: #fef2f2;
	color: #b91c1c;
	border: 1px solid #fecaca;
	margin-top: 14px;
}
.sd-loading-bar {
	position: fixed;
	top: 0; left: 0; right: 0;
	height: 3px;
	background: transparent;
	overflow: hidden;
	z-index: 60;
}
.sd-loading-bar span {
	display: block;
	height: 100%;
	width: 35%;
	background: linear-gradient(90deg, #1a5c3a, #059669);
	animation: sd-indeterminate 1.1s infinite ease-in-out;
}
@keyframes sd-indeterminate {
	0% { transform: translateX(-100%); }
	100% { transform: translateX(320%); }
}
</style>
