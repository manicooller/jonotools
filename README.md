# JonoTools for pyRevit

**JonoTools** is a custom [pyRevit](https://github.com/eirannejad/pyRevit) extension designed to automate repetitive workflows in Autodesk Revit, with a heavy focus on Family creation, auditing, and batch-cleaning.

⚠️ **DISCLAIMER & WARNING** ⚠️
> **THIS IS A WORK IN PROGRESS.** 
> Use these tools at your own risk. I am not responsible for any data loss, model corruption, or issues that arise from the use of this extension. 
> 
> **CRITICAL WARNING:** Several scripts in this repository are highly destructive and are specifically designed to **permanently delete project/family information, parameters, and materials.** Always test these scripts on detached models or ensure you have a recent backup before running them in a production environment.

---

## 🛠️ Installation

To install this extension into your pyRevit environment:

1. Open your command prompt (CMD) or terminal.
2. Use the pyRevit CLI to add the repository as a custom extension by running the following command:
   ```bash
   pyrevit extend ui JonoTools https://github.com/manicooller/jonotools.git --branch=main
   ```
3. Alternatively, you can clone this repository directly into your custom pyRevit extensions folder (configurable in pyRevit settings).
4. Reload pyRevit (`Ctrl + F5` or use the Reload button in the pyRevit ribbon).

---

## 🧰 Included Tools

The tools are organized into three main panels on the pyRevit ribbon: **Families**, **JSON**, and **Project**. 

*💡 **Pro-Tip:** Tools marked with a black dot (`•`) in the Revit ribbon indicate that they have a settings menu. Hold `Shift` and click the button to configure them!*

### 📁 Families Panel
Tools designed to clean and manage Revit Family files.

*   **Purge Shared Params (`Purge Shared Params •`)**
    *   **Context:** Family Editor
    *   **Description:** Scans the active family document and permanently purges all Shared Parameters *except* for a defined whitelist of essential GUIDs. Great for cleaning up vendor families or enforcing company standards.
    *   ⚙️ **Configurable (`Shift + Click`):** Open the settings menu to define your whitelist. You can copy and paste the raw text directly from your company's Revit Shared Parameters (`.txt`) file. The tool automatically ignores all headers, groups, and comments, safely extracting only the valid GUIDs.
    *   *Warning: This action cannot be undone and drops parameter data.*

*   **Clear Identity Data (`Clear Identity Data`)**
    *   **Context:** Family Editor
    *   **Description:** Wipes the formulas and values from standard built-in Identity Data parameters (e.g., Manufacturer, Description, Cost, URL, Assembly Code) in the active family. 
    *   *Warning: Instantly deletes proprietary or unwanted identity data values.*

*   **Purge Non-Param Materials (`Purge Non-Param Materials`)**
    *   **Context:** Project Environment
    *   **Description:** A powerful batch tool that searches the active project for loadable families of selected categories. It opens each family in the background, checks which materials are *not* mapped to a family parameter, deletes those unused materials, and reloads the family back into the project. 
    *   *Warning: Modifies families currently loaded in your project.*

### 📁 JSON Panel
Tools for programmatic family generation.

*   **JSON to Family (`JSON to Family`)**
    *   **Context:** Family Editor
    *   **Description:** A parametric family generator. When clicked, a resizable text window appears allowing you to paste a JSON schema. Once you click "Create", the script reads the JSON to automatically build Reference Planes, Dimensions, Parameters, and Geometry (Extrusions, Sweeps, Revolves, Blends, and Voids). 
    *   *Note: Includes a constraint engine that automatically locks geometry to reference planes and handles sequential void cutting.*
    *   🤖 **AI Generation Prompt:** Included in this repo is a [System Prompt for LLMs](JonoTools.extension/JonoTools.tab/JSON.Panel/JSONToFamily.pushbutton/SYSTEM%20PROMPT.md). You can supply this prompt to AI models (like ChatGPT or Claude) along with images, sketches, or text descriptions. The AI will act as a "Revit Family JSON Schema Generator" and output the exact JSON code needed for this tool to build your family.

### 📁 Project Panel
Tools for auditing and managing the project environment.

*   **Check Family Params (`Check Family Params •`)**
    *   **Context:** Project Environment
    *   **Description:** Audits loadable families within your project. You select the categories to check, and the script verifies if those families contain specific required parameters by checking both Shared Parameter GUIDs and Built-In names. It outputs a report of any families missing the required data.
    *   ⚙️ **Configurable (`Shift + Click`):** Open the settings menu to define your required parameters. Just like the Purge tool, you can paste the raw contents of your Shared Parameters (`.txt`) file. The tool parses the exact Names and GUIDs required for the audit.

*   **Hide Links (`Hide Links`)**
    *   **Context:** Project Environment
    *   **Description:** A quick visibility utility that instantly applies a "Temporary Hide/Isolate" to all Revit Link instances in the active view. Perfect for quickly decluttering a view to work on the native model.

---

## 👨‍💻 Author
**Jonathan Bourne**

*Developed for use with Autodesk Revit and the pyRevit framework.*