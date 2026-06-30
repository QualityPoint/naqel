<!-- Presentational card: elegant surface with an optional title/subtitle header. -->
<template>
	<section class="sd-card">
		<header v-if="title || $slots.actions" class="sd-card-head">
			<div>
				<h3 class="sd-card-title">{{ title }}</h3>
				<p v-if="subtitle" class="sd-card-sub">{{ subtitle }}</p>
			</div>
			<div class="sd-card-actions"><slot name="actions" /></div>
		</header>
		<div class="sd-card-body"><slot /></div>
	</section>
</template>

<script setup>
defineProps({
	title: { type: String, default: '' },
	subtitle: { type: String, default: '' },
});
</script>

<style scoped>
.sd-card {
	background: #fff;
	border: 1px solid #eef1f0;
	border-radius: 14px;
	box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04), 0 8px 24px rgba(16, 24, 40, 0.04);
	display: flex;
	flex-direction: column;
	overflow: hidden;
}
.sd-card-head {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	gap: 12px;
	padding: 16px 18px 0;
}
.sd-card-title {
	margin: 0;
	font-size: 14px;
	font-weight: 700;
	letter-spacing: 0.01em;
	color: #111827;
}
.sd-card-sub {
	margin: 2px 0 0;
	font-size: 12px;
	color: #6b7280;
}
.sd-card-body {
	padding: 14px 18px 18px;
	flex: 1;
	min-height: 0;
}
</style>
