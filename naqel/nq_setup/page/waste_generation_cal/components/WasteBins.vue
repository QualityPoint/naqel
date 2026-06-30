<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { __ } from './i18n';

const props = defineProps({
	wasteTypes: { type: Array, default: () => [] }, // WasteDistribution[]
	wasteTypesCache: { type: Object, default: () => ({}) }, // Record<string, WasteType[]>
	droppedItems: { type: Object, default: () => ({}) }, // Record<containerKey, WasteType[]>
	loadingWasteTypes: { type: Boolean, default: false },
});

const emit = defineEmits(['drop', 'remove-item', 'clear-all']);

const selectedContainer = ref(null);
const dragOverContainer = ref(null);
const isPanelVisible = ref(false);
const panelRef = ref(null);

// Color palette matching the React version
const colorSchemes = [
	{ border: '#16a34a', bg: '#f0fdf4', text: '#14532d', lid: '#16a34a', dashed: '#86efac', badge: '#bbf7d0' },
	{ border: '#0d9488', bg: '#f0fdfa', text: '#134e4a', lid: '#0d9488', dashed: '#5eead4', badge: '#99f6e4' },
	{ border: '#65a30d', bg: '#f7fee7', text: '#365314', lid: '#65a30d', dashed: '#bef264', badge: '#d9f99d' },
	{ border: '#059669', bg: '#ecfdf5', text: '#064e3b', lid: '#059669', dashed: '#6ee7b7', badge: '#a7f3d0' },
	{ border: '#15803d', bg: '#f0fdf4', text: '#14532d', lid: '#15803d', dashed: '#86efac', badge: '#bbf7d0' },
	{ border: '#0891b2', bg: '#ecfeff', text: '#164e63', lid: '#0891b2', dashed: '#67e8f9', badge: '#a5f3fc' },
];

const getColor = (index) => colorSchemes[index % colorSchemes.length];

// Allowed waste types per container (from cache)
const getAllowedTypes = (distribution) => {
	const cached = props.wasteTypesCache[distribution.waste_type];
	if (cached && cached.length > 0) return cached;
	if (!distribution.is_group) {
		// Fallback: look across all cache values
		return Object.values(props.wasteTypesCache)
			.flat()
			.filter((wt) => wt.name === distribution.waste_type);
	}
	return [];
};

// Filtered types for the currently selected container
const filteredTypes = computed(() => {
	if (!selectedContainer.value) return [];
	const dist = props.wasteTypes.find((d) => d.waste_type === selectedContainer.value);
	if (!dist) return [];
	return getAllowedTypes(dist);
});

// Whether a waste item is already dropped in any container
const isDroppedAnywhere = (itemName) =>
	Object.values(props.droppedItems).flat().some((d) => d.name === itemName);

// Click on a bin
const handleContainerClick = (containerKey) => {
	if (selectedContainer.value === containerKey && isPanelVisible.value) {
		isPanelVisible.value = false;
		selectedContainer.value = null;
	} else {
		selectedContainer.value = containerKey;
		isPanelVisible.value = true;
	}
};

// Drag from panel
const handleDragStart = (e, item) => {
	e.dataTransfer.effectAllowed = 'move';
	e.dataTransfer.setData('application/json', JSON.stringify(item));
};

const handleDragOver = (e, containerKey) => {
	e.preventDefault();
	e.dataTransfer.dropEffect = 'move';
	dragOverContainer.value = containerKey;
};

const handleDragLeave = () => {
	dragOverContainer.value = null;
};

const handleDrop = (e, distribution, containerKey) => {
	e.preventDefault();
	e.stopPropagation();
	dragOverContainer.value = null;
	try {
		const item = JSON.parse(e.dataTransfer.getData('application/json'));
		const allowed = getAllowedTypes(distribution);
		if (!allowed.some((wt) => wt.name === item.name)) return;
		const existing = props.droppedItems[containerKey] || [];
		if (existing.some((d) => d.name === item.name)) return;
		emit('drop', { item, containerKey, groupName: distribution.waste_type });
	} catch {
		frappe.show_alert({ message: __('Failed to process dropped waste item'), indicator: 'red' }, 3);
	}
};

// Click-outside detection to close panel
const handleClickOutside = (e) => {
	if (!panelRef.value) return;
	const clickedInPanel = panelRef.value.contains(e.target);
	const clickedOnBin = e.target.closest('.waste-bin-card');
	if (!clickedInPanel && !clickedOnBin && isPanelVisible.value) {
		isPanelVisible.value = false;
		selectedContainer.value = null;
	}
};

onMounted(() => document.addEventListener('mousedown', handleClickOutside));
onUnmounted(() => document.removeEventListener('mousedown', handleClickOutside));

const hasAnyDropped = computed(() =>
	Object.values(props.droppedItems).some((arr) => arr.length > 0)
);
</script>

<template>
	<div class="bins-root">
		<h2 class="bins-title">{{ __('Waste Containers') }}</h2>
		<p class="bins-desc">
			{{ __('Click on a container to view its waste types, then drag and drop waste from the panel') }}
		</p>

		<!-- Bins grid -->
		<div class="bins-grid" :class="{ 'bins-grid-shifted': isPanelVisible }">
			<div
				v-for="(dist, index) in wasteTypes"
				:key="dist.waste_type"
				class="waste-bin-card"
				@click="handleContainerClick(dist.waste_type)"
			>
				<!-- Bin visual -->
				<div class="bin-outer">
					<div
						class="bin-body"
						:class="{
							'bin-drag-over': dragOverContainer === dist.waste_type,
							'bin-selected': selectedContainer === dist.waste_type,
						}"
						:style="{
							background: getColor(index).bg,
							borderColor: getColor(index).border,
						}"
						@drop="handleDrop($event, dist, dist.waste_type)"
						@dragover="handleDragOver($event, dist.waste_type)"
						@dragleave="handleDragLeave"
					>
						<!-- Lid -->
						<div class="bin-lid" :style="{ background: getColor(index).lid }"></div>
						<!-- Handle -->
					<div class="bin-handle" :style="{ borderColor: getColor(index).lid }"></div>
						<!-- Content area -->
						<div
							class="bin-content"
							:style="{ borderColor: getColor(index).dashed, background: getColor(index).bg }"
						>
							<template v-if="(droppedItems[dist.waste_type] || []).length > 0">
								<div
									v-for="item in droppedItems[dist.waste_type]"
									:key="item.name"
									class="bin-chip"
									:style="{ borderColor: getColor(index).border, color: getColor(index).text }"
									@click.stop="emit('remove-item', { containerKey: dist.waste_type, itemName: item.name, groupName: dist.waste_type })"
									:title="__('Click to remove')"
								>
									<span class="bin-chip-text">{{ __(item.waste_name) }}</span>
									<span class="bin-chip-remove">×</span>
								</div>
							</template>
							<div v-else class="bin-empty-text" :style="{ color: getColor(index).text }">
								{{
									selectedContainer === dist.waste_type
										? __('Drag waste from the right')
										: __('Click to view waste')
								}}
							</div>
						</div>
					</div>
				</div>

				<!-- Label below bin -->
				<h3 class="bin-name" :style="{ color: getColor(index).text }">
					{{ __(dist.waste_name) }}
				</h3>
				<div class="bin-id-badge">{{ __(dist.waste_type) }}</div>
				<p class="bin-meta">
					{{ dist.is_group ? __('Group') : __('Specific type') }} — {{ dist.distribution_percentage }}%
				</p>
				<span
					v-if="selectedContainer === dist.waste_type"
					class="bin-selected-badge"
					:style="{ background: getColor(index).badge, color: getColor(index).text }"
				>
					{{ __('Selected') }}
				</span>
			</div>
		</div>

		<!-- Floating Waste Types Panel -->
		<transition name="panel-slide">
			<div v-if="isPanelVisible" ref="panelRef" class="waste-panel">
				<div class="panel-header">
					<h3 class="panel-title">{{ __('Waste Types') }}</h3>
					<p class="panel-subtitle">
						{{
							selectedContainer
								? __('Drag and drop into the container')
								: __('Click on a container to view its types')
						}}
					</p>
					<button class="panel-close" @click="isPanelVisible = false; selectedContainer = null">×</button>
				</div>

				<div class="panel-body">
					<!-- Loading -->
					<div v-if="loadingWasteTypes" class="panel-loading">
						<div class="spinner"></div>
					</div>

					<!-- Waste type list -->
					<template v-else-if="selectedContainer">
						<div v-if="filteredTypes.length > 0" class="type-list">
							<div
								v-for="item in filteredTypes"
								:key="item.name"
								class="type-item"
								:class="{ 'type-item-used': isDroppedAnywhere(item.name) }"
								:draggable="!isDroppedAnywhere(item.name)"
								@dragstart="handleDragStart($event, item)"
							>
								<span class="type-name">{{ __(item.waste_name) }}</span>
								<span v-if="isDroppedAnywhere(item.name)" class="type-used-badge">✓ {{ __('Added') }}</span>
							</div>
						</div>
						<div v-else class="panel-empty">
							<p>{{ __('No waste types available for this container') }}</p>
						</div>
					</template>

					<!-- No container selected -->
					<div v-else class="panel-empty">
						<div class="panel-empty-icon">🗑️</div>
						<p>{{ __('Click on one of the containers to view its types') }}</p>
					</div>
				</div>

				<!-- Clear all button -->
				<div v-if="hasAnyDropped" class="panel-footer">
					<button class="clear-all-btn" @click="emit('clear-all')">
						{{ __('Clear All Dropped Waste') }}
					</button>
				</div>
			</div>
		</transition>
	</div>
</template>

<style scoped>
.bins-root {
	position: relative;
	margin-top: 32px;
}
.bins-title {
	font-size: 26px;
	font-weight: 700;
	color: #064e3b;
	margin: 0 0 8px 0;
}
.bins-desc {
	font-size: 14px;
	color: #6b7280;
	margin: 0 0 24px 0;
}
.bins-grid {
	display: flex;
	flex-wrap: wrap;
	justify-content: center;
	gap: 32px;
	transition: padding 0.3s;
}
.bins-grid-shifted {
	padding-inline-end: 320px;
}
.waste-bin-card {
	display: flex;
	flex-direction: column;
	align-items: center;
	cursor: pointer;
	min-width: 160px;
}
.bin-outer {
	position: relative;
	margin-top: 24px; /* room for the handle + lid above the body */
	margin-bottom: 12px;
}
.bin-body {
	width: 140px;
	height: 185px;
	border: 3px solid;
	border-radius: 6px 6px 24px 24px;
	position: relative;
	overflow: visible;
	transition: transform 0.2s, box-shadow 0.2s;
}
/* Vertical ridge lines */
.bin-body::before {
	content: '';
	position: absolute;
	inset: 0;
	border-radius: inherit;
	background: repeating-linear-gradient(
		90deg,
		transparent 0px,
		transparent 26px,
		rgba(0, 0, 0, 0.055) 26px,
		rgba(0, 0, 0, 0.055) 28px
	);
	pointer-events: none;
	z-index: 0;
	overflow: hidden;
	border-radius: 6px 6px 24px 24px;
}
.bin-body:hover {
	transform: translateY(-2px);
	box-shadow: 0 8px 20px rgba(0, 0, 0, 0.12);
}
.bin-drag-over {
	transform: scale(1.08) !important;
	box-shadow: 0 12px 28px rgba(0, 0, 0, 0.18) !important;
}
.bin-selected {
	transform: scale(1.04);
	box-shadow: 0 8px 20px rgba(0, 0, 0, 0.15);
}
.bin-lid {
	position: absolute;
	top: -18px;
	left: -10px;
	width: calc(100% + 20px);
	height: 20px;
	border-radius: 6px 6px 0 0;
	z-index: 2;
}
.bin-handle {
	position: absolute;
	top: -36px;
	left: 50%;
	transform: translateX(-50%);
	width: 38px;
	height: 18px;
	border: 3px solid;
	border-bottom: none;
	border-radius: 20px 20px 0 0;
	background: transparent !important;
	z-index: 3;
}
.bin-content {
	position: absolute;
	top: 10px;
	left: 6px;
	right: 6px;
	bottom: 6px;
	border: 2px dashed;
	border-radius: 4px 4px 18px 18px;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: flex-start;
	overflow-y: auto;
	padding: 4px;
	gap: 4px;
	z-index: 1;
}
.bin-chip {
	width: 100%;
	background: white;
	border: 1px solid;
	border-radius: 6px;
	padding: 4px 8px;
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 4px;
	font-size: 11px;
	font-weight: 500;
	cursor: pointer;
	transition: background 0.15s, border-color 0.15s;
	box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}
.bin-chip:hover {
	background: #fef2f2;
	border-color: #fca5a5 !important;
}
.bin-chip-text {
	flex: 1;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}
.bin-chip-remove {
	color: #ef4444;
	font-weight: 700;
	font-size: 14px;
	flex-shrink: 0;
}
.bin-empty-text {
	font-size: 11px;
	text-align: center;
	margin: auto;
	padding: 4px;
}
.bin-name {
	font-size: 16px;
	font-weight: 700;
	text-align: center;
	margin: 0 0 6px 0;
}
.bin-id-badge {
	background: #f3f4f6;
	border-radius: 8px;
	padding: 4px 10px;
	font-size: 11px;
	color: #374151;
	font-weight: 500;
	text-align: center;
	max-width: 160px;
	word-break: break-all;
}
.bin-meta {
	font-size: 12px;
	color: #6b7280;
	text-align: center;
	margin: 4px 0 0 0;
}
.bin-selected-badge {
	display: inline-block;
	margin-top: 6px;
	padding: 3px 10px;
	border-radius: 999px;
	font-size: 11px;
	font-weight: 600;
}

/* === Floating Panel === */
.waste-panel {
	position: fixed;
	top: 50%;
	inset-inline-end: 16px;
	transform: translateY(-50%);
	width: 300px;
	max-height: 80vh;
	background: white;
	border: 2px solid #059669;
	border-radius: 16px;
	box-shadow: 0 16px 48px rgba(0, 0, 0, 0.18);
	z-index: 1040;
	display: flex;
	flex-direction: column;
	overflow: hidden;
}
.panel-header {
	background: #059669;
	color: white;
	padding: 16px 20px;
	position: relative;
	flex-shrink: 0;
}
.panel-title {
	font-size: 18px;
	font-weight: 700;
	margin: 0 0 4px 0;
	color: white;
}
.panel-subtitle {
	font-size: 12px;
	color: rgba(255, 255, 255, 0.85);
	margin: 0;
}
.panel-close {
	position: absolute;
	top: 10px;
	inset-inline-end: 12px;
	background: none;
	border: none;
	color: white;
	font-size: 22px;
	cursor: pointer;
	line-height: 1;
	padding: 0 4px;
	opacity: 0.8;
}
.panel-close:hover {
	opacity: 1;
}
.panel-body {
	flex: 1;
	overflow-y: auto;
	padding: 12px;
}
.panel-loading {
	display: flex;
	justify-content: center;
	align-items: center;
	padding: 32px;
}
.spinner {
	width: 32px;
	height: 32px;
	border: 3px solid #e5e7eb;
	border-top-color: #059669;
	border-radius: 50%;
	animation: spin 0.7s linear infinite;
}
@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}
.type-list {
	display: flex;
	flex-direction: column;
	gap: 8px;
}
.type-item {
	padding: 10px 12px;
	border: 2px solid #a7f3d0;
	border-radius: 8px;
	background: white;
	cursor: grab;
	transition: border-color 0.15s, transform 0.15s, box-shadow 0.15s;
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 8px;
}
.type-item:hover:not(.type-item-used) {
	border-color: #059669;
	transform: scale(1.02);
	box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}
.type-item-used {
	opacity: 0.5;
	cursor: not-allowed;
	background: #f9fafb;
	border-color: #e5e7eb;
}
.type-name {
	font-size: 13px;
	font-weight: 600;
	color: #064e3b;
}
.type-used-badge {
	font-size: 11px;
	color: #6b7280;
	white-space: nowrap;
}
.panel-empty {
	text-align: center;
	color: #9ca3af;
	padding: 32px 16px;
}
.panel-empty-icon {
	font-size: 40px;
	margin-bottom: 10px;
}
.panel-empty p {
	font-size: 13px;
}
.panel-footer {
	padding: 12px;
	border-top: 1px solid #e5e7eb;
	flex-shrink: 0;
}
.clear-all-btn {
	width: 100%;
	padding: 8px;
	background: #fef2f2;
	color: #dc2626;
	border: 1px solid #fecaca;
	border-radius: 8px;
	font-size: 13px;
	font-weight: 500;
	cursor: pointer;
	transition: background 0.15s;
}
.clear-all-btn:hover {
	background: #fee2e2;
}

/* Panel slide transition */
.panel-slide-enter-active,
.panel-slide-leave-active {
	transition: transform 0.25s ease, opacity 0.25s ease;
}
.panel-slide-enter-from,
.panel-slide-leave-to {
	transform: translateY(-50%) translateX(40px);
	opacity: 0;
}
.panel-slide-enter-to,
.panel-slide-leave-from {
	transform: translateY(-50%) translateX(0);
	opacity: 1;
}
/* RTL: panel slides from the left side */
[dir=rtl] .panel-slide-enter-from,
[dir=rtl] .panel-slide-leave-to {
	transform: translateY(-50%) translateX(-40px);
}
</style>
