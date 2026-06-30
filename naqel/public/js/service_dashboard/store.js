// Shared dashboard store (composable, provide/inject). One instance per mounted
// dashboard; provided as `store` so any component can read filters/data and trigger
// a reload. Bridges to the backend via two whitelisted endpoints.

import { reactive, ref } from 'vue';

export function createDashboardStore() {
	const filters = reactive({
		from_date: null,
		to_date: null,
		company: null,
		service_type: null,
		territory: null,
	});

	const data = ref(null);
	const options = ref({ companies: [], service_types: [], territories: [], today: null });
	const loading = ref(false);
	const error = ref(null);

	function loadOptions() {
		return new Promise((resolve) => {
			frappe.call({
				method: 'naqel.api.dashboard.get_dashboard_filter_options',
				callback: (r) => {
					if (r.message) options.value = r.message;
					resolve(r.message);
				},
				error: () => resolve(null),
			});
		});
	}

	function fetch() {
		loading.value = true;
		error.value = null;
		frappe.call({
			method: 'naqel.api.dashboard.get_service_dashboard',
			args: { filters: JSON.stringify(filters) },
			callback: (r) => {
				data.value = r.message || null;
				loading.value = false;
			},
			error: (err) => {
				error.value = (err && err.message) || __('Failed to load the dashboard.');
				loading.value = false;
			},
		});
	}

	function refresh() {
		fetch();
	}

	return { filters, data, options, loading, error, loadOptions, fetch, refresh };
}
