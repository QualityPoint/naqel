<script setup>
import { computed } from 'vue';
import { __ } from './i18n';

const props = defineProps({
	result: { type: Object, required: true },
	wasteDistributions: { type: Array, default: () => [] },
	droppedItems: { type: Object, default: () => ({}) },
});

// Suggested containers from the backend (one row per waste type when the
// configuration allocates per type, otherwise a single row).
const generatedWastes = computed(() => props.result?.generated_wastes || []);

// Map waste_type -> its suggested container row (only rows tied to a waste type).
const containersByType = computed(() => {
	const map = {};
	generatedWastes.value.forEach((row) => {
		if (row.waste_type) map[row.waste_type] = row;
	});
	return map;
});

// Allocated = a distinct container was suggested per waste type.
const isAllocated = computed(() => generatedWastes.value.length > 1);

// Parse configuration remarks string from backend
const configParams = computed(() => {
	const remarks = props.result?.configuration_remarks || '';
	const parsed = {};
	remarks.split('\n').forEach((rawLine) => {
		const line = rawLine.trim().replace(/<\/?strong>/g, '');
		if (!line) return;
		if (line.includes('Service Configuration:'))
			parsed.serviceConfiguration = line.split(/:(.+)/)[1]?.trim() || '';
		else if (line.includes('Configuration Level:'))
			parsed.configurationLevel = line.split(/:(.+)/)[1]?.trim() || '';
		else if (line.includes('Found at:'))
			parsed.foundAt = line.split(/:(.+)/)[1]?.trim() || '';
		else if (line.includes('Search Path:'))
			parsed.searchPath = line.split(/:(.+)/)[1]?.trim() || '';
		else if (line.includes('Calculation Method:'))
			parsed.calculationMethod = line.split(/:(.+)/)[1]?.trim() || '';
		else if (line.includes('Generation Rate Method:'))
			parsed.generationRateMethod = line.split(/:(.+)/)[1]?.trim() || '';
		else if (line.includes('Facility UOM:'))
			parsed.facilityUOM = line.split(/:(.+)/)[1]?.trim() || '';
		else if (line.includes('Note:'))
			parsed.note = line.split('Note:')[1]?.trim() || '';
		else if (line.includes('All calculations') || line.includes('جميع الحسابات'))
			parsed.dailyBasis = line;
	});
	return parsed;
});

// Print backend-generated HTML report on A4
const handlePrint = () => {
	if (!props.result?.waste_calculation) return;
	const w = window.open('', '_blank');
	if (!w) return;
	const dir = document.documentElement.getAttribute('dir') || 'ltr';
	const lang = document.documentElement.getAttribute('lang') || 'en';
	const isRTL = dir === 'rtl';
	const printDate = new Date().toLocaleDateString(lang, { year: 'numeric', month: 'long', day: 'numeric' });

	const _fmt = (v) => (typeof v === 'number' ? v.toFixed(2) : v ?? '--');
	const _fmt4 = (v) => (typeof v === 'number' ? v.toFixed(4) : v ?? '--');
	const r = props.result;

	// ── Build Vue-sourced preamble sections ─────────────────────────────────

	// Time estimates
	const timeHtml = (r.apply_service_duration && r.time_estimates) ? `<div class="rpt-section" style="page-break-inside:avoid">
  <h3 class="rpt-section-title">${__('Time-based Waste Generation Estimates')}</h3>
  <table class="rpt-table">
    <thead><tr>
      <th>${__('Time Period')}</th>
      <th style="text-align:center">${__('Calculation Factor')}</th>
      <th>${__('Estimated Volume')}</th>
    </tr></thead>
    <tbody>
      <tr><td>${__('Daily Generation')}</td><td style="text-align:center;color:#6b7280">${__('Base Calculation')}</td><td class="rpt-vol">${_fmt(r.time_estimates.daily)} ${r.waste_unit ?? ''}</td></tr>
      <tr class="rpt-row-alt"><td>${__('Weekly Generation')}</td><td style="text-align:center;color:#6b7280">${__('Daily × 7')}</td><td class="rpt-vol">${_fmt(r.time_estimates.weekly)} ${r.waste_unit ?? ''}</td></tr>
      <tr><td>${__('Monthly Generation')}</td><td style="text-align:center;color:#6b7280">${__('Daily × 30')}</td><td class="rpt-vol">${_fmt(r.time_estimates.monthly)} ${r.waste_unit ?? ''}</td></tr>
      <tr class="rpt-row-alt"><td>${__('Yearly Generation')}</td><td style="text-align:center;color:#6b7280">${__('Daily × 365')}</td><td class="rpt-vol">${_fmt(r.time_estimates.yearly)} ${r.waste_unit ?? ''}</td></tr>
    </tbody>
  </table>
</div>` : '';

	// Suggested container with per-distribution waste chips
	const droppedHtml = props.wasteDistributions.map((dist) => {
		const items = props.droppedItems[dist.waste_type] || [];
		if (!items.length) return '';
		const chips = items.map((w) => `<span class="rpt-chip">${__(w.waste_name || w.name)}</span>`).join('');
		return `<div class="rpt-dist-item">
  <div class="rpt-dist-header">
    <div>
      <p class="rpt-dist-name">${__(dist.waste_name || dist.waste_type)}</p>
      <p class="rpt-dist-id">${dist.waste_type}</p>
    </div>
    <span class="rpt-dist-pct">${dist.distribution_percentage}%</span>
  </div>
  <div class="rpt-chips-row">${chips}</div>
</div>`;
	}).filter(Boolean).join('');

	const containerHtml = r.suggested_container ? `<div class="rpt-section" style="page-break-inside:avoid">
  <h3 class="rpt-section-title">${__('Suggested Container')}</h3>
  <div class="rpt-container-box">
    <div class="rpt-count-badge">
      <p class="rpt-count-num">${r.suggested_container_count ?? '--'}</p>
      <p class="rpt-count-label">${__('Count')}</p>
    </div>
    <div>
      <p class="rpt-container-label">${__('Container Type')}</p>
      <p class="rpt-container-value">${__(r.suggested_container)}</p>
    </div>
  </div>
  ${droppedHtml}
</div>` : '';

	// Calculation parameters
	const cp = configParams.value;
	const paramCards = [
		cp.serviceConfiguration ? `<div class="rpt-param-card"><p class="rpt-param-key">${__('Service Configuration')}</p><p class="rpt-param-val">${__(cp.serviceConfiguration)}</p></div>` : '',
		cp.configurationLevel ? `<div class="rpt-param-card"><p class="rpt-param-key">${__('Configuration Level')}</p><p class="rpt-param-val">${__(cp.configurationLevel)}</p></div>` : '',
		cp.calculationMethod ? `<div class="rpt-param-card"><p class="rpt-param-key">${__('Calculation Method')}</p><p class="rpt-param-val">${__(cp.calculationMethod)}</p></div>` : '',
		cp.generationRateMethod ? `<div class="rpt-param-card"><p class="rpt-param-key">${__('Generation Rate Method')}</p><p class="rpt-param-val">${__(cp.generationRateMethod)}</p></div>` : '',
		cp.facilityUOM ? `<div class="rpt-param-card"><p class="rpt-param-key">${__('Facility UOM')}</p><p class="rpt-param-val">${__(cp.facilityUOM)}</p></div>` : '',
	].filter(Boolean).join('');
	const foundAtNote = cp.foundAt ? `<div class="rpt-sub-note rpt-note-amber"><p class="rpt-param-key">${__('Found At')}</p><p class="rpt-param-val">${__(cp.foundAt)}</p></div>` : '';
	const searchPathNote = cp.searchPath ? `<div class="rpt-sub-note rpt-note-gray"><p class="rpt-param-key">${__('Search Path')}</p><p class="rpt-param-val" style="font-family:monospace;font-size:7.5pt">${cp.searchPath}</p></div>` : '';
	const paramsHtml = (paramCards || cp.foundAt || cp.searchPath) ? `<div class="rpt-section" style="page-break-inside:avoid">
  <h3 class="rpt-section-title">${__('Calculation Parameters')}</h3>
  ${paramCards ? `<div class="rpt-param-grid">${paramCards}</div>` : ''}
  ${foundAtNote}
  ${searchPathNote}
</div>` : '';

	w.document.write(`<!DOCTYPE html>
<html lang="${lang}" dir="${dir}">
<head>
<meta charset="UTF-8">
<title>${__('Waste Generation Assessment Report')}</title>
<style>
  /* ── Page setup ─────────────────────────────────────────── */
  @page {
    size: A4 portrait;
    margin: 18mm 15mm 20mm;
    @bottom-center {
      content: counter(page) " / " counter(pages);
      font-size: 7.5pt;
      color: #9ca3af;
    }
  }
  *, *::before, *::after { box-sizing: border-box; }
  html { direction: ${dir}; }
  body {
    font-family: 'Almarai', 'Segoe UI', Arial, sans-serif;
    font-size: 9.5pt;
    line-height: 1.5;
    color: #1a1a1a;
    background: #fff;
    margin: 0;
    padding: 0;
    direction: ${dir};
    text-align: ${isRTL ? 'right' : 'left'};
  }

  /* ── Document header (injected by JS, sits above backend HTML) */
  .rpt-doc-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    border-bottom: 2px solid #1a5c3a;
    padding-bottom: 8pt;
    margin-bottom: 14pt;
    page-break-inside: avoid;
  }
  .rpt-doc-title { font-size: 13pt; font-weight: 800; color: #1a1a1a; margin: 0 0 2pt; }
  .rpt-doc-sub   { font-size: 8.5pt; color: #6b7280; margin: 0; }
  .rpt-doc-meta  { font-size: 8pt; color: #6b7280; text-align: ${isRTL ? 'left' : 'right'}; white-space: nowrap; }

  /* ── Vue-sourced preamble sections ── */
  .rpt-preamble { display: flex; flex-direction: column; gap: 14pt; margin-bottom: 18pt; }

  .rpt-summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8pt; }
  .rpt-card { background: #fff; border: 1px solid #d1d5db; border-inline-start: 3px solid #1a5c3a; border-radius: 5pt; padding: 9pt 11pt; }
  .rpt-card-label { font-size: 7.5pt; font-weight: 500; color: #6b7280; text-transform: uppercase; letter-spacing: 0.04em; margin: 0 0 3pt; }
  .rpt-card-value { font-size: 16pt; font-weight: 700; color: #111827; margin: 0; }

  .rpt-total-box { background: #f9fafb; border: 2px solid #1a5c3a; border-radius: 8pt; padding: 16pt 20pt; text-align: center; page-break-inside: avoid; }
  .rpt-total-label { font-size: 9pt; font-weight: 600; color: #374151; text-transform: uppercase; letter-spacing: 0.05em; margin: 0 0 8pt; }
  .rpt-total-value { font-size: 30pt; font-weight: 800; color: #111827; margin: 0; line-height: 1; }
  .rpt-total-unit  { font-size: 14pt; font-weight: 500; color: #6b7280; margin-inline-start: 5pt; }

  .rpt-section { background: #fff; border: 1px solid #d1d5db; border-radius: 7pt; padding: 12pt 14pt; }
  .rpt-section-title { font-size: 10pt; font-weight: 700; color: #1a5c3a; margin: 0 0 9pt; padding-bottom: 5pt; border-bottom: 1px solid #e5e7eb; }

  .rpt-table { width: 100%; border-collapse: collapse; font-size: 8.5pt; }
  .rpt-table th { background: #1a5c3a; color: #fff; padding: 6pt 9pt; font-weight: 600; text-align: start; }
  .rpt-table td { padding: 5pt 9pt; border-bottom: 1px solid #e5e7eb; }
  .rpt-table tr:last-child td { border-bottom: none; }
  .rpt-row-alt td { background: #f9fafb; }
  .rpt-vol { font-weight: 700; color: #1a5c3a; }

  .rpt-container-box { display: flex; align-items: center; gap: 14pt; margin-bottom: 10pt; }
  .rpt-count-badge { background: #1a5c3a; color: #fff; border-radius: 7pt; padding: 8pt 12pt; text-align: center; min-width: 55pt; }
  .rpt-count-num { font-size: 22pt; font-weight: 800; margin: 0; line-height: 1; }
  .rpt-count-label { font-size: 7pt; text-transform: uppercase; letter-spacing: 0.04em; margin: 2pt 0 0; opacity: 0.85; }
  .rpt-container-label { font-size: 7.5pt; color: #6b7280; font-weight: 500; text-transform: uppercase; margin: 0 0 3pt; }
  .rpt-container-value { font-size: 13pt; font-weight: 700; color: #1a5c3a; margin: 0; }

  .rpt-dist-item { margin-top: 7pt; border: 1px solid #e5e7eb; border-radius: 5pt; padding: 7pt 10pt; }
  .rpt-dist-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 5pt; }
  .rpt-dist-name { font-size: 9.5pt; font-weight: 600; color: #111827; margin: 0; }
  .rpt-dist-id { font-size: 7.5pt; color: #6b7280; margin: 2pt 0 0; }
  .rpt-dist-pct { font-size: 9.5pt; font-weight: 700; color: #1a5c3a; white-space: nowrap; }
  .rpt-chips-row { display: flex; flex-wrap: wrap; gap: 4pt; }
  .rpt-chip { display: inline-flex; align-items: center; background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 20pt; padding: 2pt 7pt; font-size: 7.5pt; font-weight: 500; color: #065f46; }

  .rpt-param-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 7pt; margin-bottom: 8pt; }
  .rpt-param-card { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 5pt; padding: 7pt 9pt; }
  .rpt-param-key { font-size: 7pt; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.04em; margin: 0 0 3pt; }
  .rpt-param-val { font-size: 9pt; font-weight: 600; color: #111827; margin: 0; }
  .rpt-sub-note { padding: 7pt 10pt; border-radius: 5pt; margin-top: 7pt; }
  .rpt-note-amber { background: #fffbeb; border-inline-start: 3px solid #d97706; }
  .rpt-note-gray  { background: #f9fafb; border-inline-start: 3px solid #9ca3af; }

  /* ── Override / reinforce waste_report.css for print ────── */
  /* Remove the old report-header (green block) — shown in screen only */
  .report-header {
    background: none !important;
    color: #1a1a1a !important;
    padding: 0 !important;
    margin-bottom: 10pt !important;
    box-shadow: none !important;
    border: none !important;
    border-bottom: 1px solid #d1d5db !important;
    padding-bottom: 6pt !important;
    text-align: ${isRTL ? 'right' : 'left'} !important;
  }
  .report-header h2 { font-size: 12pt !important; color: #1a1a1a !important; }
  .report-header p  { color: #6b7280 !important; font-size: 8.5pt !important; }

  /* Ensure container fills page width */
  .waste-report-container {
    max-width: 100% !important;
    padding: 0 !important;
    font-size: 9.5pt !important;
  }

  /* Section headings */
  .section-title {
    font-size: 10pt !important;
    color: #1a1a1a !important;
    border-bottom: 1px solid #d1d5db !important;
  }

  /* All section cards: white + neutral border */
  .config-summary-section,
  .calculation-section,
  .time-projections-section,
  .waste-distribution-container,
  .selected-waste-container {
    background: #f9fafb !important;
    border: 1px solid #e5e7eb !important;
    border-inline-end: 3px solid #1a5c3a !important;
    box-shadow: none !important;
  }

  /* Table headers: single dark green */
  .config-table td:first-child { background: #f9fafb !important; color: #374151 !important; }
  .waste-distribution-table thead tr,
  .selected-waste-table thead tr,
  .projections-table thead tr { background: #1a5c3a !important; }
  .waste-distribution-table thead th,
  .selected-waste-table thead th,
  .projections-table th { border-color: #1a5c3a !important; }

  /* Table rows: alternating neutral */
  .row-even, .row-even-alt     { background: #f9fafb !important; }
  .row-odd,  .row-odd-alt      { background: #ffffff !important; }
  .waste-distribution-table td,
  .selected-waste-table td     { border-color: #e5e7eb !important; }
  .projections-table td        { border-color: #e5e7eb !important; }

  /* Remove per-row projection colors */
  .projection-daily, .projection-weekly,
  .projection-monthly, .projection-yearly { background: inherit !important; }
  .projection-daily td,   .projection-weekly td,
  .projection-monthly td, .projection-yearly td { color: #1a1a1a !important; }
  .projection-daily .volume, .projection-weekly .volume,
  .projection-monthly .volume, .projection-yearly .volume { color: #1a5c3a !important; }

  /* Calculation boxes */
  .base-calculation-box {
    background: #ffffff !important;
    border: 1px solid #e5e7eb !important;
    border-inline-end: 2px solid #1a5c3a !important;
  }
  .base-calculation-box h4  { color: #1a1a1a !important; }
  .calculation-label        { color: #374151 !important; }
  .calculation-code         { background: #f3f4f6 !important; color: #1a1a1a !important; border-color: #d1d5db !important; }
  .calculation-result       { background: #f9fafb !important; border: 1px solid #e5e7eb !important; }
  .result-value             { color: #1a5c3a !important; }

  /* Safety factors */
  .safety-factors-box       { background: #ffffff !important; border: 1px solid #e5e7eb !important; border-inline-end: 2px solid #9ca3af !important; }
  .safety-factors-box h4    { color: #374151 !important; }
  .safety-factor-item       { background: #f9fafb !important; border-color: #e5e7eb !important; }
  .safety-indicator         { background: #9ca3af !important; }
  .safety-factor-label      { color: #374151 !important; }
  .adjusted-calculation     { background: #f9fafb !important; border-color: #e5e7eb !important; }
  .adjusted-calculation h5  { color: #374151 !important; }
  .adjusted-calculation .calculation-code   { background: #f3f4f6 !important; color: #1a1a1a !important; }
  .adjusted-calculation .calculation-result { background: #f3f4f6 !important; }
  .adjusted-calculation .result-value       { color: #1a5c3a !important; }

  /* Total waste box */
  .total-waste-box       { background: #f9fafb !important; border: 2px solid #1a5c3a !important; }
  .total-waste-box h4    { color: #374151 !important; }
  .total-waste-value     { font-size: 18pt !important; color: #1a1a1a !important; }
  .total-waste-unit      { color: #6b7280 !important; }

  /* Method badge */
  .method-badge { background: #f3f4f6 !important; color: #374151 !important; border: 1px solid #d1d5db !important; }

  /* Badge */
  .badge-specific { background: #1a5c3a !important; }
  .badge-group    { background: #6b7280 !important; }
  .distribution-value { color: #1a5c3a !important; }
  .volume-value       { color: #1a5c3a !important; }
  .weight-value       { color: #1a1a1a !important; }

  /* Projections note */
  .projections-note { background: #f9fafb !important; border-color: #e5e7eb !important; border-inline-end: 2px solid #9ca3af !important; }
  .projections-note p { color: #4b5563 !important; }

  /* Units footer */
  .units-footer     { background: #f9fafb !important; border-color: #e5e7eb !important; border-top: 1px solid #d1d5db !important; }
  .unit-type,
  .unit-type.volume,
  .unit-type.mass,
  .unit-type.density,
  .units-label      { color: #374151 !important; }

  /* Print-specific page-break helpers */
  .config-summary-section,
  .waste-distribution-container,
  .selected-waste-container,
  .calculation-section,
  .time-projections-section { page-break-inside: avoid; }

  /* Ensure alternating table rows print */
  * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
</style>
</head>
<body>
  <div class="rpt-doc-header">
    <div>
      <p class="rpt-doc-title">${__('Waste Generation Assessment Report')}</p>
      <p class="rpt-doc-sub">${__('Generated by the Waste Generation Calculator')}</p>
    </div>
    <div class="rpt-doc-meta">${printDate}</div>
  </div>
  <div class="rpt-preamble">
    <div class="rpt-summary-grid">
      <div class="rpt-card"><p class="rpt-card-label">${__('Unit Waste Generation Rate')}</p><p class="rpt-card-value">${_fmt4(r.facility_unit_generation_rate)}</p></div>
      <div class="rpt-card"><p class="rpt-card-label">${__('Regional Safety Factor')}</p><p class="rpt-card-value">${r.regional_safety_factor || 1}</p></div>
      <div class="rpt-card"><p class="rpt-card-label">${__('Facility Rating Safety Factor')}</p><p class="rpt-card-value">${r.rating_safety_factor || 1}</p></div>
      <div class="rpt-card"><p class="rpt-card-label">${__('Facility Generated Waste')}</p><p class="rpt-card-value">${_fmt(r.facility_generated_waste)} ${r.waste_unit ?? ''}</p></div>
    </div>
    <div class="rpt-total-box">
      <p class="rpt-total-label">${__('Total Generated Waste')}</p>
      <p class="rpt-total-value">${_fmt(r.total_generated_waste)}<span class="rpt-total-unit">${r.waste_unit ?? ''}</span></p>
    </div>
    ${timeHtml}
    ${containerHtml}
    ${paramsHtml}
  </div>
  ${props.result.waste_calculation}
  <script>window.onload = function () { window.print(); };<\/script>
</body>
</html>`);
	w.document.close();
};

const fmt = (v) => (typeof v === 'number' ? v.toFixed(2) : v ?? '--');
const fmt4 = (v) => (typeof v === 'number' ? v.toFixed(4) : v ?? '--');
</script>

<template>
	<div class="cr-root">
		<!-- Print button -->
		<div class="print-row">
			<button class="print-btn" @click="handlePrint">
				<svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
						d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
				</svg>
				{{ __('Print Report') }}
			</button>
		</div>

		<!-- Summary cards (4-up) -->
		<div class="summary-grid">
			<div class="card card-emerald">
				<p class="card-label">{{ __('Unit Waste Generation Rate') }}</p>
				<p class="card-value">{{ fmt4(result.facility_unit_generation_rate) }}</p>
			</div>
			<div class="card card-teal">
				<p class="card-label">{{ __('Regional Safety Factor') }}</p>
				<p class="card-value teal">{{ result.regional_safety_factor || 1 }}</p>
			</div>
			<div class="card card-emerald">
				<p class="card-label">{{ __('Facility Rating Safety Factor') }}</p>
				<p class="card-value">{{ result.rating_safety_factor || 1 }}</p>
			</div>
			<div class="card card-green">
				<p class="card-label">{{ __('Facility Generated Waste') }}</p>
				<p class="card-value green">{{ fmt(result.facility_generated_waste) }} {{ __(result.waste_unit) }}</p>
			</div>
		</div>

		<!-- Featured total -->
		<div class="total-box">
			<p class="total-label">{{ __('Total Generated Waste') }}</p>
			<p class="total-value">
				{{ fmt(result.total_generated_waste) }}
				<span class="total-unit">{{ __(result.waste_unit) }}</span>
			</p>
		</div>

		<!-- Time estimates (only when apply_service_duration) -->
		<div v-if="result.apply_service_duration && result.time_estimates" class="section-card">
			<h3 class="section-title">{{ __('Time-based Waste Generation Estimates') }}</h3>
			<p class="section-desc">
				{{ __('The following estimates represent expected waste generation volumes across different time periods, calculated on a daily basis') }}
			</p>
			<div class="table-wrap">
				<table class="data-table">
					<thead>
						<tr>
							<th>{{ __('Time Period') }}</th>
							<th class="text-center">{{ __('Calculation Factor') }}</th>
							<th>{{ __('Estimated Volume') }}</th>
						</tr>
					</thead>
					<tbody>
						<tr class="row-green">
							<td>{{ __('Daily Generation') }}</td>
							<td class="text-center text-muted">{{ __('Base Calculation') }}</td>
							<td class="font-bold text-green">{{ fmt(result.time_estimates.daily) }} {{ __(result.waste_unit) }}</td>
						</tr>
						<tr class="row-teal">
							<td>{{ __('Weekly Generation') }}</td>
							<td class="text-center text-muted">{{ __('Daily × 7') }}</td>
							<td class="font-bold text-teal">{{ fmt(result.time_estimates.weekly) }} {{ __(result.waste_unit) }}</td>
						</tr>
						<tr class="row-emerald">
							<td>{{ __('Monthly Generation') }}</td>
							<td class="text-center text-muted">{{ __('Daily × 30') }}</td>
							<td class="font-bold text-emerald">{{ fmt(result.time_estimates.monthly) }} {{ __(result.waste_unit) }}</td>
						</tr>
						<tr class="row-lime">
							<td>{{ __('Yearly Generation') }}</td>
							<td class="text-center text-muted">{{ __('Daily × 365') }}</td>
							<td class="font-bold text-lime">{{ fmt(result.time_estimates.yearly) }} {{ __(result.waste_unit) }}</td>
						</tr>
					</tbody>
				</table>
			</div>
			<div class="note-amber">
				<strong>{{ __('Note') }}:</strong>
				{{ __('All estimates are calculated based on daily waste generation rate. Actual volumes may vary depending on operational patterns, seasonal factors, and facility-specific conditions.') }}
			</div>
		</div>

		<!-- Suggested container -->
		<div v-if="result.suggested_container || isAllocated" class="section-card container-card">
			<h3 class="section-title">{{ __('Suggested Container') }}</h3>

			<!-- Single container (only when not allocating per waste type) -->
			<div v-if="!isAllocated" class="container-box">
				<div class="container-count-badge">
					<p class="count-number">{{ result.suggested_container_count }}</p>
					<p class="count-label">{{ __('Count') }}</p>
				</div>
				<div class="container-type-text">
					<p class="container-type-label">{{ __('Container Type') }}</p>
					<p class="container-type-value">{{ __(result.suggested_container) }}</p>
				</div>
			</div>

			<!-- Per-distribution: when allocating, each category carries its own container -->
			<div v-if="wasteDistributions.length > 0" class="dist-list">
				<template v-for="dist in wasteDistributions" :key="dist.waste_type">
					<div
						v-if="isAllocated || (droppedItems[dist.waste_type] || []).length > 0"
						class="dist-item"
					>
						<div class="dist-header">
							<div>
								<p class="dist-name">{{ __(dist.waste_name) }}</p>
								<p class="dist-id">{{ __(dist.waste_type) }}</p>
							</div>
							<span class="dist-pct">{{ dist.distribution_percentage }}%</span>
						</div>

						<!-- This category's suggested container -->
						<div v-if="isAllocated && containersByType[dist.waste_type]" class="container-box container-box-sm">
							<div class="container-count-badge">
								<p class="count-number">{{ containersByType[dist.waste_type].container_count }}</p>
								<p class="count-label">{{ __('Count') }}</p>
							</div>
							<div class="container-type-text">
								<p class="container-type-label">{{ __('Container Type') }}</p>
								<p class="container-type-value">{{ __(containersByType[dist.waste_type].container_type) }}</p>
							</div>
						</div>

						<div v-if="(droppedItems[dist.waste_type] || []).length > 0" class="chips-row">
							<span v-for="w in droppedItems[dist.waste_type]" :key="w.name" class="chip">
								<svg width="12" height="12" fill="currentColor" viewBox="0 0 20 20">
									<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
								</svg>
								{{ __(w.waste_name) }}
							</span>
						</div>
					</div>
				</template>
			</div>
		</div>

		<!-- Configuration parameters -->
		<div v-if="result.configuration_remarks" class="section-card teal-card">
			<h3 class="section-title teal-title">
				<svg width="24" height="24" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
						d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
				</svg>
				{{ __('Calculation Parameters') }}
			</h3>
			<div class="config-grid">
				<div v-if="configParams.serviceConfiguration" class="config-card">
					<p class="config-key">{{ __('Service Configuration') }}</p>
					<p class="config-val">{{ __(configParams.serviceConfiguration) }}</p>
				</div>
				<div v-if="configParams.configurationLevel" class="config-card">
					<p class="config-key">{{ __('Configuration Level') }}</p>
					<p class="config-val">{{ __(configParams.configurationLevel) }}</p>
				</div>
				<div v-if="configParams.calculationMethod" class="config-card">
					<p class="config-key">{{ __('Calculation Method') }}</p>
					<p class="config-val">{{ __(configParams.calculationMethod) }}</p>
				</div>
				<div v-if="configParams.generationRateMethod" class="config-card">
					<p class="config-key">{{ __('Generation Rate Method') }}</p>
					<p class="config-val">{{ __(configParams.generationRateMethod) }}</p>
				</div>
				<div v-if="configParams.facilityUOM" class="config-card">
					<p class="config-key">{{ __('Facility UOM') }}</p>
					<p class="config-val">{{ __(configParams.facilityUOM) }}</p>
				</div>
			</div>
			<div v-if="configParams.foundAt" class="sub-note amber-note">
				<p class="sub-key">{{ __('Found At') }}</p>
				<p class="sub-val">{{ __(configParams.foundAt) }}</p>
			</div>
			<div v-if="configParams.searchPath" class="sub-note gray-note">
				<p class="sub-key">{{ __('Search Path') }}</p>
				<p class="sub-val mono">{{ configParams.searchPath }}</p>
			</div>
			<div v-if="configParams.note" class="sub-note cyan-note">
				<p class="sub-val">{{ configParams.note }}</p>
			</div>
			<div v-if="configParams.dailyBasis" class="daily-basis-note">
				<p>{{ __(configParams.dailyBasis) }}</p>
			</div>
		</div>

		<!-- Detailed calculation report (backend-rendered HTML) -->
		<div v-if="result.waste_calculation" class="section-card detail-card">
			<div class="detail-header">
				<h3 class="section-title">{{ __('Detailed Calculation Report') }}</h3>
				<svg width="24" height="24" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
						d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
				</svg>
			</div>
			<!-- eslint-disable-next-line vue/no-v-html -->
			<div class="detail-body" v-html="result.waste_calculation"></div>
		</div>
	</div>
</template>

<style scoped>
/* ── Accent palette (one green, everything else neutral) ──────────── */
/* --accent: #1a5c3a  --accent-light: #e8f3ed  --border: #d1d5db  --bg: #f9fafb */

.cr-root {
	display: flex;
	flex-direction: column;
	gap: 20px;
}

/* Print button */
.print-row { display: flex; justify-content: flex-start; }
.print-btn {
	display: flex;
	align-items: center;
	gap: 8px;
	padding: 9px 18px;
	background: #1a5c3a;
	color: #fff;
	border: none;
	border-radius: 6px;
	font-size: 13px;
	font-weight: 600;
	cursor: pointer;
	transition: background 0.15s;
	letter-spacing: 0.01em;
}
.print-btn:hover { background: #124228; }

/* Summary cards */
.summary-grid {
	display: grid;
	grid-template-columns: repeat(4, 1fr);
	gap: 12px;
}
@media (max-width: 900px) { .summary-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 560px) { .summary-grid { grid-template-columns: 1fr; } }

.card {
	background: #fff;
	border: 1px solid #d1d5db;
	border-inline-start: 3px solid #1a5c3a;
	border-radius: 8px;
	padding: 14px 16px;
}
.card-emerald,
.card-teal,
.card-green { /* all same neutral treatment */ }
.card-label { font-size: 11px; font-weight: 500; color: #6b7280; text-transform: uppercase; letter-spacing: 0.04em; margin: 0 0 6px; }
.card-value { font-size: 24px; font-weight: 700; color: #111827; margin: 0; }
.card-value.teal,
.card-value.green { color: #1a5c3a; }

/* Featured total */
.total-box {
	background: #f9fafb;
	border: 2px solid #1a5c3a;
	border-radius: 10px;
	padding: 28px 24px;
	text-align: center;
}
.total-label { font-size: 14px; font-weight: 600; color: #374151; text-transform: uppercase; letter-spacing: 0.05em; margin: 0 0 10px; }
.total-value { font-size: 48px; font-weight: 800; color: #111827; margin: 0; line-height: 1; }
.total-unit  { font-size: 20px; font-weight: 500; color: #6b7280; margin-inline-start: 6px; }

/* Section card */
.section-card {
	background: #fff;
	border: 1px solid #d1d5db;
	border-radius: 10px;
	padding: 20px 24px;
}
.section-title {
	font-size: 16px;
	font-weight: 700;
	color: #111827;
	margin: 0 0 14px;
	display: flex;
	align-items: center;
	gap: 8px;
}
.section-desc { font-size: 12px; color: #6b7280; margin: 0 0 14px; }

/* Time estimates table */
.table-wrap { overflow-x: auto; border-radius: 6px; border: 1px solid #d1d5db; }
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table th {
	background: #1a5c3a;
	color: #fff;
	padding: 9px 12px;
	font-weight: 600;
	text-align: start;
	font-size: 12px;
}
.data-table td { padding: 9px 12px; border-bottom: 1px solid #f3f4f6; color: #374151; }
.data-table tbody tr:nth-child(even) td { background: #f9fafb; }
.text-center { text-align: center; }
.text-muted { color: #9ca3af; }
.font-bold   { font-weight: 700; }
/* Unify row & text colors to single accent */
.text-green,
.text-teal,
.text-emerald,
.text-lime    { color: #1a5c3a; font-weight: 700; }
.row-green,
.row-teal,
.row-emerald,
.row-lime     { background: transparent; }
.note-amber {
	margin-top: 14px;
	background: #f9fafb;
	border-inline-start: 3px solid #9ca3af;
	padding: 9px 12px;
	border-radius: 4px;
	font-size: 12px;
	color: #4b5563;
	line-height: 1.5;
}

/* Container section */
.container-card { border-color: #d1d5db; }
.container-box {
	display: flex;
	align-items: center;
	gap: 20px;
	background: #f9fafb;
	border: 1px solid #d1d5db;
	border-radius: 8px;
	padding: 14px 16px;
}
.container-count-badge {
	background: #1a5c3a;
	border-radius: 6px;
	padding: 10px 18px;
	text-align: center;
	min-width: 68px;
}
.count-number { font-size: 30px; font-weight: 800; color: #fff; margin: 0; }
.count-label  { font-size: 10px; font-weight: 600; color: #a7f3d0; margin: 3px 0 0; text-transform: uppercase; }
.container-type-text { flex: 1; }
.container-type-label { font-size: 11px; font-weight: 500; color: #6b7280; text-transform: uppercase; letter-spacing: 0.04em; margin: 0 0 4px; }
.container-type-value { font-size: 20px; font-weight: 700; color: #111827; margin: 0; }

/* Compact per-category container inside a distribution card */
.container-box-sm { background: #fff; gap: 14px; padding: 10px 12px; margin-bottom: 8px; }
.container-box-sm .container-count-badge { padding: 6px 12px; min-width: 52px; }
.container-box-sm .count-number { font-size: 22px; }
.container-box-sm .container-type-value { font-size: 16px; }

.dist-list { margin-top: 16px; display: flex; flex-direction: column; gap: 10px; }
.dist-item {
	background: #f9fafb;
	border: 1px solid #d1d5db;
	border-inline-start: 3px solid #1a5c3a;
	border-radius: 8px;
	padding: 12px 14px;
}
.dist-header {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	margin-bottom: 8px;
}
.dist-name { font-size: 13px; font-weight: 700; color: #111827; margin: 0; }
.dist-id   { font-size: 11px; color: #6b7280; margin: 2px 0 0; }
.dist-pct  {
	background: #374151;
	color: #fff;
	font-size: 11px;
	font-weight: 700;
	border-radius: 4px;
	padding: 2px 8px;
	flex-shrink: 0;
	margin-inline-start: 8px;
}
.chips-row { display: flex; flex-wrap: wrap; gap: 5px; }
.chip {
	display: inline-flex;
	align-items: center;
	gap: 4px;
	background: #fff;
	border: 1px solid #d1d5db;
	border-radius: 4px;
	padding: 3px 9px;
	font-size: 11px;
	font-weight: 500;
	color: #374151;
}

/* Config card */
.teal-card  { background: #f9fafb; border-color: #d1d5db; }
.teal-title { color: #111827; }
.config-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
@media (max-width: 640px) { .config-grid { grid-template-columns: 1fr; } }
.config-card {
	background: #fff;
	border: 1px solid #d1d5db;
	border-radius: 6px;
	padding: 9px 12px;
}
.config-key { font-size: 10px; font-weight: 500; color: #6b7280; text-transform: uppercase; letter-spacing: 0.04em; margin: 0 0 3px; }
.config-val { font-size: 13px; font-weight: 700; color: #111827; margin: 0; }

.sub-note { margin-top: 8px; border-radius: 6px; padding: 9px 12px; }
.amber-note,
.gray-note,
.cyan-note  { background: #f9fafb; border: 1px solid #d1d5db; border-inline-start: 3px solid #9ca3af; }
.sub-key { font-size: 10px; font-weight: 500; color: #6b7280; text-transform: uppercase; letter-spacing: 0.04em; margin: 0 0 3px; }
.sub-val { font-size: 12px; color: #374151; font-weight: 500; margin: 0; }
.mono { font-family: 'Courier New', monospace; word-break: break-all; font-size: 11px; }
.daily-basis-note {
	margin-top: 8px;
	background: #f9fafb;
	border: 1px solid #d1d5db;
	border-inline-start: 3px solid #1a5c3a;
	border-radius: 6px;
	padding: 9px 12px;
	font-size: 12px;
	font-weight: 600;
	color: #374151;
}

/* Detailed report */
.detail-card { border-color: #d1d5db; }
.detail-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding-bottom: 12px;
	border-bottom: 1px solid #e5e7eb;
	margin-bottom: 14px;
}
.detail-header .section-title { margin-bottom: 0; }
.detail-body {
	font-size: 13px;
	line-height: 1.6;
	color: #374151;
}
.detail-body :deep(table) { width: 100%; border-collapse: collapse; margin: 8px 0; }
.detail-body :deep(th) { background: #1a5c3a; color: #fff; padding: 7px 10px; text-align: start; font-size: 12px; font-weight: 600; }
.detail-body :deep(td) { padding: 6px 10px; border-bottom: 1px solid #e5e7eb; }
.detail-body :deep(tbody tr:nth-child(even) td) { background: #f9fafb; }
.detail-body :deep(h3) { color: #111827; margin: 14px 0 7px; font-size: 14px; }
.detail-body :deep(h4) { color: #374151; margin: 10px 0 5px; font-size: 13px; }
.detail-body :deep(h5) { color: #6b7280; margin: 8px 0 4px; font-size: 12px; }
.detail-body :deep(strong) { color: #1a5c3a; }
</style>
