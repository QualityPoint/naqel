import frappe
from frappe.query_builder.functions import Count
from frappe import _


# ── Config editor: load / simulate / save ────────────────────────────────────
# Clicking a chart bin opens a dialog editor. These three endpoints power it:
#   get_config_for_edit  → the full configuration for the dialog
#   simulate_config      → recompute a draft WITHOUT saving (live preview)
#   save_config          → persist the draft (Service Configuration write perm)

_BAND_INPUT_FIELDS = ('container_type', 'max_threshold', 'count')
_BAND_DERIVED_FIELDS = ('container_standard_volume', 'container_volume_unit',
                        'total_volume', 'conversion_factor',
                        'container_converted_volume', 'total_converted_volume')
_UOM_FIELDS = ('subsidiary_uom', 'conversion_factor')
_RATING_FIELDS = ('rating', 'safety_factor')


def _band_dict(row):
	return {f: row.get(f) for f in (_BAND_INPUT_FIELDS + _BAND_DERIVED_FIELDS)}


def _config_payload(doc, can_write):
	"""Shape a Service Configuration doc into the editor's payload."""
	return {
		'name': doc.name,
		'title': doc.title or doc.name,
		'service_type': doc.service_type,
		'isic_classification': doc.isic_classification,
		'isic_classification_category': doc.isic_classification_category,
		'can_write': can_write,
		# UOMs tab
		'facility_uom': doc.facility_uom,
		'default_facility_unit': doc.default_facility_unit,
		'default_volume_unit': doc.default_volume_unit,
		'uoms': [{f: r.get(f) for f in _UOM_FIELDS} for r in (doc.uoms or [])],
		# Classification tab
		'generation_classification': [_band_dict(r) for r in (doc.generation_classification or [])],
		# Settings tab
		'calculate_facility_wastes_by': doc.calculate_facility_wastes_by,
		'calculate_generation_rate_by': doc.calculate_generation_rate_by,
		'allocate_container_for_each_waste_type': doc.allocate_container_for_each_waste_type or 0,
		# Ratings tab
		'ratings': [{f: r.get(f) for f in _RATING_FIELDS} for r in (doc.ratings or [])],
		# Read-only derived statistics
		'stats': {
			'mean_threshold': doc.mean_threshold,
			'median_threshold': doc.median_threshold,
			'mean_volume': doc.mean_volume,
			'median_volume': doc.median_volume,
			'mean_generation_rate': doc.mean_generation_rate,
			'median_generation_rate': doc.median_generation_rate,
		},
	}


@frappe.whitelist()
def get_editor_options():
	"""Dropdown option lists the config editor needs, in one round-trip."""
	facility_uoms = frappe.get_all(
		'Facility UOM',
		fields=['name', 'uom_name', 'default_uom', 'must_be_whole_number'],
		order_by='uom_name')
	container_types = frappe.get_all(
		'Container Type', fields=['name', 'volume', 'volume_unit'], order_by='name')
	return {
		'facility_uoms': facility_uoms,
		'container_types': container_types,
	}


@frappe.whitelist()
def get_config_for_edit(name):
	"""Full Service Configuration for the dialog editor (read perm enforced by get_doc)."""
	doc = frappe.get_doc('Service Configuration', name)
	doc.check_permission('read')
	can_write = bool(doc.has_permission('write'))
	return _config_payload(doc, can_write)


def _apply_draft(doc, payload):
	"""Overlay the editable parts of ``payload`` onto a Service Configuration doc."""
	doc.facility_uom = payload.get('facility_uom')
	# default_facility_unit follows the facility UOM (mirrors the form's fetch).
	if doc.facility_uom:
		doc.default_facility_unit = frappe.db.get_value(
			'Facility UOM', doc.facility_uom, 'default_uom')
	# default_volume_unit is read-only — sourced from Naqel Settings, never edited here.
	doc.calculate_facility_wastes_by = payload.get('calculate_facility_wastes_by')
	doc.calculate_generation_rate_by = payload.get('calculate_generation_rate_by')
	doc.allocate_container_for_each_waste_type = \
		1 if payload.get('allocate_container_for_each_waste_type') else 0

	# Replace the child tables from the (input-only) draft; derived columns recompute.
	doc.set('uoms', [
		{f: r.get(f) for f in _UOM_FIELDS} for r in (payload.get('uoms') or [])
	])

	# Bands: also populate container volume + unit from the Container Type. fetch_from
	# only runs on save, so without this the in-memory recompute (simulate) would see
	# zero volume → every bar collapses to the zero line.
	band_rows = payload.get('generation_classification') or []
	ctypes = list({r.get('container_type') for r in band_rows if r.get('container_type')})
	cmeta = {
		c['name']: c for c in frappe.get_all(
			'Container Type', filters={'name': ['in', ctypes]},
			fields=['name', 'volume', 'volume_unit'])
	} if ctypes else {}
	doc.set('generation_classification', [
		{
			'container_type': r.get('container_type'),
			'max_threshold': r.get('max_threshold'),
			'count': r.get('count'),
			'container_standard_volume': cmeta.get(r.get('container_type'), {}).get('volume'),
			'container_volume_unit': cmeta.get(r.get('container_type'), {}).get('volume_unit'),
		}
		for r in band_rows
	])
	doc.set('ratings', [
		{f: r.get(f) for f in _RATING_FIELDS} for r in (payload.get('ratings') or [])
	])
	return doc


def _recompute(doc):
	"""Recompute the band volumes + derived statistics, mirroring the Service
	Configuration's before_validate — but WITHOUT the rating uniqueness validation
	(it would throw on transient mid-edit duplicates, and ratings don't affect the
	waste preview). Save still runs the full validation via doc.save()."""
	from naqel.utils import waste_calculations
	waste_calculations.calculate_child_table_volumes(doc, 'default_volume_unit')
	waste_calculations.calculate_threshold_statistics(doc)
	waste_calculations.calculate_volume_statistics(doc, 'total_converted_volume')
	waste_calculations.calculate_generation_rates(doc)


@frappe.whitelist()
def simulate_config(payload, uom_value=None):
	"""Recompute a draft configuration in memory (no save) and return the recomputed
	bands, derived stats, and the projected calculated waste + suggested container at
	``uom_value`` — using the config's own method (the same algorithm the calculator
	and the chart share)."""
	from naqel.nq_setup.doctype.waste_calculator.waste_calculator import (
		calculate_by_generation_rate, pick_container, select_cluster_waste,
	)

	payload = frappe.parse_json(payload)
	uom_value = frappe.utils.flt(uom_value) or 100.0

	# Start from the persisted doc (keeps reqd identity fields), overlay the draft,
	# recompute — but never save.
	doc = frappe.get_doc('Service Configuration', payload.get('name'))
	doc.check_permission('read')
	_apply_draft(doc, payload)
	_recompute(doc)

	bands = list(doc.generation_classification or [])
	if doc.calculate_facility_wastes_by == 'Cluster Classification':
		by_threshold = sorted(bands, key=lambda c: frappe.utils.flt(c.max_threshold))
		calc = select_cluster_waste(doc, uom_value, by_threshold)
	else:
		calc = calculate_by_generation_rate(doc, uom_value, None)
	calculated_waste = frappe.utils.flt(calc.get('facility_waste'))

	by_volume = sorted(bands, key=lambda c: frappe.utils.flt(c.total_converted_volume))
	container = pick_container(by_volume, calculated_waste)

	return {
		'generation_classification': [_band_dict(r) for r in bands],
		'stats': {
			'mean_threshold': doc.mean_threshold,
			'median_threshold': doc.median_threshold,
			'mean_volume': doc.mean_volume,
			'median_volume': doc.median_volume,
			'mean_generation_rate': doc.mean_generation_rate,
			'median_generation_rate': doc.median_generation_rate,
		},
		'calculated_waste': calculated_waste,
		'selected_threshold': calc.get('selected_threshold'),
		'suggested_container': container.get('container'),
		'suggested_container_count': container.get('count'),
		'default_volume_unit': doc.default_volume_unit,
	}


@frappe.whitelist()
def save_config(name, payload):
	"""Persist the draft to the Service Configuration (write perm enforced by save())."""
	payload = frappe.parse_json(payload)
	doc = frappe.get_doc('Service Configuration', name)
	_apply_draft(doc, payload)
	doc.save()  # runs before_validate recompute + validations; checks write permission
	return _config_payload(doc, can_write=True)


@frappe.whitelist()
def get_service_types():
	"""Return all Service Types with translated service_name for the filter dropdown."""
	ST = frappe.qb.DocType('Service Type')
	items = (
		frappe.qb.from_(ST)
		.select(ST.name, ST.service_name)
		.orderby(ST.service_name)
		.run(as_dict=True)
	)
	# A service "carries multiple waste types" when its `wastes` table has > 1 row;
	# this gates the "Total | By Waste Type" toggle on the page.
	SWT = frappe.qb.DocType('Service Waste Type')
	waste_counts = (
		frappe.qb.from_(SWT)
		.select(SWT.parent, Count('*').as_('cnt'))
		.where(SWT.parenttype == 'Service Type')
		.groupby(SWT.parent)
		.run(as_dict=True)
	)
	count_map = {row['parent']: row['cnt'] for row in waste_counts}
	for item in items:
		item['service_name'] = frappe._(item['service_name'])
		item['has_multiple_wastes'] = 1 if count_map.get(item['name'], 0) > 1 else 0
	return items


@frappe.whitelist()
def get_uoms():
	"""Return Facility UOM records (not standard UOM) for the filter dropdown."""
	FUOM = frappe.qb.DocType('Facility UOM')
	items = (
		frappe.qb.from_(FUOM)
		.select(FUOM.name, FUOM.uom_name)
		.orderby(FUOM.uom_name)
		.run(as_dict=True)
	)
	for item in items:
		item['uom_name'] = frappe._(item['uom_name'])
	return items


@frappe.whitelist()
def get_chart_data(service_type=None, isic_level=None, uom=None,
                   uom_value=None, waste_calc_by='generation_rate',
                   rate_type='mean', sort_order='normal', matched_only=None,
                   by_waste_type=0):
	"""
	Return Service Configuration rows for the ECharts canvas.

	Calculations delegate to the Waste Calculator's shared, DB-free helpers so this page
	and the calculator stay in lock-step:
	    - calculated_waste   → calculate_by_generation_rate / select_cluster_waste
	    - suggested container → pick_container (incl. scaling the largest container when
	                            the waste exceeds every classification)
	Classifications are bulk-fetched once for the whole chart (3 queries total,
	independent of how many configurations are plotted).

	The toolbar's ``waste_calc_by`` (generation_rate | cluster_classification) and
	``rate_type`` (mean | median) act as global overrides so every config is compared
	under the same method; ``uom_value`` plays the role of the facility measurement.

	matched_only:
	    1    → only configs whose facility_uom matches the selected uom  (Phase 1)
	    0    → only configs whose facility_uom does NOT match            (Phase 2)
	    None → all configs
	"""
	from naqel.nq_setup.doctype.waste_calculator.waste_calculator import (
		calculate_by_generation_rate,
		pick_container,
		select_cluster_waste,
	)

	uom_value = frappe.utils.flt(uom_value) or 100.0
	uom = uom or ''

	if rate_type not in ('mean', 'median'):
		rate_type = 'mean'
	if waste_calc_by not in ('generation_rate', 'cluster_classification'):
		waste_calc_by = 'generation_rate'
	if sort_order not in ('asc', 'desc', 'normal'):
		sort_order = 'normal'

	if matched_only is not None:
		try:
			matched_only = int(matched_only)
		except (ValueError, TypeError):
			matched_only = None

	# Candidate configurations (bounded by the chosen service type / ISIC level).
	filters = {'disabled': 0}
	if service_type:
		filters['service_type'] = service_type
	if isic_level:
		filters['isic_classification_category'] = isic_level

	configs = frappe.get_all(
		'Service Configuration',
		filters=filters,
		fields=[
			'name', 'title', 'isic_classification_category', 'facility_uom',
			'mean_generation_rate', 'median_generation_rate', 'default_volume_unit',
		],
	)

	# Phase split: keep only matched / unmatched configs when a UOM is selected.
	if uom and matched_only is not None:
		if matched_only == 1:
			configs = [c for c in configs if c.facility_uom == uom]
		else:
			configs = [c for c in configs if c.facility_uom != uom]

	# Bulk-fetch every config's classifications in ONE query, then select in Python —
	# so the whole chart costs 3 queries regardless of how many configs are shown.
	clusters_by_parent = {}
	names = [c.name for c in configs]
	if names:
		for w in frappe.get_all(
			'Waste Generation Classification',
			filters={'parent': ['in', names]},
			fields=['parent', 'max_threshold', 'total_converted_volume',
			        'container_type', 'count'],
		):
			clusters_by_parent.setdefault(w.parent, []).append(w)

	# The toolbar overrides which rate the calculator's algorithm applies.
	override_rate_by = 'Median' if rate_type == 'median' else 'Mean'

	rows = []
	for cfg in configs:
		# Minimal config view the calculator's helpers need; uom_value stands in for
		# the facility measurement, and the rate method is the toolbar's override.
		cfg_doc = frappe._dict({
			'name': cfg.name,
			'calculate_generation_rate_by': override_rate_by,
			'mean_generation_rate': cfg.mean_generation_rate,
			'median_generation_rate': cfg.median_generation_rate,
		})
		clusters = clusters_by_parent.get(cfg.name, [])

		if waste_calc_by == 'cluster_classification':
			by_threshold = sorted(clusters, key=lambda c: frappe.utils.flt(c.max_threshold))
			calc = select_cluster_waste(cfg_doc, uom_value, by_threshold)
		else:
			calc = calculate_by_generation_rate(cfg_doc, uom_value, None)
		calculated_waste = frappe.utils.flt(calc.get('facility_waste'))

		uom_match = 1 if (uom and cfg.facility_uom == uom) else 0

		# Suggest a container only for UOM-matched configs (others aren't comparable at
		# the entered value); pick_container handles exceed-scaling of the largest.
		suggested_container = None
		suggested_count = None
		if uom_match:
			by_volume = sorted(clusters, key=lambda c: frappe.utils.flt(c.total_converted_volume))
			container = pick_container(by_volume, calculated_waste)
			suggested_container = container.get('container')
			suggested_count = container.get('count')

		rows.append({
			'name': cfg.name,
			'title': cfg.title or cfg.name,
			'isic_level': cfg.isic_classification_category,
			'facility_uom': cfg.facility_uom,
			'mean_generation_rate': frappe.utils.flt(cfg.mean_generation_rate),
			'median_generation_rate': frappe.utils.flt(cfg.median_generation_rate),
			'default_volume_unit': cfg.default_volume_unit,
			'calculated_waste': calculated_waste,
			'uom_match': uom_match,
			'suggested_container': suggested_container,
			'suggested_container_count': suggested_count,
		})

	# Sort (mirrors the previous SQL ordering: by waste then title, or title alone).
	if sort_order == 'asc':
		rows.sort(key=lambda r: (r['calculated_waste'], r['title'] or ''))
	elif sort_order == 'desc':
		rows.sort(key=lambda r: (-r['calculated_waste'], r['title'] or ''))
	else:
		rows.sort(key=lambda r: (r['title'] or ''))

	# Attach waste distributions when stacked-by-waste-type mode is requested.
	if frappe.utils.cint(by_waste_type) and rows:
		names = [r['name'] for r in rows]
		dist_rows = frappe.get_all(
			'Waste Distribution',
			filters={'parent': ['in', names]},
			fields=['parent', 'waste_type', 'distribution_percentage'],
			order_by='parent, idx',
		)
		dist_map = {}
		for d in dist_rows:
			dist_map.setdefault(d.parent, []).append({
				'waste_type': d.waste_type,
				'pct': frappe.utils.flt(d.distribution_percentage),
			})
		for row in rows:
			row['waste_distributions'] = dist_map.get(row['name'], [])

	return rows
