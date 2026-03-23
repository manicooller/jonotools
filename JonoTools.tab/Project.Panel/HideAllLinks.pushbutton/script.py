# -*- coding: utf-8 -*-
"""Temporarily hides all Revit Link instances in the active view."""

__title__ = "Hide Links"
__author__ = "Jonathan Bourne"

import sys
from pyrevit import revit, DB, UI, script
# No framework List needed
# No clr needed

# Get the current document and active view
doc = revit.doc
uidoc = revit.uidoc # Need UIDocument for RefreshActiveView
if not uidoc:
    print("ERROR: Could not get UIDocument.")
    script.exit()

active_view = uidoc.ActiveView

# --- Pre-checks ---
if not doc:
    print("ERROR: No active document found.")
    script.exit()

if not active_view:
    print("ERROR: No active view found. Please open a view.")
    script.exit()

# --- Main Logic ---
try:
    # Find all Revit Link Instances visible in the active view
    link_collector = DB.FilteredElementCollector(doc, active_view.Id)\
                       .OfClass(DB.RevitLinkInstance)\
                       .WhereElementIsNotElementType()

    # Get the collection of ElementIds directly from the collector
    link_ids_to_hide = link_collector.ToElementIds() # This returns ICollection<ElementId>

    # --- Perform Action ---
    if link_ids_to_hide.Count > 0:
        # Wrap the temporary hide call in a transaction as required by the API
        # Even though it's temporary, the API demands it here.
        with revit.Transaction("Apply Temporary Hide to Links"): # <--- ADDED TRANSACTION
            try:
                # Directly call HideElementsTemporary.
                active_view.HideElementsTemporary(link_ids_to_hide)

                # Note: Print statement is outside the 'try' within the transaction
                #       to avoid potential issues if printing itself fails.
                #       The action itself will commit if HideElementsTemporary succeeds.

            except Exception as hide_err:
                 # Catch potential errors during the temporary hide operation.
                 print("ERROR: Failed to temporarily hide links within transaction.")
                 err_msg = str(hide_err).lower()
                 if "temporary view modes" in err_msg or "hide/isolate" in err_msg or "not applicable" in err_msg:
                     print("Reason: The active view type ({}) might not support Temporary Hide/Isolate, or another issue occurred.".format(active_view.ViewType))
                 else:
                    print("Details: {}".format(hide_err))
                    # import traceback
                    # print(traceback.format_exc())
                 # If an error occurs here, the transaction will automatically roll back.
                 script.exit() # Exit after error within transaction try block

        # This print happens *after* the transaction has successfully committed
        print("Successfully applied temporary hide to {} Revit link instance(s) in view: '{}'".format(
            link_ids_to_hide.Count,
            active_view.Name)
        )
        # Refresh the view graphics
        uidoc.RefreshActiveView()

    else:
        print("No visible Revit links found to temporarily hide in the active view: '{}'".format(active_view.Name))

except Exception as e:
    # General error handling for collector or other issues outside the main action
    print("An unexpected error occurred (e.g., during link collection):")
    print(e)
    # import traceback
    # print(traceback.format_exc())

