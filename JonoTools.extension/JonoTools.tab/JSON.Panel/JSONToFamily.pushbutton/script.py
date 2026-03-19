# -*- coding: utf-8 -*-
"""
Parametric Revit Family Generator (Metric Edition)
--------------------------------------------------
Parses a JSON schema to generate parametric Revit Families (Furniture, Casework, etc.).

TODO / Potential Future Upgrades:
- Multiple Types: Add a 'types' array in JSON to batch-generate Family Types.
- Subcategories: Assign geometry to Object Styles (e.g., OST_Furniture -> 'Glass').
- Formulas: Parse 'formula' strings from JSON and apply via doc.FamilyManager.SetFormula().
- Reference Plane Types: Define IsReference properties (Strong, Weak, Origin) in JSON.
- Arrays: Implement NewLinearArray to pattern elements (e.g. repeated louvers/shelves).

KNOWN LIMITATIONS & BUGS TO WATCH OUT FOR:
- Profile Loops: Curves MUST be drawn continuously end-to-end. Self-intersecting profiles will crash the Extrusion creation.
- Blends: The bottom profile and top profile MUST have the exact same number of curve segments.
- Alignments: Complex curved geometry sometimes fails `ComputeReferences`, causing `NewAlignment` to fail silently. 
- Sweeps: Sweep profiles must be drawn in the 2D XY plane, the API internally handles rotating them onto the 3D path.
"""

__title__ = "JSON to\nFamily"
__author__ = "Jonathan Bourne"

import json
import clr
import os

from Autodesk.Revit.DB import *
from pyrevit import revit, forms, script

doc = revit.doc

# =========================================================================
# METRIC CONVERSION CONFIGURATION
# =========================================================================
IS_METRIC = True
SCL = (1.0 / 304.8) if IS_METRIC else 1.0


# -------------------------------------------------------------------------
# UI DIALOG FOR JSON INPUT
# -------------------------------------------------------------------------
# Define a custom WPF Window for pasting JSON
xaml_layout = """
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="Paste JSON Schema" Height="500" Width="600" 
        WindowStartupLocation="CenterScreen" ShowInTaskbar="False">
    <Grid Margin="10">
        <Grid.RowDefinitions>
            <RowDefinition Height="*"/>
            <RowDefinition Height="Auto"/>
        </Grid.RowDefinitions>
        
        <TextBox x:Name="json_tb" Grid.Row="0" 
                 AcceptsReturn="True" 
                 TextWrapping="Wrap" 
                 VerticalScrollBarVisibility="Auto" 
                 FontFamily="Consolas"
                 Text="Paste your JSON schema here..."/>
                 
        <Button x:Name="create_btn" Grid.Row="1" 
                Content="Create" Height="35" 
                Margin="0,10,0,0" 
                FontWeight="Bold"
                Click="create_clicked"/>
    </Grid>
</Window>
"""

class JsonInputDialog(forms.WPFWindow):
    def __init__(self):
        forms.WPFWindow.__init__(self, xaml_layout, literal_string=True)
        self.json_data = None

    def create_clicked(self, sender, args):
        # Save the text from the textbox and close the window
        self.json_data = self.json_tb.Text
        self.Close()


# -------------------------------------------------------------------------
# GEOMETRY HELPER FUNCTIONS
# -------------------------------------------------------------------------

def to_xyz(pt_list, scale=SCL):
    return XYZ(pt_list[0] * scale, pt_list[1] * scale, pt_list[2] * scale)

def to_vec(pt_list):
    return XYZ(pt_list[0], pt_list[1], pt_list[2])

def to_xyz_2d(pt_list, scale=SCL):
    return XYZ(pt_list[0] * scale, pt_list[1] * scale, 0.0)

def project_to_plane(pt, plane):
    vector = pt - plane.Origin
    distance = vector.DotProduct(plane.Normal)
    return pt - (plane.Normal * distance)

def create_curve_from_json(segment_data, sp_plane=None, is_2d_sweep=False, blend_offset=None):
    if is_2d_sweep:
        p1 = to_xyz_2d(segment_data["p1"])
        p2 = to_xyz_2d(segment_data["p2"])
    else:
        p1 = to_xyz(segment_data["p1"])
        p2 = to_xyz(segment_data["p2"])
        
        if sp_plane:
            p1 = project_to_plane(p1, sp_plane)
            p2 = project_to_plane(p2, sp_plane)
            
        if sp_plane and blend_offset is not None:
            offset_vec = sp_plane.Normal * blend_offset
            p1 += offset_vec
            p2 += offset_vec

    if segment_data.get("is_arc", False):
        if is_2d_sweep:
            p3 = to_xyz_2d(segment_data["p3"])
        else:
            p3 = to_xyz(segment_data["p3"])
            if sp_plane:
                p3 = project_to_plane(p3, sp_plane)
            if sp_plane and blend_offset is not None:
                p3 += sp_plane.Normal * blend_offset
        return Arc.Create(p1, p2, p3)
    else:
        return Line.CreateBound(p1, p2)


# -------------------------------------------------------------------------
# MAIN GENERATION ENGINE
# -------------------------------------------------------------------------

def generate_family_from_json(schema):
    with revit.Transaction("Generate Master Parametric Family"):
        
        # --- PREPARATION: FIND REQUIRED VIEWS ---
        plan_view, elev_view = None, None
        for v in FilteredElementCollector(doc).OfClass(View):
            if v.IsTemplate: continue
            if v.ViewType == ViewType.FloorPlan and not plan_view:
                plan_view = v
            elif v.ViewType == ViewType.Elevation and not elev_view:
                if abs(v.ViewDirection.Y) > 0.99:
                    elev_view = v
                
        if not plan_view or not elev_view:
            forms.alert("Family template is missing a Plan or Front/Back Elevation view.", exitscript=True)

        if doc.FamilyManager.CurrentType is None:
            doc.FamilyManager.NewType("Standard")

        # --- STEP 1: CREATE PARAMETERS ---
        param_dict = {}
        for p in schema.get("parameters", []):
            p_type = p.get("type", "Length")
            try:
                if p_type == "Material":
                    family_param = doc.FamilyManager.AddParameter(p["name"], GroupTypeId.Materials, SpecTypeId.Reference.Material, p["is_instance"])
                elif p_type == "YesNo":
                    family_param = doc.FamilyManager.AddParameter(p["name"], GroupTypeId.Visibility, SpecTypeId.Boolean.YesNo, p["is_instance"])
                else:
                    family_param = doc.FamilyManager.AddParameter(p["name"], GroupTypeId.Geometry, SpecTypeId.Length, p["is_instance"])
            except AttributeError:
                if p_type == "Material":
                    family_param = doc.FamilyManager.AddParameter(p["name"], BuiltInParameterGroup.PG_MATERIALS, ParameterType.Material, p["is_instance"])
                elif p_type == "YesNo":
                    family_param = doc.FamilyManager.AddParameter(p["name"], BuiltInParameterGroup.PG_VISIBILITY, ParameterType.YesNo, p["is_instance"])
                else:
                    family_param = doc.FamilyManager.AddParameter(p["name"], BuiltInParameterGroup.PG_GEOMETRY, ParameterType.Length, p["is_instance"])
            
            if p.get("value") is not None:
                val = p["value"] * SCL if p_type == "Length" else p["value"]
                doc.FamilyManager.Set(family_param, val)
                
            param_dict[p["name"]] = family_param


        # --- STEP 2: CREATE REFERENCE PLANES ---
        rp_dict = {}
        for rp_data in schema.get("reference_planes", []):
            view = plan_view if rp_data["view"] == "Plan" else elev_view
            cut_vec = to_vec(rp_data["normal"]) if "normal" in rp_data else (XYZ.BasisZ if rp_data["view"] == "Plan" else XYZ.BasisY)
            
            rp = doc.FamilyCreate.NewReferencePlane(to_xyz(rp_data["p1"]), to_xyz(rp_data["p2"]), cut_vec, view)
            rp.Name = rp_data["name"]
            rp_dict[rp_data["name"]] = rp

        doc.Regenerate()

        # --- STEP 3: CREATE DIMENSIONS ---
        for dim_data in schema.get("dimensions", []):
            view = plan_view if dim_data["view"] == "Plan" else elev_view
            ref_array = ReferenceArray()
            for plane_name in dim_data["planes"]:
                ref_array.Append(rp_dict[plane_name].GetReference())
                
            dim_line = Line.CreateBound(to_xyz(dim_data["line_dir"][0]), to_xyz(dim_data["line_dir"][1]))
            try:
                new_dim = doc.FamilyCreate.NewDimension(view, dim_line, ref_array)
                new_dim.FamilyLabel = param_dict[dim_data["parameter"]] 
            except Exception as e:
                print("Could not dimension parameter '{}': {}".format(dim_data["parameter"], e))


        # --- STEP 4: CREATE GEOMETRY ---
        created_geometries = {}
        solid_forms, void_forms = [], []

        for geom_data in schema.get("geometry", []):
            created_geom = None
            is_solid = geom_data.get("is_solid", True)
            
            if "sketch_plane_x" in geom_data:
                base_plane = Plane.CreateByNormalAndOrigin(XYZ.BasisX, XYZ(geom_data["sketch_plane_x"] * SCL, 0, 0))
            elif "sketch_plane_y" in geom_data:
                base_plane = Plane.CreateByNormalAndOrigin(XYZ.BasisY, XYZ(0, geom_data["sketch_plane_y"] * SCL, 0))
            else:
                z_height = geom_data.get("sketch_plane_z", 0.0) * SCL
                base_plane = Plane.CreateByNormalAndOrigin(XYZ.BasisZ, XYZ(0, 0, z_height))
                
            sketch_plane = SketchPlane.Create(doc, base_plane)
            sp_plane = sketch_plane.GetPlane()

            # --- EXTRUSION ---
            if geom_data["type"] == "Extrusion":
                profile = CurveArrArray()
                loop = CurveArray()
                for segment in geom_data.get("profile", []):
                    loop.Append(create_curve_from_json(segment, sp_plane=sp_plane))
                profile.Append(loop)
                created_geom = doc.FamilyCreate.NewExtrusion(is_solid, profile, sketch_plane, geom_data["extrusion_end"] * SCL)
                created_geom.StartOffset = geom_data.get("extrusion_start", 0.0) * SCL
            
            # --- SWEEP ---
            elif geom_data["type"] == "Sweep":
                path = CurveArray()
                for segment in geom_data.get("path", []):
                    path.Append(create_curve_from_json(segment, sp_plane=sp_plane))
                
                profile_loop = CurveArray()
                for segment in geom_data.get("profile_2d", []):
                    profile_loop.Append(create_curve_from_json(segment, is_2d_sweep=True))
                
                profile_arr = CurveArrArray()
                profile_arr.Append(profile_loop)
                sweep_profile = doc.Application.Create.NewCurveLoopsProfile(profile_arr)
                created_geom = doc.FamilyCreate.NewSweep(is_solid, path, sketch_plane, sweep_profile, 0, ProfilePlaneLocation.Start)
            
            # --- REVOLVE ---
            elif geom_data["type"] == "Revolve":
                profile = CurveArrArray()
                loop = CurveArray()
                for segment in geom_data.get("profile", []):
                    loop.Append(create_curve_from_json(segment, sp_plane=sp_plane))
                profile.Append(loop)
                
                axis_p1 = project_to_plane(to_xyz(geom_data["axis"]["p1"]), sp_plane)
                axis_p2 = project_to_plane(to_xyz(geom_data["axis"]["p2"]), sp_plane)
                axis_line = Line.CreateBound(axis_p1, axis_p2)
                created_geom = doc.FamilyCreate.NewRevolution(is_solid, profile, sketch_plane, axis_line, geom_data.get("start_angle", 0.0), geom_data.get("end_angle", 6.283185307))

            # --- BLEND ---
            elif geom_data["type"] == "Blend":
                bottom_profile = CurveArray()
                for segment in geom_data.get("bottom_profile", []):
                    bottom_profile.Append(create_curve_from_json(segment, sp_plane=sp_plane))
                
                top_profile = CurveArray()
                second_end_offset = geom_data.get("second_end", 1.0) * SCL
                for segment in geom_data.get("top_profile", []):
                    top_profile.Append(create_curve_from_json(segment, sp_plane=sp_plane, blend_offset=second_end_offset))

                created_geom = doc.FamilyCreate.NewBlend(is_solid, top_profile, bottom_profile, sketch_plane)
                
                if created_geom:
                    try:
                        created_geom.BottomOffset = geom_data.get("first_end", 0.0) * SCL
                        created_geom.TopOffset = second_end_offset
                    except Exception:
                        pass

            # --- STEP 4.5: BIND MATERIALS & VISIBILITY ---
            if created_geom:
                if "id" in geom_data:
                    created_geometries[geom_data["id"]] = created_geom
                
                if is_solid:
                    solid_forms.append(created_geom)
                else:
                    void_forms.append(created_geom)
                    
                mat_param_name = geom_data.get("material_param")
                if mat_param_name and mat_param_name in param_dict:
                    geom_mat_param = created_geom.get_Parameter(BuiltInParameter.MATERIAL_ID_PARAM)
                    if geom_mat_param:
                        doc.FamilyManager.AssociateElementParameterToFamilyParameter(geom_mat_param, param_dict[mat_param_name])
                
                vis_param_name = geom_data.get("visible_param")
                if vis_param_name and vis_param_name in param_dict:
                    geom_vis_param = created_geom.get_Parameter(BuiltInParameter.IS_VISIBLE_PARAM)
                    if geom_vis_param:
                        doc.FamilyManager.AssociateElementParameterToFamilyParameter(geom_vis_param, param_dict[vis_param_name])

            doc.Regenerate()


            # --- STEP 5: LOCK FACES TO REFERENCE PLANES ---
            if "locks" in geom_data and created_geom:
                geom_opt = Options()
                geom_opt.ComputeReferences = True 
                
                geometry_element = created_geom.get_Geometry(geom_opt)
                for geom_obj in geometry_element:
                    if isinstance(geom_obj, Solid):
                        for face in geom_obj.Faces:
                            if isinstance(face, PlanarFace):
                                normal = face.FaceNormal
                                for lock in geom_data["locks"]:
                                    req_norm = to_vec(lock["face_normal"]) 
                                    if normal.DotProduct(req_norm) > 0.99:
                                        target_rp = rp_dict[lock["plane"]]
                                        align_view = plan_view if abs(normal.Z) < 0.01 else elev_view
                                        try:
                                            alignment = doc.FamilyCreate.NewAlignment(align_view, target_rp.GetReference(), face.Reference)
                                            if alignment:
                                                alignment.IsLocked = True
                                        except Exception as e:
                                            pass


        # =========================================================================
        # --- STEP 6: EXPLICIT SEQUENTIAL VOID CUTTING ---
        # =========================================================================
        doc.Regenerate()
        
        # 1. Build a map of Solid IDs -> List of Void Elements that need to cut it
        cuts_map = {}
        for geom_data in schema.get("geometry", []):
            if not geom_data.get("is_solid", True) and "cuts" in geom_data and "id" in geom_data:
                void_elem = created_geometries.get(geom_data["id"])
                if void_elem:
                    for solid_id in geom_data["cuts"]:
                        if solid_id not in cuts_map:
                            cuts_map[solid_id] = []
                        cuts_map[solid_id].append(void_elem)
                        
        # 2. Execute cuts sequentially to preserve the "GeomCombination" chain
        for solid_id, void_list in cuts_map.items():
            current_solid_target = created_geometries.get(solid_id)
            if not current_solid_target: continue
            
            for void_elem in void_list:
                combine_array = CombinableElementArray()
                combine_array.Append(current_solid_target)
                combine_array.Append(void_elem)
                try:
                    # CombineElements returns a GeomCombination object.
                    # We MUST capture this and make it the target for the next void in the loop!
                    new_combination = doc.CombineElements(combine_array)
                    if new_combination:
                        current_solid_target = new_combination
                except Exception as e:
                    print("Failed to cut '{}' with a void. Error: {}".format(solid_id, e))


# -------------------------------------------------------------------------
# EXECUTION
# -------------------------------------------------------------------------
if __name__ == "__main__":
    if not doc.IsFamilyDocument:
        forms.alert("This script must be run inside a Family Document.", exitscript=True)

    # 1. Show the WPF Dialog to get the JSON string
    dialog = JsonInputDialog()
    dialog.show_dialog() # Halts script execution until the window is closed

    # 2. Check if user clicked Create and captured data
    if dialog.json_data and dialog.json_data.strip() and dialog.json_data != "Paste your JSON schema here...":
        try:
            # Parse the JSON string
            parsed_schema = json.loads(dialog.json_data)
            
            # Execute family generation
            generate_family_from_json(parsed_schema)
            forms.alert("Metric Parametric Family generated successfully!", title="Success")
            
        except ValueError as e: # Catch JSON parsing errors gracefully
            forms.alert("Invalid JSON format detected:\n\n{}".format(e), title="JSON Error", exitscript=True)
        except Exception as e: # Catch other API generation errors
            forms.alert("Error generating family:\n\n{}".format(e), title="Generation Error", exitscript=True)
    else:
        # Window was closed or nothing was entered
        script.exit()
