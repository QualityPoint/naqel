<!-- Interactive facility map (Leaflet). Uses vector circle-markers (no image assets
     to bundle) sized/coloured by data, with OpenStreetMap tiles. Leaflet's CSS is
     vendored at /assets/naqel/css/leaflet.css and injected once. -->
<template>
	<div class="sd-map-wrap">
		<div ref="mapEl" class="sd-map"></div>
		<div v-if="!points.length" class="sd-map-empty">{{ __('No geolocated facilities in this period.') }}</div>
	</div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue';
import L from 'leaflet';

const props = defineProps({
	points: { type: Array, default: () => [] },
});

const LEAFLET_CSS = '/assets/naqel/css/leaflet.css';
const mapEl = ref(null);
let map = null;
let layer = null;

function ensureCss() {
	if (document.getElementById('naqel-leaflet-css')) return;
	const link = document.createElement('link');
	link.id = 'naqel-leaflet-css';
	link.rel = 'stylesheet';
	link.href = LEAFLET_CSS;
	document.head.appendChild(link);
}

function ratingColor(rating) {
	// Green for high ratings → amber/red for low; grey when unrated.
	if (!rating) return '#64748b';
	if (rating >= 4) return '#059669';
	if (rating >= 3) return '#65a30d';
	if (rating >= 2) return '#f59e0b';
	return '#ef4444';
}

function draw() {
	if (!map) return;
	if (layer) { layer.remove(); layer = null; }
	layer = L.layerGroup().addTo(map);

	const latlngs = [];
	props.points.forEach((p) => {
		if (!p.lat || !p.lng) return;
		latlngs.push([p.lat, p.lng]);
		const m = L.circleMarker([p.lat, p.lng], {
			radius: 7,
			color: '#fff',
			weight: 1.5,
			fillColor: ratingColor(p.rating),
			fillOpacity: 0.9,
		});
		const lines = [
			`<b>${frappe.utils.escape_html(p.label || p.name || '')}</b>`,
			p.city ? frappe.utils.escape_html(p.city) : '',
			p.territory ? frappe.utils.escape_html(p.territory) : '',
			p.rating ? `${'★'.repeat(Math.round(p.rating))}` : '',
		].filter(Boolean);
		m.bindPopup(lines.join('<br/>'));
		m.on('click', () => frappe.set_route('Form', 'Facility', p.name));
		m.addTo(layer);
	});

	if (latlngs.length) {
		map.fitBounds(L.latLngBounds(latlngs).pad(0.2), { maxZoom: 12 });
	}
}

onMounted(async () => {
	ensureCss();
	await nextTick();
	if (!mapEl.value) return;
	map = L.map(mapEl.value, { scrollWheelZoom: false, attributionControl: true })
		.setView([23.8859, 45.0792], 5); // default: Saudi Arabia
	L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
		maxZoom: 19,
		attribution: '&copy; OpenStreetMap',
	}).addTo(map);
	// Map needs a sizing tick after mount inside flex/grid containers.
	setTimeout(() => map && map.invalidateSize(), 60);
	draw();
});

onBeforeUnmount(() => {
	if (map) { map.remove(); map = null; }
	layer = null;
});

watch(() => props.points, draw, { deep: false });
</script>

<style scoped>
.sd-map-wrap {
	position: relative;
	height: 380px;
	border-radius: 10px;
	overflow: hidden;
	border: 1px solid #e8eeeb;
}
.sd-map {
	height: 100%;
	width: 100%;
	background: #eef3f1;
}
.sd-map-empty {
	position: absolute;
	inset: 0;
	display: grid;
	place-items: center;
	color: #9ca3af;
	font-size: 13px;
	pointer-events: none;
}
</style>
