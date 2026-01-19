# Standard Operating Procedure (SOP): ADP Uzio Data Comparator Tool

## 1. Overview
The **ADP Uzio Data Comparator Tool** is a Python-based application designed to audit and compare employee census data between the **Uzio** platform and **ADP** (or Paycom). It identifies discrepancies, missing data, and potential mapping issues to ensure data integrity across systems.

## 2. Prerequisites
Before running the tool, ensure the following are installed on your system:
- **Python 3.x**: [Download Python](https://www.python.org/downloads/)
- **Required Libraries**: Installed via `requirements.txt` (see Setup section).

## 3. Input File Requirements
The tool accepts a single Excel workbook (`.xlsx`) as input. This workbook **MUST** generally contain the following three sheets with exact names (or as configured in the code):

### A. Sheet 1: `Uzio Data`
- Contains the census data exported from the Uzio platform.
- **Key Requirement**: Must include a unique identifier column (e.g., `Employee ID`).

### B. Sheet 2: `ADP Data`
- Contains the census data exported from ADP (or Paycom).
- **Key Requirement**: Must include a corresponding unique identifier column (e.g., `Associate ID`).

### C. Sheet 3: `Mapping Sheet`
- Defines how columns in Uzio map to columns in ADP.
- **Required Columns**:
    1.  `Uzio Coloumn`: Header name in the **Uzio Data** sheet.
    2.  `ADP Coloumn`: Corresponding header name in the **ADP Data** sheet.
- **Critical Mapping Rules**:
    - You **MUST** map the unique identifier.
        - Example: Map `Employee ID` (Uzio) to `Associate ID` (ADP).
    - Rows with empty values in either column will be ignored.
    - Duplicate mappings for the same Uzio column are removed (first one kept).

## 4. Setup and Installation
1.  **Unzip/Navigation**: Open the folder containing the tool files.
2.  **Open Terminal**: Right-click inside the folder and select "Open in Terminal" (or use Command Prompt).
3.  **Install Dependencies** (First time only):
    ```bash
    pip install -r requirements.txt
    ```

## 5. Running the Tool
1.  In the terminal, run the following command:
    ```bash
    streamlit run app.py
    ```
2.  A browser window will automatically open showing the tool's interface.
    - If it doesn't open, copy the "Local URL" shown in the terminal (usually `http://localhost:8501`) and paste it into your browser.

## 6. Using the Tool
1.  **Upload File**: Click the **"Browse files"** button and select your prepared Excel workbook.
2.  **Run Audit**: Click the **"Run Audit"** button.
    - The tool will process the data, perform normalizations (e.g., formatting SSNs, dates, gender), and compare values.
3.  **Download Report**: Once processing is complete, a **"Download Report (.xlsx)"** button will appear.
    - Click to save the audit report.
    - **Filename Format**: `Client_Name_ADP_Census_Data_Audit_YYYY-MM-DD.xlsx` (e.g., `Client_Name_ADP_Census_Data_Audit_2026-01-19.xlsx`).

## 7. Understanding the Audit Report
 The generated report contains the following output sheets:

### A. `Summary`
- Provides high-level metrics:
    - Total employees in Uzio and ADP.
    - Number of matches vs. mismatches.
    - Count of mapped fields.

### B. `Field_Summary_By_Status`
- A pivot table showing the count of each status for every mapped field.
- Helps identify systemic issues (e.g., if "Date of Birth" has 500 mismatches, check the format).

### C. `Comparison_Detail_AllFields`
- The granular, row-by-row comparison data.
- **Key Column**: `ADP_SourceOfTruth_Status`
    - **Data Match**: Values are identical (after normalization).
    - **Data Mismatch**: Values differ between Uzio and ADP.
    - **Value missing in Uzio (ADP has value)**: Field is empty in Uzio but populated in ADP.
    - **Value missing in ADP (Uzio has value)**: Field is populated in Uzio but empty in ADP.
    - **Employee ID Not Found in ADP**: Employee exists in Uzio but not in ADP file.
    - **Employee ID Not Found in Uzio**: Employee exists in ADP but not in Uzio file.
    - **Column Missing in ADP Sheet**: The mapped column header was not found in the ADP sheet.
    - **Column Missing in Uzio Sheet**: The mapped column header was not found in the Uzio sheet.

## 8. Logic & Normalization Notes
The tool applies smart logic to reduce false positives:
- **SSN**: Formats to 9 digits, adds leading zeros.
- **Dates**: Standardizes to `YYYY-MM-DD`.
- **Gender**: Normalizes "Female"/"Woman" to "female", "Male"/"Man" to "male".
- **Pay Type**: Maps "Salary"/"Salaried" and "Hourly"/"Hour" to common buckets.
- **Employment Status**: Checks for "Active", "Terminated", etc.
- **Termination Reasons**: Matches "Other" in Uzio to specific allowed reasons in ADP.
- **Middle Initial**: Extracts the first letter if comparing a full middle name to an initial.
