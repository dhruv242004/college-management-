"""College information and configuration settings."""

COLLEGE_INFO = {
    "name": "Premier College Management System",
    "tagline": "Excellence in Education, Innovation in Learning",
    "email": "info@college.edu",
    "phone": "+91 98765 43210",
    "address": "123 Education Street, Academic City, State - 123456",
    "website": "www.college.edu",
    "established_year": 2000,
    "abbreviation": "PCMS"
}

COLLEGE_HIGHLIGHTS = {
    "courses": "20+",
    "description": "Wide range of undergraduate and postgraduate programs",
    "students": "5000+",
    "faculty": "500+",
    "placement": "100%",
    "facilities": "World-class infrastructure"
}

FEATURES = {
    "modern_ui": True,
    "3d_animations": True,
    "enrollment_based_login": True,
    "course_wise_enrollment": True,
    "automated_enrollment": True,
    "glassmorphism": True,
    "dark_mode": True
}

ENROLLMENT_PREFIX_MAP = {
    # Maps course codes to enrollment prefixes
    # Example: {"BCA": "BCA", "MCA": "MCA", "BSC": "BSC"}
}

COURSE_ENROLLMENT_FORMAT = "{COURSE_CODE}{YEAR}{SEQUENCE:03d}"
# Example: BCA2025001, MCA2025002
