# -*- coding: utf-8 -*-
"""Clears values and formulas from standard Identity Data parameters
in the active family document."""

__title__ = "Clear Identity\nData"
__author__ = "Jonathan Bourne"
# No __context__ needed, using runtime check

import sys
from pyrevit import revit, DB, script, forms

# --- Target Built-in Parameters (Identity Data) ---
# Using a set for efficient lookup
IDENTITY_DATA_BIPS = {
    DB.BuiltInParameter.ALL_MODEL_URL,
    DB.BuiltInParameter.ALL_MODEL_TYPE_COMMENTS,
    DB.BuiltInParameter.ALL_MODEL_MODEL,
    DB.BuiltInParameter.ALL_MODEL_MANUFACTURER,
    DB.BuiltInParameter.KEYNOTE_PARAM,
    DB.BuiltInParameter.ALL_MODEL_DESCRIPTION,
    DB.BuiltInParameter.ALL_MODEL_COST,
    DB.BuiltInParameter.UNIFORMAT_CODE,          # Assembly Code
    DB.BuiltInParameter.ALL_MODEL_IMAGE            # Type Image
}

# --- Get Family Document and Manager ---
doc = revit.doc

# --- Runtime Check for Family Document ---
if not doc:
    print("ERROR: No active document found.")
    script.exit()

forms.check_familydoc(doc, exitscript=True)
# --- End of Runtime Check ---

family_mgr = doc.FamilyManager

if not family_mgr:
    print("ERROR: Could not access the Family Manager.")
    script.exit()

# --- Find Matching Parameters ---
params_to_clear = []
all_family_params = family_mgr.Parameters

print("Scanning {} parameters in family: {}".format(all_family_params.Size, doc.Title))

for param in all_family_params:
    # Check if the parameter's definition corresponds to one of our target BIPs
    try:
        bip = param.Definition.BuiltInParameter
        # Check if bip is valid and in our target set
        if bip != DB.BuiltInParameter.INVALID and bip in IDENTITY_DATA_BIPS:
            params_to_clear.append(param)
            # print("Found Identity Data param: {}".format(param.Definition.Name)) # Debugging
    except Exception as e:
        # Some parameters might cause errors when checking BuiltInParameter, skip them
        # print("Skipping parameter due to check error: {}".format(e)) # Debugging
        continue

# --- Perform Clear Action ---
if not params_to_clear:
    print("\nNo standard Identity Data parameters found or accessible in this family.")
else:
    print("\nFound {} standard Identity Data parameter(s) to clear:".format(len(params_to_clear)))
    for p in params_to_clear:
        print("- {}".format(p.Definition.Name))

    # Confirmation before clearing
    confirm = forms.alert(
        msg="Do you want to clear values and formulas for these {} parameters?\n\nThis action cannot be easily undone.".format(len(params_to_clear)),
        title="Confirm Identity Data Clearing",
        yes=True, no=True, exitscript=False
    )

    if confirm: # True means user clicked Yes
        print("\nAttempting to clear parameters...")
        cleared_count = 0
        failed_params = {} # Use dict to store param name and error reason

        # IMPORTANT: Modifications require a transaction
        with revit.Transaction("Clear Identity Data Parameters"):
            for param_to_clear in params_to_clear:
                param_name = param_to_clear.Definition.Name
                cleared_successfully = True
                error_details = []

                # 1. Try to clear the formula
                if param_to_clear.CanAssignFormula:
                    try:
                        if family_mgr.GetFormula(param_to_clear): # Only set if it actually has a formula
                            family_mgr.SetFormula(param_to_clear, None)
                            # print("  Cleared formula for {}".format(param_name)) # Debugging
                    except Exception as formula_err:
                        cleared_successfully = False
                        error_details.append("Formula clear failed: {}".format(formula_err))

                # 2. Try to clear the value based on StorageType
                try:
                    storage_type = param_to_clear.StorageType
                    if storage_type == DB.StorageType.String:
                        family_mgr.Set(param_to_clear, "")
                    elif storage_type == DB.StorageType.Double: # Includes numbers, currency, length, area etc.
                         # Check if it's Type Image (ElementId stored as Double internally sometimes?) - Use InvalidElementId
                        if param_to_clear.Definition.BuiltInParameter == DB.BuiltInParameter.ALL_MODEL_IMAGE:
                            family_mgr.Set(param_to_clear, DB.ElementId.InvalidElementId)
                        else:
                            family_mgr.Set(param_to_clear, 0.0)
                    elif storage_type == DB.StorageType.Integer:
                        family_mgr.Set(param_to_clear, 0)
                    elif storage_type == DB.StorageType.ElementId:
                        # Includes Type Image if correctly stored as ElementId
                        family_mgr.Set(param_to_clear, DB.ElementId.InvalidElementId)
                    # print("  Cleared value for {}".format(param_name)) # Debugging

                except Exception as value_err:
                    # Check if it's read-only before reporting as a failure
                    if not param_to_clear.IsReadOnly:
                         cleared_successfully = False
                         error_details.append("Value clear failed: {}".format(value_err))
                    # else: If read-only, not really a failure we can fix

                # Update counts
                if cleared_successfully:
                    cleared_count += 1
                elif param_name not in failed_params: # Only record first failure reason
                     failed_params[param_name] = "; ".join(error_details)

        # --- Summary ---
        print("\n----- Clearing Summary -----")
        print("Attempted to clear: {} parameters.".format(len(params_to_clear)))
        print("Successfully cleared (formula and/or value): {} parameters.".format(cleared_count))
        if failed_params:
            print("Failed to fully clear: {} parameters:".format(len(failed_params)))
            for fp_name, fp_reason in failed_params.items():
                print("- {}: {}".format(fp_name, fp_reason))
        print("----------------------------")

    else: # False means user clicked No or closed the dialog
        print("\nClearing cancelled by user.")

