import win32com.client
import os
import re

def sanitize_sheet_name(name, flash_code):
    """Sanitizes a sheet name for Excel and makes it unique with flash_code."""
    base_name = str(name) if name else "Report"
    # Replace forbidden characters: \ / ? * [ ] :
    # Excel sheet names cannot contain: \ / ? * [ ]
    # Also, ':' is problematic for file systems if sheet name is used in filenames later.
    # Max length is 31 characters.
    sanitized_base_name = re.sub(r'[\\/\?\*\[\]:]', '_', base_name)

    # Construct name with flash_code, ensuring it's not too long
    suffix = f"_{flash_code}"
    max_base_len = 31 - len(suffix)

    if len(sanitized_base_name) > max_base_len:
        sanitized_base_name = sanitized_base_name[:max_base_len]

    final_name = f"{sanitized_base_name}{suffix}"
    return final_name[:31] # Ensure final length is max 31

def automate_revenue_report(source_workbook_path, division_input, macro_names_to_run):
    """
    Automates the Excel report generation process.

    Args:
        source_workbook_path (str): Full path to the source Excel workbook.
        division_input (str): The division to process (e.g., "APAC").
        macro_names_to_run (list): A list of macro names (strings) to run.
                                   Example: ["Macro1", "Sheet1.ProcessData"]
                                   Macros should be in the source workbook.
    """
    excel_app = None
    source_wb = None
    new_wb = None

    try:
        # --- 0. Basic Path Check ---
        if not os.path.exists(source_workbook_path):
            print(f"Error: Source workbook not found at {source_workbook_path}")
            return

        # --- 1. Initialization ---
        print("Initializing Excel application...")
        excel_app = win32com.client.Dispatch("Excel.Application")
        excel_app.Visible = False  # Run in background; set to True for debugging
        excel_app.DisplayAlerts = False # Suppress Excel's own alerts

        print(f"Opening source workbook: {source_workbook_path}")
        source_wb = excel_app.Workbooks.Open(source_workbook_path)

        print("Creating new workbook 'sample.xlsx'...")
        new_wb = excel_app.Workbooks.Add()
        # Define the path for the new workbook
        output_folder = os.path.dirname(source_workbook_path) if os.path.dirname(source_workbook_path) else os.getcwd()
        new_workbook_save_path = os.path.join(output_folder, "sample.xlsx")


        # --- 2. Access Sheets in Source Workbook ---
        try:
            source_template_sheet = source_wb.Sheets("Template")
            source_ref_sheet = source_wb.Sheets("Ref")
        except Exception as e:
            print(f"Error accessing 'Template' or 'Ref' sheet in source workbook: {e}")
            if source_wb:
                source_wb.Close(SaveChanges=False)
            if new_wb: # Close new_wb if it was created but not saved
                new_wb.Close(SaveChanges=False)
            excel_app.Quit()
            return

        # --- 3. Retrieve Flash Codes for the Division (Lookup Method) ---
        print(f"Retrieving flash codes for division: {division_input} from 'Ref' sheet...")
        flash_codes = []
        # Assuming 'Ref' sheet has headers in row 1. Data starts from row 2.
        # Column A (index 1) for Division, B (2), C (3), D (4) for Flash Codes.
        # UsedRange can be unreliable if sheet has stray data. Iterate a reasonable range or find last row.
        # For simplicity, let's iterate up to a presumed max number of rows or use UsedRange carefully.
        # A more robust way is to find the last used row in column A.
        last_row_ref = source_ref_sheet.Cells(source_ref_sheet.Rows.Count, "A").End(-4162).Row # -4162 is xlUp

        found_division = False
        for r in range(1, last_row_ref + 1): # Iterate from row 1 (assuming headers might be there)
            division_cell_value = source_ref_sheet.Cells(r, 1).Value
            if division_cell_value and str(division_cell_value).strip() == division_input:
                print(f"Found division '{division_input}' in 'Ref' sheet at row {r}.")
                # Flash codes are in columns B, C, D (indices 2, 3, 4)
                fc1 = source_ref_sheet.Cells(r, 2).Value
                fc2 = source_ref_sheet.Cells(r, 3).Value
                fc3 = source_ref_sheet.Cells(r, 4).Value

                if fc1 and str(fc1).strip(): flash_codes.append(str(fc1).strip())
                if fc2 and str(fc2).strip(): flash_codes.append(str(fc2).strip())
                if fc3 and str(fc3).strip(): flash_codes.append(str(fc3).strip())
                found_division = True
                break # Stop searching once division is found

        if not found_division:
            print(f"Error: Division '{division_input}' not found in 'Ref' sheet (Column A).")
            # Clean up before exiting
            if source_wb: source_wb.Close(SaveChanges=False)
            if new_wb: new_wb.Close(SaveChanges=False) # new_wb is empty, no need to save
            excel_app.Quit()
            return

        if not flash_codes:
            print(f"No flash codes found for division '{division_input}'.")
            # Clean up before exiting
            if source_wb: source_wb.Close(SaveChanges=False)
            if new_wb: new_wb.Close(SaveChanges=False)
            excel_app.Quit()
            return

        print(f"Found flash codes: {flash_codes}")

        # --- 4. Process Each Flash Code ---
        for current_flash_code in flash_codes:
            print(f"\nProcessing flash code: {current_flash_code}...")

            # a. Update 'Template' Sheet (in source_workbook)
            print(f"  Updating 'Template' sheet cells E6, E7, E8 with '{current_flash_code}'...")
            source_template_sheet.Range("E6").Value = current_flash_code
            source_template_sheet.Range("E7").Value = current_flash_code
            source_template_sheet.Range("E8").Value = current_flash_code

            # b. Refresh and Run Macros (in source_workbook)
            print("  Forcing calculation and refreshing all data in source workbook...")
            # It's often good to calculate before refreshing if pivots/charts depend on calculated cells
            excel_app.Calculate() # Calculates all open workbooks. Or source_wb.Calculate()
            source_wb.RefreshAll()
            # Wait for refresh to complete - this is tricky. Add a small delay if needed.
            # For robust solution, you might need to check specific query states if using Power Query.
            # excel_app.CalculateUntilAsyncQueriesDone() # If available and applicable

            if macro_names_to_run:
                for macro_name in macro_names_to_run:
                    print(f"  Running macro: '{macro_name}' in source workbook...")
                    try:
                        # Ensure macro name is qualified if it's not in a global module
                        # e.g., "Sheet1.MyMacro" or "ThisWorkbook.MyMacro" or just "MyMacro"
                        # Using f"'{source_wb.Name}'!{macro_name}" is safer for workbook-specific macros
                        excel_app.Run(f"'{os.path.basename(source_wb.FullName)}'!{macro_name}")
                        # Or, if macros are in modules: excel_app.Run(macro_name)
                    except Exception as e:
                        print(f"    Warning: Could not run macro '{macro_name}'. Error: {e}")
            else:
                print("  No macros specified to run.")

            # c. Determine New Sheet Name for Copy
            # Assuming sheet name base is from 'Template'!E5
            sheet_name_base_from_cell = source_template_sheet.Range("E5").Value
            if not sheet_name_base_from_cell:
                print("  Warning: Cell E5 in 'Template' sheet is empty. Using 'Report' as base name.")
                sheet_name_base_from_cell = "Report"
            
            target_sheet_name = sanitize_sheet_name(sheet_name_base_from_cell, current_flash_code)
            print(f"  Target sheet name in new workbook: '{target_sheet_name}'")

            # d. Copy 'Template' Sheet to New Workbook
            print(f"  Copying updated 'Template' sheet to '{new_workbook_save_path}' as '{target_sheet_name}'...")
            # Ensure no sheet with the same name already exists in new_wb
            for sheet_in_new_wb in new_wb.Sheets:
                if sheet_in_new_wb.Name == target_sheet_name:
                    print(f"    Sheet '{target_sheet_name}' already exists in new workbook. Deleting old one.")
                    sheet_in_new_wb.Delete() # Suppressed DisplayAlerts handles confirmation
                    break
            
            source_template_sheet.Copy(Before=new_wb.Sheets(1)) # Copies to the beginning
            copied_sheet_in_new_wb = new_wb.Sheets(1) # The newly copied sheet is now the first one
            copied_sheet_in_new_wb.Name = target_sheet_name

            print(f"  Successfully processed and copied sheet for flash code: {current_flash_code}")

        # --- 5. Finalize ---
        print(f"\nAll flash codes processed. Saving new workbook as '{new_workbook_save_path}'...")
        # Delete the default sheet "Sheet1" if it exists in new_wb and other sheets were added
        if new_wb.Sheets.Count > 1 and any(s.Name == "Sheet1" for s in new_wb.Sheets):
            try:
                default_sheet = new_wb.Sheets("Sheet1")
                # Check if it's the only sheet left (e.g. if no flash codes were processed)
                is_only_sheet = True
                for s in new_wb.Sheets:
                    if s.Name != "Sheet1":
                        is_only_sheet = False
                        break
                if not is_only_sheet: # Only delete if other sheets were added
                    default_sheet.Delete()
            except Exception as e:
                print(f"  Note: Could not delete default 'Sheet1' from new workbook: {e}")
        
        new_wb.SaveAs(new_workbook_save_path)
        print("New workbook saved.")

    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # --- Clean up ---
        print("Cleaning up Excel instances...")
        try:
            if source_wb is not None:
                try:
                    source_wb.Close(SaveChanges=False)  # Do not save changes to the original template
                    print("Source workbook closed.")
                except Exception as e:
                    print(f"Warning: Could not close source workbook: {e}")
        except Exception as e:
            print(f"Warning: Could not close source workbook (outer): {e}")

        try:
            if new_wb is not None:
                try:
                    if not new_wb.Saved:
                        new_wb.Close(SaveChanges=False)
                        print("New workbook closed without saving (due to error or no data).")
                    else:
                        new_wb.Close()
                        print("New workbook closed.")
                except Exception as e:
                    print(f"Warning: Could not close new workbook: {e}")
        except Exception as e:
            print(f"Warning: Could not close new workbook (outer): {e}")

        try:
            if excel_app is not None:
                try:
                    excel_app.Quit()
                    print("Excel application quit.")
                except Exception as e:
                    print(f"Warning: Could not quit Excel application: {e}")
        except Exception as e:
            print(f"Warning: Could not quit Excel application (outer): {e}")

        # Optional: Ensure COM objects are released
        source_template_sheet = None
        source_ref_sheet = None
        source_wb = None
        new_wb = None
    # For debugging, you can print all division names in Ref sheet:
    # (Uncomment the following lines to see available division names)
    # import win32com.client
    # excel = win32com.client.Dispatch("Excel.Application")
    # wb = excel.Workbooks.Open(SOURCE_WORKBOOK_FULL_PATH)
    # ref_sheet = wb.Sheets("Ref")
    # last_row = ref_sheet.Cells(ref_sheet.Rows.Count, "A").End(-4162).Row
    # print([ref_sheet.Cells(r, 1).Value for r in range(1, last_row+1)])
    # wb.Close(False)
    # excel.Quit()
    print("Automation process finished.")

if __name__ == "__main__":
    # --- !!! IMPORTANT: CONFIGURE THESE VALUES !!! ---
    # Example: "C:\\Users\\YourUser\\Documents\\RevenueReport phase2.xlsx"
    # Use raw string (r"...") or double backslashes ("C:\\...") for Windows paths
    SOURCE_WORKBOOK_FULL_PATH = r"D:\GenerativeAI\RevenueReport phase2.xlsm"

    # The division you want to process
    DIVISION_TO_PROCESS = "DIVISION 5 - ABELLO" # Example, change as needed

    # List of macro names to run. If macros are in specific sheets/modules, qualify them.
    # Example: ["ProcessReportData", "Module1.FinalizeCharts"]
    # If no macros, use an empty list: []
    MACROS_TO_RUN = ["'RevenueReport phase2.xlsm'!Module1.Chart2_Click", "'RevenueReport phase2.xlsm'!Module1.Chart6_Click"] # Replace with actual macro names or leave empty

    # --- Check if placeholder path is modified ---
    if r"D:\\GenerativeAI\\RevenueReport phase2.xlsm" in SOURCE_WORKBOOK_FULL_PATH:
        print("ERROR: Please update the 'SOURCE_WORKBOOK_FULL_PATH' variable in the script with the actual path to your Excel file.")
    else:
        automate_revenue_report(SOURCE_WORKBOOK_FULL_PATH, DIVISION_TO_PROCESS, MACROS_TO_RUN)

