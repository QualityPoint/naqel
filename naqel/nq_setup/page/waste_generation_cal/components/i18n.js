// Shared translation helper for the Waste Calculator page components.
//
// SetVueGlobals(app) injects `__` as a Vue global property, which covers templates,
// but `<script setup>` cannot read global properties — so this exposes the same
// Frappe translator for use in component scripts (and templates) from one place.
export const __ = (key) => (window.__ ? window.__(key) : key);
