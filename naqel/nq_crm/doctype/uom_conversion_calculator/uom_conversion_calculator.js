// Copyright (c) 2025, QualityPoint and contributors
// For license information, please see license.txt

frappe.ui.form.on("UOM Conversion Calculator", {
	onload: function (frm) {
		frm.trigger("setup_calculator");
	},

	setup_calculator: function (frm) {
		// Track to prevent recursive calculations
		frm._calculating = false;
	},

	// Trigger calculation when O or any checkbox changes
	daily_generated_waste: function (frm) {
		if (frm._calculating) return;
		frm.trigger("calculate_parameters");
	},

	calculate_daily_waste_generation_rate: function (frm) {
		if (frm._calculating) return;
		frm.trigger("calculate_parameters");
	},

	calculate_threshold: function (frm) {
		if (frm._calculating) return;
		frm.trigger("calculate_parameters");
	},

	calculate_safety_factor: function (frm) {
		if (frm._calculating) return;
		frm.trigger("calculate_parameters");
	},

	// When user manually changes a parameter, trigger recalculation
	daily_waste_generation_rate: function (frm) {
		if (frm._calculating) return;

		// Check if all three are checked
		let all_checked =
			frm.doc.calculate_daily_waste_generation_rate &&
			frm.doc.calculate_threshold &&
			frm.doc.calculate_safety_factor;

		// Only trigger if this parameter is NOT being calculated OR all are checked
		if (!frm.doc.calculate_daily_waste_generation_rate || all_checked) {
			// When all checked, mark that X was just changed
			if (all_checked) {
				frm._last_changed = "X";
			}
			frm.trigger("calculate_parameters");
		}
	},

	threshold: function (frm) {
		if (frm._calculating) return;

		// Check if all three are checked
		let all_checked =
			frm.doc.calculate_daily_waste_generation_rate &&
			frm.doc.calculate_threshold &&
			frm.doc.calculate_safety_factor;

		// Apply whole number rule if user is manually entering threshold
		if (!frm.doc.calculate_threshold || all_checked) {
			let is_whole_number = frm.doc.whole_number || 0;
			let Y = frm.doc.threshold || 0;

			if (is_whole_number && Y > 0) {
				let rounded_Y = Math.round(Y);
				if (Y !== rounded_Y) {
					// Trim the fraction
					frm._calculating = true;
					frm.set_value("threshold", rounded_Y);
					frm._calculating = false;

					frappe.show_alert(
						{
							message: __("Threshold must be a whole number. Value rounded to {0}", [
								rounded_Y,
							]),
							indicator: "orange",
						},
						3
					);
				}
			}

			// When all checked, mark that Y was just changed
			if (all_checked) {
				frm._last_changed = "Y";
			}
			frm.trigger("calculate_parameters");
		}
	},

	safety_factor: function (frm) {
		if (frm._calculating) return;

		// Check if all three are checked
		let all_checked =
			frm.doc.calculate_daily_waste_generation_rate &&
			frm.doc.calculate_threshold &&
			frm.doc.calculate_safety_factor;

		// Only trigger if this parameter is NOT being calculated OR all are checked
		if (!frm.doc.calculate_safety_factor || all_checked) {
			// When all checked, mark that Z was just changed
			if (all_checked) {
				frm._last_changed = "Z";
			}
			frm.trigger("calculate_parameters");
		}
	},

	from_uom: function (frm) {
		frm.trigger("validate_uoms");
	},

	to_uom: function (frm) {
		frm.trigger("validate_uoms");
		if (!frm._calculating) {
			frm.trigger("calculate_parameters");
		}
	},

	validate_uoms: function (frm) {
		// Check if both UOMs are selected
		if (!frm.doc.from_uom || !frm.doc.to_uom) {
			return false;
		}
		return true;
	},

	calculate_parameters: function (frm) {
		// Only calculate if both UOMs are selected
		if (!frm.trigger("validate_uoms")) {
			return;
		}

		let O = frm.doc.daily_generated_waste || 0;

		// If O is 0, clear all calculated fields
		if (O === 0) {
			frm._calculating = true;
			if (frm.doc.calculate_daily_waste_generation_rate) {
				frm.set_value("daily_waste_generation_rate", 0);
			}
			if (frm.doc.calculate_threshold) {
				frm.set_value("threshold", 0);
			}
			if (frm.doc.calculate_safety_factor) {
				frm.set_value("safety_factor", 0);
			}
			frm._calculating = false;
			return;
		}

		// Get current values
		let X = frm.doc.daily_waste_generation_rate || 0;
		let Y = frm.doc.threshold || 0;
		let Z = frm.doc.safety_factor || 0;
		let is_whole_number = frm.doc.whole_number || 0;

		// Check which parameters to calculate
		let calc_X = frm.doc.calculate_daily_waste_generation_rate || 0;
		let calc_Y = frm.doc.calculate_threshold || 0;
		let calc_Z = frm.doc.calculate_safety_factor || 0;

		// Count how many parameters need to be calculated
		let calc_count = calc_X + calc_Y + calc_Z;

		if (calc_count === 0) {
			return;
		}

		frm._calculating = true;

		if (calc_count === 1) {
			// Calculate only one parameter
			if (calc_X) {
				// Calculate X: X = O / (Y × Z)
				if (Y > 0 && Z > 0) {
					X = O / (Y * Z);
					frm.set_value("daily_waste_generation_rate", flt(X, 2));
				}
			} else if (calc_Y) {
				// Calculate Y: Y = O / (X × Z)
				if (X > 0 && Z > 0) {
					Y = O / (X * Z);
					Y = apply_whole_number_rule(Y, is_whole_number);
					frm.set_value("threshold", Y);
				}
			} else if (calc_Z) {
				// Calculate Z: Z = O / (X × Y)
				if (X > 0 && Y > 0) {
					Z = O / (X * Y);
					frm.set_value("safety_factor", flt(Z, 2));
				}
			}
		} else if (calc_count === 2) {
			// Calculate two parameters - distribute evenly
			if (calc_X && calc_Y) {
				// Calculate X and Y: X × Y = O / Z
				if (Z > 0) {
					let XY = O / Z;
					let sqrt_XY = Math.sqrt(XY);

					// Calculate Y with whole number rule first
					Y = apply_whole_number_rule(sqrt_XY, is_whole_number);

					// Calculate X to balance the equation (absorb the fraction)
					X = XY / Y;

					frm.set_value("threshold", Y);
					frm.set_value("daily_waste_generation_rate", flt(X, 2));
				}
			} else if (calc_X && calc_Z) {
				// Calculate X and Z: X × Z = O / Y
				if (Y > 0) {
					let XZ = O / Y;
					let sqrt_XZ = Math.sqrt(XZ);

					X = sqrt_XZ;
					Z = sqrt_XZ;

					frm.set_value("daily_waste_generation_rate", flt(X, 2));
					frm.set_value("safety_factor", flt(Z, 2));
				}
			} else if (calc_Y && calc_Z) {
				// Calculate Y and Z: Y × Z = O / X
				if (X > 0) {
					let YZ = O / X;
					let sqrt_YZ = Math.sqrt(YZ);

					// Calculate Y with whole number rule first
					Y = apply_whole_number_rule(sqrt_YZ, is_whole_number);

					// Calculate Z to balance the equation (absorb the fraction)
					Z = YZ / Y;

					frm.set_value("threshold", Y);
					frm.set_value("safety_factor", flt(Z, 2));
				}
			}
		} else if (calc_count === 3) {
			// Calculate all three parameters
			// Use frm._last_changed to know which parameter the user just entered
			let last_changed = frm._last_changed || null;

			if (last_changed === "X" && X > 0) {
				// X was just changed, calculate Y and Z
				let YZ = O / X;
				let sqrt_YZ = Math.sqrt(YZ);

				// Calculate Y with whole number rule first
				Y = apply_whole_number_rule(sqrt_YZ, is_whole_number);

				// Calculate Z to balance the equation (absorb the fraction)
				Z = YZ / Y;

				frm.set_value("threshold", Y);
				frm.set_value("safety_factor", flt(Z, 2));
			} else if (last_changed === "Y" && Y > 0) {
				// Y was just changed, calculate X and Z
				let XZ = O / Y;
				let sqrt_XZ = Math.sqrt(XZ);

				X = sqrt_XZ;
				Z = sqrt_XZ;

				frm.set_value("daily_waste_generation_rate", flt(X, 2));
				frm.set_value("safety_factor", flt(Z, 2));
			} else if (last_changed === "Z" && Z > 0) {
				// Z was just changed, calculate X and Y
				let XY = O / Z;
				let sqrt_XY = Math.sqrt(XY);

				// Calculate Y with whole number rule first
				Y = apply_whole_number_rule(sqrt_XY, is_whole_number);

				// Calculate X to balance the equation (absorb the fraction)
				X = XY / Y;

				frm.set_value("daily_waste_generation_rate", flt(X, 2));
				frm.set_value("threshold", Y);
			} else {
				// No specific last changed, or no value entered yet
				// Distribute evenly across all three
				let cube_root = Math.cbrt(O);

				// Calculate Y with whole number rule first
				Y = apply_whole_number_rule(cube_root, is_whole_number);

				// Distribute the remaining value between X and Z
				let remaining = O / Y;
				let sqrt_remaining = Math.sqrt(remaining);

				X = sqrt_remaining;
				Z = sqrt_remaining;

				frm.set_value("daily_waste_generation_rate", flt(X, 2));
				frm.set_value("threshold", Y);
				frm.set_value("safety_factor", flt(Z, 2));
			}

			// Clear the last changed marker
			frm._last_changed = null;
		}

		frm._calculating = false;
	},
});

/**
 * Apply whole number rule to threshold if to_uom requires it
 */
function apply_whole_number_rule(value, is_whole_number) {
	if (is_whole_number) {
		return Math.round(value);
	}
	return flt(value, 2);
}
