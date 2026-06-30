<!-- Ranked tables: top customers and top service types by contracted revenue. -->
<template>
	<div class="sd-grid sd-grid-2">
		<Card :title="__('Top Customers')" :subtitle="__('By contracted revenue')">
			<ul v-if="customers.length" class="sd-rank">
				<li v-for="(r, i) in customers" :key="r.id">
					<span class="sd-rank-no">{{ i + 1 }}</span>
					<span class="sd-rank-name" :title="r.name || r.id">{{ r.name || r.id }}</span>
					<span class="sd-rank-meta">{{ r.contracts }} {{ __('contracts') }}</span>
					<span class="sd-rank-bar"><i :style="{ width: pct(r.revenue, customers) + '%' }"></i></span>
					<span class="sd-rank-val">{{ money(r.revenue) }}</span>
				</li>
			</ul>
			<div v-else class="sd-empty">{{ __('No contracts in this period.') }}</div>
		</Card>

		<Card :title="__('Top Service Types')" :subtitle="__('By contracted revenue')">
			<ul v-if="serviceTypes.length" class="sd-rank">
				<li v-for="(r, i) in serviceTypes" :key="r.id">
					<span class="sd-rank-no alt">{{ i + 1 }}</span>
					<span class="sd-rank-name" :title="r.name || r.id">{{ r.name || r.id }}</span>
					<span class="sd-rank-meta">{{ r.contracts }} {{ __('contracts') }}</span>
					<span class="sd-rank-bar"><i class="alt" :style="{ width: pct(r.revenue, serviceTypes) + '%' }"></i></span>
					<span class="sd-rank-val">{{ money(r.revenue) }}</span>
				</li>
			</ul>
			<div v-else class="sd-empty">{{ __('No contracts in this period.') }}</div>
		</Card>
	</div>
</template>

<script setup>
import { computed } from 'vue';
import Card from './Card.vue';
import { formatFullCurrency } from '../palette';

const props = defineProps({
	top: { type: Object, default: () => ({}) },
	currency: { type: String, default: 'SAR' },
	loading: Boolean,
});

const customers = computed(() => props.top.customers || []);
const serviceTypes = computed(() => props.top.service_types || []);

function money(v) {
	return formatFullCurrency(v, props.currency);
}
function pct(value, rows) {
	const max = Math.max(...rows.map((r) => r.revenue || 0), 1);
	return Math.round(((value || 0) / max) * 100);
}
</script>

<style scoped>
.sd-grid { display: grid; gap: 14px; margin-top: 14px; }
.sd-grid-2 { grid-template-columns: 1fr 1fr; }
@media (max-width: 1100px) { .sd-grid-2 { grid-template-columns: 1fr; } }

.sd-rank { list-style: none; margin: 0; padding: 0; }
.sd-rank li {
	display: grid;
	grid-template-columns: 22px minmax(120px, 1.4fr) auto 1fr auto;
	align-items: center;
	gap: 10px;
	padding: 9px 0;
	border-bottom: 1px solid #f1f4f3;
	font-size: 13px;
}
.sd-rank li:last-child { border-bottom: none; }
.sd-rank-no {
	width: 22px; height: 22px;
	display: grid; place-items: center;
	border-radius: 6px;
	background: #e8f3ed; color: #1a5c3a;
	font-size: 11px; font-weight: 700;
}
.sd-rank-no.alt { background: #e0f2fe; color: #0e7490; }
.sd-rank-name {
	font-weight: 600; color: #111827;
	white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.sd-rank-meta { color: #9ca3af; font-size: 11.5px; white-space: nowrap; }
.sd-rank-bar { height: 8px; background: #eef1f0; border-radius: 999px; overflow: hidden; }
.sd-rank-bar i { display: block; height: 100%; background: linear-gradient(90deg, #1a5c3a, #059669); }
.sd-rank-bar i.alt { background: linear-gradient(90deg, #0e7490, #22d3ee); }
.sd-rank-val { font-weight: 700; color: #0f172a; white-space: nowrap; }
.sd-empty { padding: 30px 0; text-align: center; color: #9ca3af; font-size: 13px; }
</style>
