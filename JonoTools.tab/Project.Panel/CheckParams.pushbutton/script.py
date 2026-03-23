# -*- coding: utf-8 -*-
"""Checks selected categories of loadable families in the project
for the presence of specific parameters (Shared GUID or Built-in Name:
Depth, Width, Height) and lists families missing any of them."""

__title__ = "Check Family\nParams"
__author__ = "Jonathan Bourne"
# __context__ = "Project" # Optional: Ensures it runs only in a project

import sys
from pyrevit import revit, DB, script, forms
from pyrevit.framework import Guid

# --- Target Parameter Definitions ---
cfg = script.get_config()

DEFAULT_TEXT = (
    "PARAM\t11111111-2222-3333-4444-555555555555\tJONO_Default Width\tLENGTH\t\t1\t1\t\t1\t0\n"
    "PARAM\taaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee\tJONO_Default Height\tLENGTH\t\t1\t1\t\t1\t0\n"
    "PARAM\t99999999-8888-7777-6666-555555555555\tJONO_Default Depth\tLENGTH\t\t1\t1\t\t1\t0"
)

saved_text = getattr(cfg, 'check_params_raw', DEFAULT_TEXT)

REQUIRED_PARAMS_INFO = {}

# Parse Name and GUID from the saved tab-separated rows
for line in saved_text.splitlines():
    parts = line.split('\t')
    if len(parts) >= 3 and parts[0] == 'PARAM':
        guid_str = parts[1].strip()
        param_name = parts[2].strip()
        REQUIRED_PARAMS_INFO[param_name] = guid_str

# Extract sets for efficient lookup during the check
TARGET_GUIDS = {guid.lower() for guid in REQUIRED_PARAMS_INFO.values()}
TARGET_BIP_NAMES = set(REQUIRED_PARAMS_INFO.keys())
TARGET_PARAM_NAMES_STR = "({})".format(", ".join(TARGET_BIP_NAMES)) # For messages

# --- Get Project Document ---
doc = revit.doc
output = script.get_output()

# --- Runtime Check for Project Document ---
if not doc:
    print("ERROR: No active document found.")
    script.exit()

if doc.IsFamilyDocument:
    print("ERROR: This script must be run in a Project (.rvt file), not a Family.")
    script.exit()

# --- Collect Loadable Families and Their Categories ---
print("Collecting loadable families and categories from project: {}...".format(doc.Title))
all_families_collector = DB.FilteredElementCollector(doc)\
                           .OfClass(DB.Family)

loadable_families = []
available_categories_by_name = {}

for fam in all_families_collector:
    if fam.IsEditable and not fam.IsInPlace:
        loadable_families.append(fam)
        cat = fam.FamilyCategory
        if cat and cat.Name not in available_categories_by_name:
             available_categories_by_name[cat.Name] = cat

if not loadable_families:
    print("No loadable families found in the project.")
    script.exit()

if not available_categories_by_name:
    print("Could not determine categories for the found loadable families.")
    script.exit()

print("Found {} loadable families across {} categories.".format(
    len(loadable_families), len(available_categories_by_name))
    )

# --- Category Selection using SelectFromList ---
sorted_category_names = sorted(available_categories_by_name.keys())
selected_category_names = forms.SelectFromList.show(
    sorted_category_names,
    title="Select Categories to Check (Multi-Select)",
    button_name="Check Selected Categories",
    multiselect=True,
    width=500,
    height=600
)

if not selected_category_names:
    print("Category selection cancelled by user.")
    script.exit()

selected_category_ids = {
    available_categories_by_name[name].Id
    for name in selected_category_names
    if name in available_categories_by_name
}

if not selected_category_ids:
    print("No valid categories were selected or found.")
    script.exit()

families_to_check = [
    fam for fam in loadable_families
    if fam.FamilyCategory and fam.FamilyCategory.Id in selected_category_ids
]

if not families_to_check:
    print("No loadable families found matching the selected categories.")
    script.exit()

total_families_to_check = len(families_to_check)
print("\nChecking {} families in selected categories...".format(total_families_to_check))


# --- Check Families ---
# Use a dictionary to store missing parameters per family
# { family_name: [missing_param_name1, missing_param_name2,...] }
families_missing_details = {}
checked_count = 0
output.set_title("Checking Family Params {}/{}".format(checked_count, total_families_to_check))

for fam in families_to_check:
    checked_count += 1
    progress_message = "Checking {} ({}/{})".format(fam.Name, checked_count, total_families_to_check)
    print(progress_message)
    output.update_progress(checked_count, total_families_to_check)
    output.set_title(progress_message)

    family_doc = None
    try:
        family_doc = doc.EditFamily(fam)
        if family_doc:
            family_mgr = family_doc.FamilyManager
            # Track found parameters for *this* family
            found_guids = set()
            found_bip_names = set()

            # Check all parameters in the family document
            for param in family_mgr.Parameters:
                # Check if it's the target shared parameter by GUID
                if param.IsShared and param.GUID is not None and param.GUID != Guid.Empty:
                    guid_str = str(param.GUID).lower()
                    if guid_str in TARGET_GUIDS:
                        found_guids.add(guid_str)

                # Check if it's the target built-in parameter by Name
                try:
                    bip_enum = param.Definition.BuiltInParameter
                    if bip_enum != DB.BuiltInParameter.INVALID:
                        # For BIPs, rely on the Name comparison
                        param_name = param.Definition.Name
                        if param_name in TARGET_BIP_NAMES:
                            found_bip_names.add(param_name)
                except Exception:
                    # Some parameters might not expose BuiltInParameter correctly
                    pass

            # Determine which required parameters are missing
            missing_in_this_family = []
            for req_name, req_guid in REQUIRED_PARAMS_INFO.items():
                guid_found = req_guid.lower() in found_guids
                bip_name_found = req_name in found_bip_names

                # Parameter is considered missing if NEITHER the shared GUID NOR the BIP Name is found
                if not guid_found and not bip_name_found:
                    missing_in_this_family.append(req_name)

            # If any required parameters are missing, record the family and the missing list
            if missing_in_this_family:
                families_missing_details[fam.Name] = missing_in_this_family
                print("  -> MISSING: {}".format(", ".join(missing_in_this_family)))

            family_doc.Close(False)
        else:
            print("  -> SKIPPED: Could not open family '{}' for editing.".format(fam.Name))

    except Exception as e:
        print("  -> ERROR checking family '{}': {}".format(fam.Name, e))
        if family_doc and family_doc.IsValidObject:
            try:
                family_doc.Close(False)
            except: pass

# --- Report Results ---
output.self_destruct(60) # Keep output window open longer

if not families_missing_details:
    print("\n------------------------------------------")
    print("Check Complete: All {} checked families in the selected categories contain the required parameters {} (by GUID or Built-in Name).".format(
        total_families_to_check, TARGET_PARAM_NAMES_STR))
    print("------------------------------------------")
    forms.alert("All checked families contain the required parameters {}.".format(TARGET_PARAM_NAMES_STR),
                title="Check Complete")
else:
    print("\n---------------------------------------------------------------------")
    print("Check Complete: The following {} families from the selected categories are MISSING\n"
          "one or more required parameters {} (Shared GUID or Built-in Name):".format(len(families_missing_details), TARGET_PARAM_NAMES_STR))
    print("---------------------------------------------------------------------")
    # Sort families by name for readability
    sorted_missing_families = sorted(families_missing_details.keys())
    for i, fam_name in enumerate(sorted_missing_families):
        missing_list = ", ".join(families_missing_details[fam_name])
        print("{}. {}: Missing -> {}".format(i + 1, fam_name, missing_list))

output.set_title("Family Parameter Check Complete")
