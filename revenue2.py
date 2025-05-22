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

def automate_revenue_report(source_workbook_path, flash_codes_to_process, macro_names_to_run):
    """
    Automates the Excel report generation process using a provided list of flash codes.

    Args:
        source_workbook_path (str): Full path to the source Excel workbook.
        flash_codes_to_process (list): A list of flash code strings to process.
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
        # Ensure the path uses double backslashes for Excel compatibility
        new_workbook_save_path = os.path.join(output_folder, "sample.xlsx")
        new_workbook_save_path = os.path.abspath(new_workbook_save_path)
        new_workbook_save_path = new_workbook_save_path.replace('/', '\\')


        # --- 2. Access Sheets in Source Workbook ---
        try:
            source_template_sheet = source_wb.Sheets("Template")
            # source_ref_sheet is no longer needed as flash codes are passed directly
        except Exception as e:
            print(f"Error accessing 'Template' sheet in source workbook: {e}")
            if source_wb:
                source_wb.Close(SaveChanges=False)
            if new_wb: # Close new_wb if it was created but not saved
                new_wb.Close(SaveChanges=False)
            excel_app.Quit()
            return

        # --- 3. Validate Provided Flash Codes ---
        if not flash_codes_to_process or not isinstance(flash_codes_to_process, list):
            print("Error: No flash codes provided or the input is not a list.")
            if source_wb: source_wb.Close(SaveChanges=False)
            if new_wb: new_wb.Close(SaveChanges=False)
            excel_app.Quit()
            return

        print(f"Processing provided flash codes: {flash_codes_to_process}")

        # --- 4. Process Each Flash Code ---
        for current_flash_code in flash_codes_to_process:
            if not current_flash_code or not str(current_flash_code).strip():
                print(f"  Skipping empty or invalid flash code: '{current_flash_code}'")
                continue
            
            current_flash_code = str(current_flash_code).strip() # Ensure it's a string and stripped
            print(f"\nProcessing flash code: {current_flash_code}...")

            # a. Update 'Template' Sheet (in source_workbook)
            print(f"  Updating 'Template' sheet cells E6, E7, E8 with '{current_flash_code}'...")
            source_template_sheet.Range("E6").Value = current_flash_code
            source_template_sheet.Range("E7").Value = current_flash_code
            source_template_sheet.Range("E8").Value = current_flash_code

            # b. Refresh and Run Macros (in source_workbook)
            print("  Forcing calculation and refreshing all data in source workbook...")
            excel_app.Calculate() 
            source_wb.RefreshAll()
            
            if macro_names_to_run:
                for macro_name in macro_names_to_run:
                    print(f"  Running macro: '{macro_name}' in source workbook...")
                    try:
                        excel_app.Run(f"'{os.path.basename(source_wb.FullName)}'!{macro_name}" if "!" not in macro_name else macro_name)
                    except Exception as e:
                        print(f"    Warning: Could not run macro '{macro_name}'. Error: {e}")
            else:
                print("  No macros specified to run.")

            # c. Determine New Sheet Name for Copy using B5 cell value
            sheet_name_base_from_cell = source_template_sheet.Range("B5").Value
            if not sheet_name_base_from_cell:
                print("  Warning: Cell B5 in 'Template' sheet is empty. Using 'Report' as base name.")
                sheet_name_base_from_cell = "Report"
            
            target_sheet_name = sanitize_sheet_name(sheet_name_base_from_cell, current_flash_code)
            print(f"  Target sheet name in new workbook: '{target_sheet_name}'")

            # d. Copy 'Template' Sheet to New Workbook
            print(f"  Copying updated 'Template' sheet to '{new_workbook_save_path}' as '{target_sheet_name}'...")
            for sheet_in_new_wb in new_wb.Sheets:
                if sheet_in_new_wb.Name == target_sheet_name:
                    print(f"    Sheet '{target_sheet_name}' already exists in new workbook. Deleting old one.")
                    sheet_in_new_wb.Delete() 
                    break
            
            source_template_sheet.Copy(Before=new_wb.Sheets(1)) 
            copied_sheet_in_new_wb = new_wb.Sheets(1) 
            copied_sheet_in_new_wb.Name = target_sheet_name

            print(f"  Successfully processed and copied sheet for flash code: {current_flash_code}")

        # --- 5. Finalize ---
        print(f"\nAll flash codes processed. Saving new workbook as '{new_workbook_save_path}'...")
        if new_wb.Sheets.Count > 1 and any(s.Name == "Sheet1" for s in new_wb.Sheets):
            try:
                default_sheet = new_wb.Sheets("Sheet1")
                is_only_sheet = True
                for s in new_wb.Sheets:
                    if s.Name != "Sheet1":
                        is_only_sheet = False
                        break
                if not is_only_sheet: 
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
        if source_wb:
            source_wb.Close(SaveChanges=False) 
            print("Source workbook closed.")
        if new_wb and not new_wb.Saved: 
             new_wb.Close(SaveChanges=False)
             print("New workbook closed without saving (due to error or no data).")
        elif new_wb and new_wb.Saved:
            new_wb.Close() 
            print("New workbook closed.")


        if excel_app:
            excel_app.Quit()
            print("Excel application quit.")
        
        source_template_sheet = None # Removed source_ref_sheet
        source_wb = None
        new_wb = None
        excel_app = None
        print("Automation process finished.")

if __name__ == "__main__":
    # --- !!! IMPORTANT: CONFIGURE THESE VALUES !!! ---
    # NOTE: Update the path below to the actual location of your Excel file before running the script.
    SOURCE_WORKBOOK_FULL_PATH = r"D:\\GenerativeAI\\RevenueReport phase2.xlsm"

    # --- Provide the list of flash codes directly ---
    # Example: ["F100", "F205", "F310"]
    FLASH_CODES_TO_PROCESS = ["FSBC","FSFM","FSNX"] # Replace with actual flash codes

    # List of macro names to run.
    # Example format: ["'WorkbookName.xlsm'!ModuleName.MacroName", "'WorkbookName.xlsm'!SheetName.MacroName"]
    # Ensure the macro names include the workbook name (if needed), module or sheet name, and the macro name.
    # Example: ["'RevenueReport phase2.xlsm'!Module1.Chart2_Click", "'RevenueReport phase2.xlsm'!Module1.Chart6_Click"]
    MACROS_TO_RUN = ["Module1.Chart2_Click", "Module1.Chart6_Click"] # Replace with actual macro names or leave empty

    # --- Check if placeholder path is modified ---
    if "D:\\GenerativeAI\\RevenueReport phase2.xlsm" in SOURCE_WORKBOOK_FULL_PATH:
        print("ERROR: Please update the 'SOURCE_WORKBOOK_FULL_PATH' variable in the script with the actual path to your Excel file.")
    elif not FLASH_CODES_TO_PROCESS or not isinstance(FLASH_CODES_TO_PROCESS, list):
         print("ERROR: Please update the 'FLASH_CODES_TO_PROCESS' list in the script with your actual flash codes.")
    else:
        automate_revenue_report(SOURCE_WORKBOOK_FULL_PATH, FLASH_CODES_TO_PROCESS, MACROS_TO_RUN)

