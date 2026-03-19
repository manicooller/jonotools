# -*- coding: utf-8 -*-
"""Purges shared parameters from the active family document,
except for a predefined list of essential parameters."""

# REMOVED __context__ directive - will rely on runtime check instead.
# __context__ = "Family"
__title__ = "Purge Shared\nParams"
__author__ = "Jonathan Bourne"


import sys
from pyrevit import revit, DB, script, forms # Ensure forms is imported
from pyrevit.framework import Guid

# --- Parameters to KEEP ---
cfg = script.get_config()

DEFAULT_TEXT = (
    "PARAM\t11111111-2222-3333-4444-555555555555\tJONO_Default Width\tLENGTH\t\t1\t1\t\t1\t0\n"
    "PARAM\taaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee\tJONO_Default Height\tLENGTH\t\t1\t1\t\t1\t0\n"
    "PARAM\t99999999-8888-7777-6666-555555555555\tJONO_Default Depth\tLENGTH\t\t1\t1\t\t1\t0"
)

# Fetch saved raw text from config
saved_text = getattr(cfg, 'purge_whitelist_raw', DEFAULT_TEXT)

KEEP_GUIDS = set()
for line in saved_text.splitlines():
    parts = line.split('\t')
    # If line starts with 'PARAM' and has enough columns
    if len(parts) >= 3 and parts[0] == 'PARAM':
        guid_str = parts[1].strip().lower()
        KEEP_GUIDS.add(guid_str)



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

# --- Find Parameters to Purge ---
params_to_purge = []
all_family_params = family_mgr.Parameters

print("Scanning {} parameters in family: {}".format(all_family_params.Size, doc.Title))

for param in all_family_params:
    if param.IsShared:
        if param.GUID is not None and param.GUID != Guid.Empty:
            guid_str = str(param.GUID).lower()
            param_name = param.Definition.Name
            if guid_str not in KEEP_GUIDS:
                params_to_purge.append(param)

# --- Perform Purge Action ---
if not params_to_purge:
    print("\nNo shared parameters found to purge (excluding the specified keep list).")
else:
    print("\nFound {} shared parameter(s) to purge:".format(len(params_to_purge)))
    for p in params_to_purge:
        print("- {} ({})".format(p.Definition.Name, p.GUID))

    # Confirmation before deleting using forms.alert
    confirm = forms.alert( # <--- CORRECTED FUNCTION CALL
        msg="Do you want to permanently delete these {} parameters?\n\nTHIS CAN NOT BE UNDONE.".format(len(params_to_purge)),
        title="Confirm Parameter Purge",
        yes=True,       # Show a "Yes" button
        no=True,        # Show a "No" button
        exitscript=False # IMPORTANT: Don't exit automatically, let us check the return value
    )
    # forms.alert returns True for Yes/OK/Retry, False for No/Cancel/Close

    if confirm: # True means user clicked Yes
        print("\nAttempting to remove parameters...")
        removed_count = 0
        failed_params = []

        with revit.Transaction("Purge Shared Parameters"):
            for param_to_remove in params_to_purge:
                try:
                    pname = param_to_remove.Definition.Name
                    family_mgr.RemoveParameter(param_to_remove)
                    removed_count += 1
                except Exception as remove_err:
                    # It's safer to get the name *before* trying to remove, in case the object becomes invalid
                    pname_fail = "Unknown"
                    try:
                        pname_fail = param_to_remove.Definition.Name
                    except:
                        pass # Keep Unknown if getting name fails post-error
                    print("ERROR: Failed to remove parameter '{}'. It might be in use (e.g., formulas, dimensions) or locked.".format(pname_fail))
                    print("   Error details: {}".format(remove_err))
                    failed_params.append(pname_fail)

        print("\n----- Purge Summary -----")
        print("Successfully removed: {} parameters.".format(removed_count))
        if failed_params:
            print("Failed to remove: {} parameters:".format(len(failed_params)))
            for fp in failed_params:
                print("- {}".format(fp))
        print("-------------------------")

    else: # False means user clicked No or closed the dialog
        print("\nPurge cancelled by user.")

