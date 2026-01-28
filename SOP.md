# Standard Operating Procedure (SOP)
## Census ADP and Uzio Data Review Tool

### 1. Introduction
This tool helps you comparing employee data between **Uzio** and **ADP**. It automatically identifies differences (mismatches) and creates a simple report for you to review.

### 2. Preparing the Input File
To run the audit, you need to prepare a single Excel file (`.xlsx`) with your data. This file must contain exactly **three sheets** (tabs) at the bottom.

#### Step 1: Create the Excel File
Open a new Excel workbook and create three sheets named exactly as follows:
1.  **Uzio Data**
2.  **ADP Data**
3.  **Mapping Sheet**

> [!IMPORTANT]
> The names of these sheets must match exactly. Please check spelling and capitalization.

#### Step 2: Paste Your Data
*   **In the "Uzio Data" sheet:** Paste the full census report exported from Uzio. Include the header row (the top row with column names).
*   **In the "ADP Data" sheet:** Paste the full census report exported from ADP. Include the header row.

#### Step 3: Fill the Mapping Sheet
The "Mapping Sheet" tells the tool which column in Uzio corresponds to which column in ADP.
Create two columns in this sheet:
*   **Column A Header:** `Uzio Coloumn`
*   **Column B Header:** `ADP Coloumn`

List the column names from your data under these headers. For example:

| Uzio Coloumn | ADP Coloumn |
| :--- | :--- |
| First Name | Legal First Name |
| Last Name | Legal Last Name |
| DOB | Birth Date |
| Employee ID | Associate ID |

**Critical Rule:**  
You **must** include a mapping for the Employee ID. The tool uses this to find the same person in both files.

### 3. How to Run the Tool

1.  **Open the Tool Link:** [**https://uzio-adp-data-audit.streamlit.app/**](https://uzio-adp-data-audit.streamlit.app/)
2.  **Upload Your File:**
    *   Look for the area that says **"Drag and drop file here"**.
    *   Drag your prepared Excel file into this box, or click **"Browse files"** to select it from your computer.
3.  **Wait for Processing:** The tool will automatically read your file.
4.  **Download Report:**
    *   Once processing is complete, a **"Download Audit Report"** button will appear.
    *   Click it to save the results to your computer.

### 4. Understanding the Report
The downloaded Excel file will have a few tabs. The main one is **Comparison_Detail_AllFields**. Here is what the status column means:

| Status Message | Meaning | Action Required |
| :--- | :--- | :--- |
| **Data Match** | The information is identical in both systems. | ✅ No action needed. |
| **Data Mismatch** | The information is different (e.g., DOB is different). | ⚠️ Investigate the difference. |
| **Value missing in Uzio** | ADP has data, but Uzio is blank. | 📝 Check if data needs to be added to Uzio. |
| **Value missing in ADP** | Uzio has data, but ADP is blank. | 📝 Check if data needs to be added to ADP. |
| **Active in Uzio** | Employee is Active in Uzio but Terminated/Retired in ADP. | ⚠️ Verify employment status. |
| **Terminated in Uzio** | Employee is Terminated in Uzio but Active in ADP. | ⚠️ Verify employment status. |
| **Active in ADP** | Uzio is blank, but ADP shows as Active. | ⚠️ Verify employment status. |
| **Terminated in ADP** | Uzio is blank, but ADP shows as Terminated. | ⚠️ Verify employment status. |

### 5. Common Issues & Tips
*   **"File must have 3 sheets":** Make sure you didn't rename the tabs incorrectly.
*   **"Employee ID not found":** Check your Mapping Sheet. Did you type the column headers exactly as they appear in the data? (e.g., "Employee ID" vs "Emp ID").
*   **Special Matches:** The tool is smart enough to know that "Active" matches "Leave", and "Terminated" matches "Deceased" or "Retired". These will show as a **Data Match**.
