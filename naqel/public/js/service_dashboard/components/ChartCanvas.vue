<!-- Generic echarts wrapper. Pass an echarts `option`; re-renders on change and
     resizes with its container (ResizeObserver) — robust inside flex/grid layouts. -->
<template>
	<div ref="el" class="chart-canvas" :style="{ height }"></div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue';
import * as echarts from 'echarts';

const props = defineProps({
	option: { type: Object, default: () => ({}) },
	height: { type: String, default: '320px' },
});

const el = ref(null);
let chart = null;
let ro = null;

function render() {
	if (!chart) return;
	chart.setOption(props.option || {}, { notMerge: true, lazyUpdate: true });
}

onMounted(async () => {
	await nextTick();
	if (!el.value) return;
	chart = echarts.init(el.value, null, { renderer: 'canvas' });
	render();
	ro = new ResizeObserver(() => chart && chart.resize());
	ro.observe(el.value);
});

onBeforeUnmount(() => {
	if (ro) { ro.disconnect(); ro = null; }
	if (chart) { chart.dispose(); chart = null; }
});

watch(() => props.option, render, { deep: true });
</script>

<style scoped>
.chart-canvas {
	width: 100%;
}
</style>
