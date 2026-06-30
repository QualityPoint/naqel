<script setup>
import { ref, watch } from 'vue';
import { __ } from './i18n';

const props = defineProps({
	modelValue: { type: String, default: '' },
	label: { type: String, required: true },
	method: { type: String, required: true },
	methodParams: { type: Object, default: () => ({}) },
	displayField: { type: String, default: 'name' },
	valueField: { type: String, default: 'name' },
	placeholder: { type: String, default: '' },
	required: { type: Boolean, default: false },
	disabled: { type: Boolean, default: false },
});

const emit = defineEmits(['update:modelValue']);

const search = ref('');
const options = ref([]);
const open = ref(false);
const loading = ref(false);
let debounceTimer = null;
let reqSeq = 0; // guards against stale responses

// Sync display text when an external value is set (e.g. auto-populated configuration
// / default UOM). If the value isn't among the loaded options yet, fetch the list so
// its label resolves immediately — without the user having to open the field.
watch(
	() => props.modelValue,
	(val) => {
		if (!val) {
			search.value = '';
			return;
		}
		const opt = options.value.find((o) => o[props.valueField] === val);
		if (opt) {
			search.value = opt[props.displayField];
		} else {
			doFetch('', true);
		}
	}
);

// When method params change (e.g. service_configuration resets), clear field
watch(
	() => props.methodParams,
	() => {
		options.value = [];
		search.value = '';
		emit('update:modelValue', '');
	},
	{ deep: true }
);

const doFetch = (query, restoreDisplay = false) => {
	loading.value = true;
	const seq = ++reqSeq;
	frappe.call({
		method: props.method,
		args: { ...props.methodParams, search: query },
		callback: (r) => {
			if (seq !== reqSeq) return; // discard stale response
			loading.value = false;
			const data = r?.message;
			if (data?.success) {
				options.value = data.data || [];
			} else if (Array.isArray(data)) {
				options.value = data;
			} else {
				options.value = [];
			}
			// Only restore display text when NOT in active typing mode
			if (restoreDisplay && props.modelValue) {
				const opt = options.value.find((o) => o[props.valueField] === props.modelValue);
				if (opt) search.value = opt[props.displayField];
			}
		},
		error: () => {
			if (seq !== reqSeq) return;
			loading.value = false;
		},
	});
};

const scheduleSearch = (query) => {
	clearTimeout(debounceTimer);
	debounceTimer = setTimeout(() => doFetch(query), 280);
};

const onInput = (e) => {
	search.value = e.target.value;
	if (!open.value) open.value = true;
	scheduleSearch(search.value);
};

const onFocus = (e) => {
	if (props.disabled) return;
	open.value = true;
	// Keep the current label visible (no blank flicker) and select it so the user can
	// still type to replace it. The dropdown shows the full list regardless of the text.
	e?.target?.select?.();
	doFetch('', true); // full list; restoreDisplay keeps the label in sync after load
};

const onBlur = () => {
	clearTimeout(debounceTimer);
	setTimeout(() => {
		open.value = false;
		if (!props.modelValue) {
			search.value = '';
		} else {
			const opt = options.value.find((o) => o[props.valueField] === props.modelValue);
			search.value = opt ? opt[props.displayField] : props.modelValue;
		}
	}, 200);
};

const select = (opt) => {
	emit('update:modelValue', opt[props.valueField]);
	search.value = opt[props.displayField];
	open.value = false;
};

const clear = () => {
	emit('update:modelValue', '');
	search.value = '';
	doFetch(''); // immediately repopulate with first-page results
};
</script>

<template>
	<div class="lf-root">
		<label class="lf-label">
			<span v-if="required" class="text-danger">*</span>
			{{ label }}
		</label>
		<div class="lf-input-wrap">
			<input
				class="lf-input"
				:class="{ 'lf-disabled': disabled }"
				:disabled="disabled"
				:placeholder="disabled ? __('Select previous fields first') : placeholder || __('Search...')"
				:value="search"
				@input="onInput"
				@focus="onFocus"
				@blur="onBlur"
				autocomplete="off"
			/>
			<button v-if="modelValue && !disabled" class="lf-clear" type="button" @mousedown.prevent="clear">×</button>
			<div v-if="loading" class="lf-spinner"></div>
		</div>
		<div v-if="open && loading && options.length === 0" class="lf-dropdown lf-loading-msg">
			{{ __('Loading...') }}
		</div>
		<div v-else-if="open && options.length > 0" class="lf-dropdown">
			<div
				v-for="opt in options.slice(0, 30)"
				:key="opt[valueField]"
				class="lf-option"
				:class="{ 'lf-option-active': opt[valueField] === modelValue }"
				@mousedown.prevent="select(opt)"
			>
				{{ opt[displayField] }}
			</div>
		</div>
		<div v-else-if="open && !loading && search && options.length === 0" class="lf-dropdown lf-no-results">
			{{ __('No results found') }}
		</div>
	</div>
</template>

<style scoped>
.lf-root {
	position: relative;
}
.lf-label {
	display: block;
	font-size: 12px;
	font-weight: 600;
	color: #374151;
	margin-bottom: 4px;
	text-transform: uppercase;
	letter-spacing: 0.03em;
}
.lf-input-wrap {
	position: relative;
}
.lf-input {
	width: 100%;
	padding-block: 9px;
	padding-inline-start: 12px;
	padding-inline-end: 36px;
	border: 2px solid #d1d5db;
	border-radius: 8px;
	font-size: 14px;
	outline: none;
	box-sizing: border-box;
	transition: border-color 0.15s;
	background: white;
	color: #111827;
}
.lf-input:focus {
	border-color: #059669;
	box-shadow: 0 0 0 3px rgba(5, 150, 105, 0.12);
}
.lf-disabled {
	background: #f3f4f6 !important;
	cursor: not-allowed;
	color: #9ca3af;
}
.lf-clear {
	position: absolute;
	inset-inline-end: 8px;
	top: 50%;
	transform: translateY(-50%);
	background: none;
	border: none;
	font-size: 18px;
	color: #9ca3af;
	cursor: pointer;
	line-height: 1;
	padding: 0 2px;
}
.lf-clear:hover {
	color: #374151;
}
.lf-spinner {
	position: absolute;
	inset-inline-end: 10px;
	top: 50%;
	transform: translateY(-50%);
	width: 14px;
	height: 14px;
	border: 2px solid #e5e7eb;
	border-top-color: #059669;
	border-radius: 50%;
	animation: lf-spin 0.7s linear infinite;
}
@keyframes lf-spin {
	to {
		transform: translateY(-50%) rotate(360deg);
	}
}
.lf-dropdown {
	position: absolute;
	top: calc(100% + 4px);
	left: 0;
	right: 0;
	background: white;
	border: 1px solid #e5e7eb;
	border-radius: 8px;
	box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
	z-index: 1050;
	max-height: 220px;
	overflow-y: auto;
}
.lf-option {
	padding: 8px 12px;
	font-size: 13px;
	cursor: pointer;
	color: #374151;
}
.lf-option:hover {
	background: #f0fdf4;
	color: #065f46;
}
.lf-option-active {
	background: #d1fae5;
	color: #065f46;
	font-weight: 600;
}
.lf-no-results {
	padding: 10px 12px;
	font-size: 13px;
	color: #9ca3af;
	text-align: center;
}
.lf-loading-msg {
	padding: 12px;
	font-size: 13px;
	color: #6b7280;
	text-align: center;
}
</style>
