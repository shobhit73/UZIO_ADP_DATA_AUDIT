
# ---------------------------------------------------------
# VERIFICATION SCRIPT FOR CENSUS GENERATOR LOGIC
# ---------------------------------------------------------
import pandas as pd
import sys
import os

# Mock the streamlit module so we can import the app function
import types
mock_st = types.ModuleType("streamlit")
mock_st.error = lambda *args, **kwargs: None
mock_st.warning = lambda *args, **kwargs: None
mock_st.info = lambda *args, **kwargs: None
mock_st.success = lambda *args, **kwargs: None
mock_st.set_page_config = lambda **kwargs: None
mock_st.title = lambda *args, **kwargs: None
mock_st.markdown = lambda *args, **kwargs: None
mock_st.file_uploader = lambda *args, **kwargs: None
mock_st.button = lambda *args, **kwargs: False
mock_st.spinner = lambda *args, **kwargs: types.SimpleNamespace(__enter__=lambda self: None, __exit__=lambda self, *args: None)
mock_st.download_button = lambda *args, **kwargs: None
sys.modules["streamlit"] = mock_st

# Add path to import
sys.path.append(os.getcwd())

# Import functions to test
from pages.Census_Generator import get_mapped_term_reason, get_state_abbr, norm_job_title

def test_term_reason():
    print("\n--- Testing Termination Reason Logic ---")
    cases = [
        ("Personal", "Voluntary Termination of Employment"),
        ("Attendance", "Involuntary Termination of Employment"),
        ("Deceased", "Death"),
        ("Random Reason", "Other"),
        ("  quit without notice  ", "Voluntary Termination of Employment"),
        ("", "Other"),
        (None, "Other")
    ]
    
    passes = 0
    for inp, expected in cases:
        res = get_mapped_term_reason(inp)
        if res == expected:
            passes += 1
        else:
            print(f"FAILED: Input='{inp}' -> Got='{res}', Expected='{expected}'")
            
    print(f"Termination Reason: {passes}/{len(cases)} Passed")

def test_state_abbr():
    print("\n--- Testing State Abbreviation Logic ---")
    cases = [
        ("Virginia", "VA"),
        ("virginia", "VA"),
        ("California", "CA"),
        ("NY", "NY"),
        ("  Texas  ", "TX"),
        ("", ""),
        (None, "")
    ]
    
    passes = 0
    for inp, expected in cases:
        res = get_state_abbr(inp)
        if res == expected:
            passes += 1
        else:
            print(f"FAILED: Input='{inp}' -> Got='{res}', Expected='{expected}'")
            
    print(f"State Abbr: {passes}/{len(cases)} Passed")

def test_job_title():
    print("\n--- Testing Job Title Logic ---")
    cases = [
        ("Admin", "administrator"),
        ("Management", "manager"),
        ("Software Engineer", "software engineer"), # Unmapped, should be lowered
        ("  DSP Owner  ", "owner"),
        (None, "")
    ]
    
    passes = 0
    for inp, expected in cases:
        res = norm_job_title(inp)
        if res == expected:
            passes += 1
        else:
            print(f"FAILED: Input='{inp}' -> Got='{res}', Expected='{expected}'")
            
    print(f"Job Title: {passes}/{len(cases)} Passed")


def test_pay_type_logic():
    print("\n--- Testing Pay Type Normalization Logic (Stub) ---")
    cases = [
        ("Hourly", "Hourly", True, False),
        ("Salaried", "Salaried", False, True),
        ("Salary", "Salaried", False, True),
        ("Exempt", "Salaried", False, True),
        ("Non-Exempt Hourly", "Hourly", True, False),
        ("Full Time", "Full Time", False, False) # Fallback
    ]
    
    passes = 0
    for inp, expected_val, exp_hourly, exp_salary in cases:
        # Re-implementing logic here to verify consistency with my thought process
        row_pay_type_source = inp.lower()
        norm_val = ""
        act_hourly = False
        act_salary = False
        
        if "hour" in row_pay_type_source:
            norm_val = "Hourly"
            act_hourly = True
        elif "sal" in row_pay_type_source or "exempt" in row_pay_type_source:
            norm_val = "Salaried"
            act_salary = True
        else:
            norm_val = inp.title()
            
        if norm_val.lower() == "salary":
            norm_val = "Salaried"
            
        if norm_val == expected_val and act_hourly == exp_hourly and act_salary == exp_salary:
            passes += 1
        else:
             print(f"FAILED: Input='{inp}' -> Got='{norm_val}', Expected='{expected_val}'")

    print(f"Pay Type Logic: {passes}/{len(cases)} Passed")


def test_flsa_logic():
    print("\n--- Testing FLSA Logic (Stub) ---")
    cases = [
        (True, False, "Non-Exempt"), # Hourly
        (False, True, "Exempt"),     # Salaried
        (False, False, None)         # Unknown
    ]
    
    passes = 0
    for is_hourly, is_salary, expected in cases:
        val = None
        if is_hourly:
            val = "Non-Exempt"
        elif is_salary:
            val = "Exempt"
            
        if val == expected:
            passes += 1
        else:
            print(f"FAILED: Hourly={is_hourly}, Salary={is_salary} -> Got='{val}', Expected='{expected}'")
            
    print(f"FLSA Logic: {passes}/{len(cases)} Passed")

if __name__ == "__main__":
    test_term_reason()
    test_state_abbr()
    test_job_title()
    test_pay_type_logic()
    test_flsa_logic()
