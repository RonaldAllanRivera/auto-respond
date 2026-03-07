#!/usr/bin/env python3
"""
Test script to verify imperative prompt detection works.
"""

from detector import detect_questions

# Test cases
test_cases = [
    "Explain Python Programming Language",
    "Describe photosynthesis",
    "Define recursion",
    "Compare Python and Java",
    "What is Python?",
    "How does this work?",
    "Calculate 5 + 3",
]

print("Testing imperative prompt detection:\n")
for text in test_cases:
    detected = detect_questions(text)
    status = "✓ DETECTED" if detected else "✗ MISSED"
    print(f"{status}: '{text}'")
    if detected:
        print(f"         → {detected[0]}")
    print()

print("\nAll test cases should show '✓ DETECTED'")
