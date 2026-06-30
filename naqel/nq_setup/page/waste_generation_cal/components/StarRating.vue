<script setup>
import { ref, onMounted } from 'vue';
import { __ } from './i18n';

const props = defineProps({
	// Rating in stars (0..max). Supports .5 steps when fractional ratings are enabled.
	modelValue: { type: Number, default: 0 },
	max: { type: Number, default: () => (window.naqel?.RATING_MAX_STARS || 5) },
});
const emit = defineEmits(['update:modelValue']);

const hover = ref(0);
const allowFractional = ref(false);
const isRtl = ref(false);

onMounted(() => {
	isRtl.value = (document.documentElement.dir || document.body.dir) === 'rtl';
	// Reuse the shared Service Settings reader so the desk forms and this page stay
	// in sync from a single source of truth.
	if (window.naqel?.allow_fractional_rating) {
		naqel.allow_fractional_rating().then((v) => { allowFractional.value = !!v; });
	}
});

// Resolve the star value under the pointer. With fractional ratings the leading half
// of a star yields x.5; otherwise the whole star. RTL flips which half is leading.
const valueAt = (event, star) => {
	if (!allowFractional.value) return star;
	const rect = event.currentTarget.getBoundingClientRect();
	const ratio = (event.clientX - rect.left) / rect.width;
	const leadingHalf = isRtl.value ? ratio > 0.5 : ratio < 0.5;
	return leadingHalf ? star - 0.5 : star;
};

const onMove = (event, star) => { hover.value = valueAt(event, star); };

const onClick = (event, star) => {
	const value = valueAt(event, star);
	// Click the current value again to clear it.
	emit('update:modelValue', value === props.modelValue ? 0 : value);
};

const fillPercent = (star) => {
	const display = hover.value || props.modelValue;
	if (star <= display) return 100;
	if (star - 0.5 <= display) return 50;
	return 0;
};
</script>

<template>
	<div class="rating-control">
		<div class="stars-row" @mouseleave="hover = 0">
			<button
				v-for="star in max"
				:key="star"
				type="button"
				class="star-btn"
				:aria-label="`${star} / ${max}`"
				@mousemove="onMove($event, star)"
				@click="onClick($event, star)"
			>
				<span class="star-glyph star-bg">★</span>
				<span class="star-glyph star-fg" :style="{ inlineSize: `${fillPercent(star)}%` }">★</span>
			</button>
		</div>
		<button
			v-if="modelValue"
			type="button"
			class="clear-btn"
			:aria-label="__('Clear rating')"
			:title="__('Clear rating')"
			@click="emit('update:modelValue', 0)"
		>✕</button>
	</div>
</template>

<style scoped>
.rating-control {
	display: flex;
	align-items: center;
	gap: 10px;
}
.stars-row {
	display: flex;
	gap: 6px;
}
.clear-btn {
	background: none;
	border: none;
	cursor: pointer;
	color: #9ca3af;
	font-size: 16px;
	line-height: 1;
	padding: 2px;
	transition: color 0.1s;
}
.clear-btn:hover {
	color: #ef4444;
}
.star-btn {
	position: relative;
	width: 1em;
	height: 1em;
	font-size: 28px;
	line-height: 1;
	background: none;
	border: none;
	padding: 0;
	cursor: pointer;
}
.star-glyph {
	position: absolute;
	inset-block-start: 0;
	inset-inline-start: 0;
	display: inline-block;
	width: 1em;
	overflow: hidden;
	white-space: nowrap;
	transition: color 0.1s;
}
.star-bg {
	color: #d1d5db;
}
.star-fg {
	color: #f59e0b;
	inline-size: 0;
}
</style>
