// Shared palette + formatters for the Service Dashboard.
// Forest-green system borrowed from the Waste Calculator page, with related
// categorical accents (emerald, teal, cyan, lime, amber, red, indigo).

export const PALETTE = {
	primary: '#1a5c3a',      // deep forest green (Waste Calc primary)
	primaryDark: '#064e3b',
	primarySoft: '#e8f3ed',
	emerald: '#059669',
	emeraldLight: '#a7f3d0',
	teal: '#0d9488',
	cyan: '#0891b2',
	lime: '#65a30d',
	amber: '#f59e0b',
	red: '#ef4444',
	indigo: '#6366f1',
	slate: '#64748b',
	ink: '#111827',
	muted: '#6b7280',
	line: '#e5e7eb',
	bgSoft: '#f9fafb',
};

// Ordered categorical ramp for charts (greens first, then accents).
export const CATEGORICAL = [
	'#1a5c3a', '#059669', '#0d9488', '#65a30d', '#0891b2',
	'#16a34a', '#f59e0b', '#6366f1', '#ef4444', '#86efac',
	'#15803d', '#0e7490', '#a16207', '#9333ea', '#64748b',
];

// Stable, meaning-aware colors for known statuses across doctypes.
const STATUS_COLORS = {
	// positive / active
	Active: '#059669', Accepted: '#16a34a', Completed: '#15803d',
	'Fully Paid': '#059669', Cleared: '#16a34a', Converted: '#15803d',
	// in-progress / neutral
	Draft: '#94a3b8', Open: '#0891b2', Unsigned: '#0d9488',
	'Under Process': '#0ea5e9', 'Quotation Request': '#0d9488',
	'Quotation': '#0891b2', 'Partially Paid': '#f59e0b', 'On Hold': '#f59e0b',
	'Require Clarification': '#eab308', Clarified: '#22c55e', Appealed: '#f59e0b',
	Inactive: '#94a3b8', 'Sales Order': '#6366f1',
	// negative
	Rejected: '#ef4444', Cancelled: '#9ca3af', Terminated: '#dc2626',
	Expired: '#a3a3a3', Unpaid: '#ef4444', Lost: '#ef4444',
};

export function statusColor(name, index = 0) {
	return STATUS_COLORS[name] || CATEGORICAL[index % CATEGORICAL.length];
}

export function formatNumber(value) {
	const n = Number(value || 0);
	return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

// Compact currency, e.g. 1.2M / 340.5K — keeps KPI cards tidy.
export function formatCurrency(value, currency = 'SAR') {
	const n = Number(value || 0);
	const abs = Math.abs(n);
	let str;
	if (abs >= 1e9) str = (n / 1e9).toFixed(1) + 'B';
	else if (abs >= 1e6) str = (n / 1e6).toFixed(1) + 'M';
	else if (abs >= 1e3) str = (n / 1e3).toFixed(1) + 'K';
	else str = n.toLocaleString(undefined, { maximumFractionDigits: 0 });
	return `${str} ${currency}`;
}

export function formatFullCurrency(value, currency = 'SAR') {
	const n = Number(value || 0);
	return `${n.toLocaleString(undefined, { maximumFractionDigits: 2 })} ${currency}`;
}
