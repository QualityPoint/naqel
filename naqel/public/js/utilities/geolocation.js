/**
 * Geolocation Utilities
 * 
 * Generic utility functions for synchronizing between Frappe's Geolocation field (GeoJSON format)
 * and separate Float latitude/longitude fields.
 * 
 * Usage:
 *     // In your doctype's JavaScript file:
 *     frappe.ui.form.on("Your DocType", {
 *         location: function(frm) {
 *             naqel.geolocation.sync_geolocation_to_floats(frm, 'location', 'latitude', 'longitude');
 *         },
 *         latitude: function(frm) {
 *             naqel.geolocation.sync_floats_to_geolocation(frm, 'latitude', 'longitude', 'location');
 *         }
 *     });
 */

frappe.provide("naqel.geolocation");

naqel.geolocation = {
    /**
     * Parse geolocation field and extract latitude/longitude
     * @param {string|object} geolocation_value - Geolocation field value (GeoJSON)
     * @returns {object} {latitude, longitude} or {latitude: null, longitude: null}
     * 
     * @example
     * const coords = naqel.geolocation.parse_geolocation(frm.doc.location);
     * console.log(coords.latitude, coords.longitude);
     */
    parse_geolocation(geolocation_value) {
        if (!geolocation_value) {
            return { latitude: null, longitude: null };
        }

        try {
            // Parse JSON if it's a string
            const geo_data = typeof geolocation_value === 'string'
                ? JSON.parse(geolocation_value)
                : geolocation_value;

            // Extract coordinates from GeoJSON FeatureCollection format
            // If multiple pins exist, use the last one (most recently added)
            if (geo_data.type === "FeatureCollection" && geo_data.features && geo_data.features.length > 0) {
                const feature = geo_data.features[geo_data.features.length - 1];
                if (feature.geometry && feature.geometry.type === "Point" && feature.geometry.coordinates) {
                    const coordinates = feature.geometry.coordinates;
                    if (coordinates.length >= 2) {
                        // GeoJSON format is [longitude, latitude]
                        return {
                            latitude: parseFloat(coordinates[1]),
                            longitude: parseFloat(coordinates[0])
                        };
                    }
                }
            }
            // Try alternate format: direct coordinates
            else if (geo_data.coordinates && geo_data.coordinates.length >= 2) {
                return {
                    latitude: parseFloat(geo_data.coordinates[1]),
                    longitude: parseFloat(geo_data.coordinates[0])
                };
            }
        } catch (e) {
            console.error("Failed to parse geolocation:", e, geolocation_value);
        }

        return { latitude: null, longitude: null };
    },

    /**
     * Build GeoJSON for Geolocation field from latitude/longitude
     * @param {number} latitude - Latitude value
     * @param {number} longitude - Longitude value
     * @returns {string|null} GeoJSON formatted string or null
     * 
     * @example
     * const geo_json = naqel.geolocation.build_geolocation_json(24.7136, 46.7382);
     * frm.set_value('location', geo_json);
     */
    build_geolocation_json(latitude, longitude) {
        if (latitude == null || longitude == null) {
            return null;
        }

        try {
            const lat = parseFloat(latitude);
            const lng = parseFloat(longitude);

            if (isNaN(lat) || isNaN(lng)) {
                return null;
            }

            // Build GeoJSON FeatureCollection format
            const geo_json = {
                type: "FeatureCollection",
                features: [
                    {
                        type: "Feature",
                        properties: {},
                        geometry: {
                            type: "Point",
                            coordinates: [lng, lat]  // GeoJSON format is [longitude, latitude]
                        }
                    }
                ]
            };

            return JSON.stringify(geo_json);
        } catch (e) {
            console.error("Failed to build geolocation JSON:", e);
            return null;
        }
    },

    /**
     * Sync Geolocation field to separate Float latitude/longitude fields
     * @param {object} frm - The form object
     * @param {string} geolocation_field - Name of Geolocation field (default: 'location')
     * @param {string} latitude_field - Name of latitude field (default: 'latitude')
     * @param {string} longitude_field - Name of longitude field (default: 'longitude')
     * 
     * @example
     * // In your doctype's JavaScript:
     * frappe.ui.form.on("Your DocType", {
     *     location: function(frm) {
     *         naqel.geolocation.sync_geolocation_to_floats(frm);
     *     }
     * });
     */
    sync_geolocation_to_floats(frm, geolocation_field = 'location', latitude_field = 'latitude', longitude_field = 'longitude') {
        const geolocation_value = frm.doc[geolocation_field];

        // Check if geolocation is empty or has no features (cleared by user)
        let is_empty = false;

        if (!geolocation_value) {
            is_empty = true;
        } else {
            try {
                const geo_data = typeof geolocation_value === 'string'
                    ? JSON.parse(geolocation_value)
                    : geolocation_value;

                // Check if FeatureCollection exists but has no features (Clear All clicked)
                if (geo_data.type === "FeatureCollection" && (!geo_data.features || geo_data.features.length === 0)) {
                    is_empty = true;
                }
            } catch (e) {
                is_empty = true;
            }
        }

        if (is_empty) {
            // Clear float fields if geolocation is empty or has no features
            frm.set_value(latitude_field, null);
            frm.set_value(longitude_field, null);
            return;
        }

        // Parse and get the last pin coordinates
        const { latitude, longitude } = this.parse_geolocation(geolocation_value);

        if (latitude != null && longitude != null) {
            // Update float fields
            frm.set_value(latitude_field, latitude);
            frm.set_value(longitude_field, longitude);

            // Keep only the last pin - rebuild geolocation with single point
            try {
                const geo_data = typeof geolocation_value === 'string'
                    ? JSON.parse(geolocation_value)
                    : geolocation_value;

                if (geo_data.type === "FeatureCollection" && geo_data.features && geo_data.features.length > 1) {
                    // Multiple pins detected - keep only the last one
                    const single_pin_json = this.build_geolocation_json(latitude, longitude);
                    if (single_pin_json) {
                        frm.set_value(geolocation_field, single_pin_json);
                    }
                }
            } catch (e) {
                console.error("Failed to clean multiple pins:", e);
            }
        } else {
            // If parsing returned null coordinates, clear float fields
            frm.set_value(latitude_field, null);
            frm.set_value(longitude_field, null);
        }
    },

    /**
     * Sync Float latitude/longitude fields to Geolocation field
     * @param {object} frm - The form object
     * @param {string} latitude_field - Name of latitude field (default: 'latitude')
     * @param {string} longitude_field - Name of longitude field (default: 'longitude')
     * @param {string} geolocation_field - Name of Geolocation field (default: 'location')
     * 
     * @example
     * // In your doctype's JavaScript:
     * frappe.ui.form.on("Your DocType", {
     *     latitude: function(frm) {
     *         naqel.geolocation.sync_floats_to_geolocation(frm);
     *     },
     *     longitude: function(frm) {
     *         naqel.geolocation.sync_floats_to_geolocation(frm);
     *     }
     * });
     */
    sync_floats_to_geolocation(frm, latitude_field = 'latitude', longitude_field = 'longitude', geolocation_field = 'location') {
        const latitude = frm.doc[latitude_field];
        const longitude = frm.doc[longitude_field];

        if (latitude == null && longitude == null) {
            // Clear geolocation if both floats are empty
            frm.set_value(geolocation_field, null);
            return;
        }

        if (latitude == null || longitude == null) {
            // Don't update if only one coordinate is provided
            frappe.show_alert({
                message: __("Both latitude and longitude are required to update location."),
                indicator: "orange"
            });
            return;
        }

        const geo_json = this.build_geolocation_json(latitude, longitude);

        if (geo_json) {
            frm.set_value(geolocation_field, geo_json);
        }
    },

    /**
     * Calculate distance between two geographic points using Haversine formula
     * @param {number} lat1 - Latitude of first point
     * @param {number} lon1 - Longitude of first point
     * @param {number} lat2 - Latitude of second point
     * @param {number} lon2 - Longitude of second point
     * @param {string} unit - Distance unit: 'km' or 'mi' (default: 'km')
     * @returns {number} Distance in specified unit
     * 
     * @example
     * // Calculate distance from Riyadh to Mecca
     * const distance = naqel.geolocation.get_distance_between_points(24.7136, 46.7382, 21.4225, 39.8262);
     * console.log(distance + ' km');
     */
    get_distance_between_points(lat1, lon1, lat2, lon2, unit = 'km') {
        // Convert to radians
        const toRad = (deg) => deg * Math.PI / 180;

        const lat1_rad = toRad(parseFloat(lat1));
        const lon1_rad = toRad(parseFloat(lon1));
        const lat2_rad = toRad(parseFloat(lat2));
        const lon2_rad = toRad(parseFloat(lon2));

        // Haversine formula
        const dlat = lat2_rad - lat1_rad;
        const dlon = lon2_rad - lon1_rad;

        const a = Math.sin(dlat / 2) ** 2 +
            Math.cos(lat1_rad) * Math.cos(lat2_rad) *
            Math.sin(dlon / 2) ** 2;
        const c = 2 * Math.asin(Math.sqrt(a));

        // Earth radius in kilometers
        const radius_km = 6371.0;

        let distance = radius_km * c;

        if (unit === 'mi') {
            distance = distance * 0.621371;  // Convert to miles
        }

        return parseFloat(distance.toFixed(2));
    }
};
