"""
This script reads an Excel file and modifies the values in Column B
by shortening dot-separated strings.

Specifically:
- For each string in Column B:
    - If it contains one or more dots, only the last segment is retained.
    - If there is no dot, the string is left unchanged.
- The updated data is saved to a new Excel file called 'shortend_Team-Member-Registration-DET.xlsx'.

Use Case:
This is useful for simplifying verbose or hierarchical field names
(e.g., 'form.section.group.field' → 'field') for better readability,
especially when preparing data for database headers, analytics, or display.
"""

import pandas as pd

# Load Excel file
file_path = "Team-Member-Registration-DET.xlsx"  # Replace this with your actual file path
df = pd.read_excel(file_path)

# Function to shorten the string in Column B to the last segment after the dot
def keep_last_segment(s):
    if isinstance(s, str) and '.' in s:
        return s.split('.')[-1]  # Keep only the last segment
    return s  # Return as is if no dot or not a string

# Apply the function to column B (2nd column, index 1)
df.iloc[:, 1] = df.iloc[:, 1].apply(keep_last_segment)

# Save to a new Excel file
df.to_excel("shortend_Team-Member-Registration-DET.xlsx", index=False)
