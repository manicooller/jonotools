# -*- coding: utf-8 -*-
"""Attempts to purge materials NOT used as parameter values from selected
categories of loadable families within the current project.
Includes detailed logging for deletion step.
!!! WARNING: Modifies families loaded in the project. BACKUP FIRST. !!!"""

__title__ = "Purge Non-Param\nMaterials" # Updated Title
__author__ = "Jonathan Bourne"
# __context__ = "Project"

import sys
from pyrevit import revit, DB, script, forms
from pyrevit.framework import List

output = script.get_output()

# --- Keywords often found in non-purgeable material names ---
SKIP_MATERIAL_NAME_KEYWORDS = {"<", ">"} # Keep this minimal

# --- Family Load Options Handler ---
# ... (remains same) ...
class OverwriteFamilyLoadOptions(DB.IFamilyLoadOptions):
    def OnFamilyFound(self, familyInUse, overwriteParameterValues):
        overwriteParameterValues = True; return True
    def OnSharedFamilyFound(self, sharedFamily, familyInUse, source, overwriteParameterValues):
        overwriteParameterValues = True; return True

# --- Get Project Document ---
doc = revit.doc

# --- Runtime Check ---
# ... (remains same) ...
if not doc: print("ERROR: No active document found."); script.exit()
if doc.IsFamilyDocument: print("ERROR: This script must be run in a Project (.rvt file), not a Family."); script.exit()

# --- Collect Families & Categories ---
# ... (remains same) ...
print("Collecting loadable families and categories from project: {}...".format(doc.Title))
all_families_collector = DB.FilteredElementCollector(doc).OfClass(DB.Family)
loadable_families = []
available_categories_by_name = {}
for fam in all_families_collector:
    if fam.IsEditable and not fam.IsInPlace and fam.FamilyCategory:
        loadable_families.append(fam)
        cat = fam.FamilyCategory
        if cat and cat.Name not in available_categories_by_name:
             available_categories_by_name[cat.Name] = cat
if not loadable_families: print("No editable loadable families found in the project."); script.exit()
if not available_categories_by_name: print("Could not determine categories for the found loadable families."); script.exit()
print("Found {} editable loadable families across {} categories.".format(len(loadable_families), len(available_categories_by_name)))

# --- Category Selection ---
# ... (remains same) ...
sorted_category_names = sorted(available_categories_by_name.keys())
selected_category_names = forms.SelectFromList.show(
    sorted_category_names, title="Select Categories to Purge Materials From",
    button_name="Purge Materials in Selected", multiselect=True, width=500, height=600
)
if not selected_category_names: print("Category selection cancelled by user."); script.exit()
selected_category_ids = { available_categories_by_name[name].Id for name in selected_category_names if name in available_categories_by_name }
if not selected_category_ids: print("No valid categories were selected or found."); script.exit()
families_to_process = [ fam for fam in loadable_families if fam.FamilyCategory and fam.FamilyCategory.Id in selected_category_ids ]
if not families_to_process: print("No loadable families found matching the selected categories."); script.exit()
total_families_to_process = len(families_to_process)
print("\nSelected {} families in selected categories for processing...".format(total_families_to_process))

# --- !!! OVERALL CONFIRMATION !!! ---
# ... (remains same) ...
confirm_all = forms.alert(
    msg="WARNING: [...] Do you want to proceed?".format(total_families_to_process),
    title="MAJOR WARNING - Confirm Family Material Purge",
    yes=True, no=True, exitscript=False
)
if not confirm_all: print("\nOperation cancelled by user."); script.exit()

# --- Process Families ---
processed_count = 0
modified_count = 0
failed_families = {}
output.set_title("Purging Family Materials {}/{}".format(processed_count, total_families_to_process))
family_load_options = OverwriteFamilyLoadOptions()

for fam in families_to_process:
    processed_count += 1
    progress_message = "Processing {} ({}/{})".format(fam.Name, processed_count, total_families_to_process)
    print(progress_message)
    output.update_progress(processed_count, total_families_to_process)
    output.set_title(progress_message)

    family_doc = None
    family_opened_successfully = False
    try:
        family_doc = doc.EditFamily(fam)
        if not (family_doc and family_doc.IsValidObject):
            print("  -> SKIPPED: Could not open family '{}' for editing.".format(fam.Name))
            failed_families[fam.Name] = "Could not open for editing"
            continue

        family_opened_successfully = True
        family_mgr = family_doc.FamilyManager
        family_modified = False
        materials_purged_in_this_family = 0

        # Step 1: Find Material IDs used in Parameters
        material_ids_used_in_params = set()
        # ... (parameter scanning logic remains same) ...
        try:
            for param in family_mgr.Parameters:
                 if param.StorageType == DB.StorageType.ElementId:
                     for fam_type in family_mgr.Types:
                         if fam_type.HasValue(param):
                             value_id = fam_type.AsElementId(param)
                             if value_id and value_id.IntegerValue > 0:
                                 element = family_doc.GetElement(value_id)
                                 if element and element.Category and element.Category.Id == DB.BuiltInCategory.OST_Materials:
                                     material_ids_used_in_params.add(value_id)
        except Exception as step1_err: print("    -> WARNING: Error scanning parameters: {}".format(step1_err))


        # Step 2 & 3: Find All Materials and Identify Purge Targets
        materials_to_purge = []
        skipped_material_names = []
        # ... (material collection logic remains same, using updated SKIP_KEYWORDS) ...
        try:
            all_materials_collector=DB.FilteredElementCollector(family_doc).OfCategory(DB.BuiltInCategory.OST_Materials).WhereElementIsNotElementType()
            all_materials = all_materials_collector.ToElements()
            for mat in all_materials:
                if mat.Id not in material_ids_used_in_params:
                    mat_name_lower = mat.Name.lower()
                    skip = False
                    for keyword in SKIP_MATERIAL_NAME_KEYWORDS:
                        if keyword in mat_name_lower:
                            skip = True; skipped_material_names.append(mat.Name); break
                    if not skip: materials_to_purge.append(mat)
            # if skipped_material_names: print("      Skipped {} potential system materials by name.".format(len(skipped_material_names)))
        except Exception as step23_err: print("    -> WARNING: Error collecting/identifying materials: {}".format(step23_err))


        # Step 4: Perform Purge Action with Detailed Logging
        if materials_to_purge:
            num_attempted = len(materials_to_purge) # Store initial count
            print("      Attempting to purge {} materials...".format(num_attempted))
            removed_count_this_fam = 0
            failed_mats_this_fam = {} # Store Name: Reason
            t = DB.Transaction(family_doc, "Purge Non-Param Materials")
            try:
                t.Start()
                material_ids_to_delete_pylist = [m.Id for m in materials_to_purge]
                if material_ids_to_delete_pylist:
                    net_ids_to_delete = List[DB.ElementId](material_ids_to_delete_pylist)
                    deleted_ids_result = family_doc.Delete(net_ids_to_delete)
                    removed_count_this_fam = deleted_ids_result.Count
                    materials_purged_in_this_family = removed_count_this_fam

                    # --- Detailed Failure Check ---
                    if removed_count_this_fam < net_ids_to_delete.Count:
                         actually_deleted_ids = set(deleted_ids_result)
                         for m in materials_to_purge:
                              if m.Id not in actually_deleted_ids:
                                   # Try to get a specific reason if possible, otherwise default
                                   reason = "Not deleted (likely in use or system)"
                                   # Check if it's likely analytical
                                   if "analytical" in m.Name.lower():
                                        reason = "Not deleted (likely system analytical)"
                                   failed_mats_this_fam[m.Name] = reason
                    # --- End Detailed Failure Check ---

                if materials_purged_in_this_family > 0: family_modified = True

                # Updated Reporting inside Transaction Try
                print("        Attempted: {}, Succeeded: {}, Failed/Kept: {}".format(
                      num_attempted, materials_purged_in_this_family, len(failed_mats_this_fam)))
                if failed_mats_this_fam:
                     # List specific failures/kept items
                     kept_items_str = ["'{}' ({})".format(name, reason) for name, reason in failed_mats_this_fam.items()]
                     print("        Failed/Kept Items: {}".format("; ".join(kept_items_str)))

                t.Commit()

            except Exception as step4_err:
                 print("    -> WARNING: Error during material deletion transaction: {}".format(step4_err))
                 if t.HasStarted(): t.RollBack()
                 family_modified = False
        else:
            print("      No non-parameter, non-system materials (by name) found to purge.")

        # Step 5: Load Family back into Project if modified
        # ... (remains same) ...
        if family_modified:
             try:
                 print("      Reloading modified family into project...")
                 reloaded_fam = family_doc.LoadFamily(doc, family_load_options)
                 if reloaded_fam: modified_count += 1; print("        Successfully reloaded.")
                 else: print("    -> ERROR Reloading family '{}': LoadFamily returned None.".format(fam.Name)); failed_families[fam.Name] = "Reload failed (LoadFamily returned None)"
             except Exception as load_err: print("    -> ERROR Reloading family '{}': {}".format(fam.Name, load_err)); failed_families[fam.Name] = "Reload failed: {}".format(load_err)

    except Exception as outer_err:
        # ... (remains same) ...
        error_msg = "Outer error: {}".format(outer_err)
        print("  -> ERROR processing family '{}': {}".format(fam.Name, error_msg))
        if fam.Name not in failed_families: failed_families[fam.Name] = error_msg

    finally:
        # Step 6: Ensure Family Doc is Closed
        # ... (remains same) ...
        if family_opened_successfully and family_doc and family_doc.IsValidObject:
            try: family_doc.Close(False)
            except Exception as finally_close_err: print("    -> WARNING: Error closing family doc in finally block: {}".format(finally_close_err))

# --- Final Report ---
# ... (remains same) ...
output.self_destruct(120)
print("\n----- FINAL SUMMARY -----")
print("Processed: {} families.".format(processed_count))
print("Modified and Reloaded: {} families.".format(modified_count))
if failed_families:
    print("Failed/Skipped: {} families:".format(len(failed_families)))
    for fam_name, reason in failed_families.items(): print("- {}: {}".format(fam_name, reason))
print("-------------------------")
print("\nNOTE: Materials used directly on geometry or required by system "
      "were likely NOT deleted even if listed as 'Attempted'. Use Revit's 'Purge Unused' tool "
      "within families for a full purge.")
forms.alert(
    "Purge attempt complete.\n\nProcessed: {}\nModified: {}\nFailed/Skipped: {}\n\n"
    "See log for details (check 'Failed/Kept Items' lines).\n"
    "Remember to use Revit's 'Purge Unused' for a full cleanup."
    .format(processed_count, modified_count, len(failed_families)),
    title="Purge Complete")
output.set_title("Family Material Purge Complete")
