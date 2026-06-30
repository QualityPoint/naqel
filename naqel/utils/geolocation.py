"""
Geolocation Utilities

This module provides generic utility functions for synchronizing between
Frappe's Geolocation field (JSON format) and separate Float latitude/longitude fields.

Usage:
    # In your doctype's validate() or before_save():
    from naqel.utils.geolocation import sync_geolocation_to_floats, sync_floats_to_geolocation
    
    # Sync geolocation to float fields
    sync_geolocation_to_floats(self, 'location', 'latitude', 'longitude')
    
    # Or sync float fields to geolocation
    sync_floats_to_geolocation(self, 'latitude', 'longitude', 'location')
"""

import json
import frappe
from frappe import _


def parse_geolocation(geolocation_value):
    """
    Parse geolocation field value and extract latitude and longitude.

    Args:
        geolocation_value: Geolocation field value (can be string JSON or dict)

    Returns:
        tuple: (latitude, longitude) as floats, or (None, None) if parsing fails

    Examples:
        >>> parse_geolocation('{"type":"FeatureCollection","features":[{"type":"Feature","properties":{},"geometry":{"type":"Point","coordinates":[46.7382,24.7136]}}]}')
        (24.7136, 46.7382)

        >>> parse_geolocation(None)
        (None, None)
    """
    if not geolocation_value:
        return None, None

    try:
        # Parse JSON if it's a string
        if isinstance(geolocation_value, str):
            geo_data = json.loads(geolocation_value)
        else:
            geo_data = geolocation_value

        # Extract coordinates from GeoJSON format
        # Geolocation field stores data as: {"type":"FeatureCollection","features":[...]}
        # If multiple pins exist, use the last one (most recently added)
        if geo_data.get("type") == "FeatureCollection" and geo_data.get("features"):
            feature = geo_data["features"][-1]  # Get last feature
            if feature.get("geometry", {}).get("type") == "Point":
                coordinates = feature["geometry"].get("coordinates", [])
                if len(coordinates) >= 2:
                    # GeoJSON format is [longitude, latitude]
                    longitude = float(coordinates[0])
                    latitude = float(coordinates[1])
                    return latitude, longitude

        # Try alternate format: direct coordinates
        elif isinstance(geo_data, dict) and "coordinates" in geo_data:
            coordinates = geo_data["coordinates"]
            if len(coordinates) >= 2:
                longitude = float(coordinates[0])
                latitude = float(coordinates[1])
                return latitude, longitude

    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        frappe.log_error(
            message=f"Failed to parse geolocation: {str(e)}\nValue: {geolocation_value}",
            title="Geolocation Parse Error"
        )

    return None, None


def build_geolocation_json(latitude, longitude):
    """
    Build GeoJSON format for Geolocation field from latitude and longitude.

    Args:
        latitude: Latitude as float
        longitude: Longitude as float

    Returns:
        str: GeoJSON formatted string for Geolocation field, or None if inputs invalid

    Examples:
        >>> build_geolocation_json(24.7136, 46.7382)
        '{"type":"FeatureCollection","features":[{"type":"Feature","properties":{},"geometry":{"type":"Point","coordinates":[46.7382,24.7136]}}]}'
    """
    if latitude is None or longitude is None:
        return None

    try:
        lat = float(latitude)
        lng = float(longitude)

        # Build GeoJSON FeatureCollection format
        geo_json = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {
                        "type": "Point",
                        # GeoJSON format is [longitude, latitude]
                        "coordinates": [lng, lat]
                    }
                }
            ]
        }

        return json.dumps(geo_json)

    except (ValueError, TypeError) as e:
        frappe.log_error(
            message=f"Failed to build geolocation JSON: {str(e)}\nLat: {latitude}, Lng: {longitude}",
            title="Geolocation Build Error"
        )
        return None


def sync_geolocation_to_floats(doc, geolocation_field='location', latitude_field='latitude', longitude_field='longitude'):
    """
    Synchronize Geolocation field to separate Float latitude/longitude fields.

    This function extracts coordinates from a Geolocation field and updates
    the corresponding Float fields. If multiple pins exist, keeps only the last one.
    Use in validate() or before_save() hooks.

    Args:
        doc: Frappe document object
        geolocation_field: Name of the Geolocation field (default: 'location')
        latitude_field: Name of the latitude Float field (default: 'latitude')
        longitude_field: Name of the longitude Float field (default: 'longitude')

    Returns:
        bool: True if sync was successful, False otherwise

    Examples:
        # In your doctype controller:
        def validate(self):
            sync_geolocation_to_floats(self)

        # With custom field names:
        def validate(self):
            sync_geolocation_to_floats(self, 'geo_location', 'lat', 'lng')
    """
    geolocation_value = doc.get(geolocation_field)

    if not geolocation_value:
        # Clear float fields if geolocation is empty
        doc.set(latitude_field, None)
        doc.set(longitude_field, None)
        return False

    # Parse and get the last pin coordinates
    latitude, longitude = parse_geolocation(geolocation_value)

    if latitude is not None and longitude is not None:
        # Update float fields
        doc.set(latitude_field, latitude)
        doc.set(longitude_field, longitude)

        # Keep only the last pin - rebuild geolocation with single point
        try:
            if isinstance(geolocation_value, str):
                geo_data = json.loads(geolocation_value)
            else:
                geo_data = geolocation_value

            if geo_data.get("type") == "FeatureCollection" and geo_data.get("features"):
                if len(geo_data["features"]) > 1:
                    # Multiple pins detected - keep only the last one
                    single_pin_json = build_geolocation_json(
                        latitude, longitude)
                    if single_pin_json:
                        doc.set(geolocation_field, single_pin_json)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            frappe.log_error(
                message=f"Failed to clean multiple pins: {str(e)}",
                title="Geolocation Multiple Pins Cleanup Error"
            )

        return True

    return False


def sync_floats_to_geolocation(doc, latitude_field='latitude', longitude_field='longitude', geolocation_field='location'):
    """
    Synchronize Float latitude/longitude fields to Geolocation field.

    This function builds a GeoJSON from Float fields and updates the
    Geolocation field. Use when users update lat/lng directly.

    Args:
        doc: Frappe document object
        latitude_field: Name of the latitude Float field (default: 'latitude')
        longitude_field: Name of the longitude Float field (default: 'longitude')
        geolocation_field: Name of the Geolocation field (default: 'location')

    Returns:
        bool: True if sync was successful, False otherwise

    Examples:
        # In your doctype controller:
        def validate(self):
            # Only sync if float fields are manually updated
            if self.has_value_changed('latitude') or self.has_value_changed('longitude'):
                sync_floats_to_geolocation(self)
    """
    latitude = doc.get(latitude_field)
    longitude = doc.get(longitude_field)

    if latitude is None and longitude is None:
        # Clear geolocation if both floats are empty
        doc.set(geolocation_field, None)
        return False

    if latitude is None or longitude is None:
        # Don't update if only one coordinate is provided
        frappe.msgprint(
            _("Both latitude and longitude are required to update location."),
            indicator="orange"
        )
        return False

    geo_json = build_geolocation_json(latitude, longitude)

    if geo_json:
        doc.set(geolocation_field, geo_json)
        return True

    return False


def get_distance_between_points(lat1, lon1, lat2, lon2, unit='km'):
    """
    Calculate distance between two geographic points using Haversine formula.

    Args:
        lat1: Latitude of first point
        lon1: Longitude of first point
        lat2: Latitude of second point
        lon2: Longitude of second point
        unit: Distance unit - 'km' for kilometers, 'mi' for miles (default: 'km')

    Returns:
        float: Distance between points in specified unit

    Examples:
        >>> get_distance_between_points(24.7136, 46.7382, 21.4225, 39.8262)  # Riyadh to Mecca
        862.37
    """
    import math

    # Convert to radians
    lat1_rad = math.radians(float(lat1))
    lon1_rad = math.radians(float(lon1))
    lat2_rad = math.radians(float(lat2))
    lon2_rad = math.radians(float(lon2))

    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * \
        math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))

    # Earth radius in kilometers
    radius_km = 6371.0

    distance = radius_km * c

    if unit == 'mi':
        distance = distance * 0.621371  # Convert to miles

    return round(distance, 2)
