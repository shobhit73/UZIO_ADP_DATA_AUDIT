# ADP Uzio Data Comparator Tool

This tool automates the auditing and comparison of census data between **Uzio** and **ADP** (or Paycom). It normalizes data formats (SSN, dates, gender, etc.) to ensure accurate comparisons and generates a detailed discrepancy report.

## 📚 Documentation
For detailed instructions on how to prepare input files, run the tool, and interpret the results, please refer to the **[Standard Operating Procedure (SOP)](SOP.md)**.

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.x installed.

### 2. Setup
Open a terminal in the project folder and install dependencies:
```bash
pip install -r requirements.txt
```

### 3. Run the App
Launch the tool interface:
```bash
streamlit run app.py
```

## 📂 Output
The tool generates an Excel report named `Client_Name_ADP_Census_Data_Audit_YYYY-MM-DD.xlsx` containing:
- **Summary**: High-level audit metrics.
- **Field Summary**: Discrepancy counts per field.
- **Comparison Detail**: Row-by-row analysis of every employee and field.
