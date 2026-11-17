"""Static reference data: crops, Karnataka mandis, MSP and the festival calendar.

Coordinates are approximate APMC yard locations. MSP values are the published Government of
India MSPs where known (Rs/quintal); the 2026-27 values are marked as estimates (+5%).
Festival dates are the commonly observed dates for Karnataka.
"""

# code, en, hi, kn, category, emoji, agmarknet commodity, k (daily decay @25C), storage Rs/qtl/day, base Rs/qtl
CROPS = [
    ("tomato", "Tomato", "टमाटर", "ಟೊಮೆಟೊ", "vegetable", "🍅", "Tomato", 0.060, 0.0, 1600),
    ("onion", "Onion", "प्याज", "ಈರುಳ್ಳಿ", "vegetable", "🧅", "Onion", 0.006, 1.0, 2200),
    ("potato", "Potato", "आलू", "ಆಲೂಗಡ್ಡೆ", "vegetable", "🥔", "Potato", 0.005, 1.5, 1900),
    ("green_chilli", "Green Chilli", "हरी मिर्च", "ಹಸಿ ಮೆಣಸಿನಕಾಯಿ", "vegetable", "🌶️", "Green Chilli", 0.045, 0.0, 3200),
    ("banana", "Banana", "केला", "ಬಾಳೆಹಣ್ಣು", "fruit", "🍌", "Banana", 0.070, 0.0, 2000),
    ("paddy", "Paddy", "धान", "ಭತ್ತ", "cereal", "🌾", "Paddy(Dhan)(Common)", 0.0005, 0.6, 2400),
    ("maize", "Maize", "मक्का", "ಮೆಕ್ಕೆಜೋಳ", "cereal", "🌽", "Maize", 0.0008, 0.6, 2250),
    ("ragi", "Ragi", "रागी", "ರಾಗಿ", "cereal", "🌾", "Ragi (Finger Millet)", 0.0004, 0.6, 3900),
    ("tur", "Tur (Arhar)", "अरहर (तूर)", "ತೊಗರಿ", "pulse", "🫘", "Arhar (Tur/Red Gram)(Whole)", 0.0004, 0.8, 7600),
    ("cotton", "Cotton", "कपास", "ಹತ್ತಿ", "fibre", "☁️", "Cotton", 0.0002, 0.5, 7200),
]

# Price-season shape: month index (1-12) of the seasonal low (harvest glut) and amplitude.
CROP_SEASON = {
    "tomato": (2, 0.35), "onion": (3, 0.30), "potato": (2, 0.15), "green_chilli": (1, 0.25),
    "banana": (7, 0.12), "paddy": (11, 0.06), "maize": (10, 0.08), "ragi": (12, 0.07),
    "tur": (1, 0.10), "cotton": (11, 0.07),
}
# Daily log-price volatility (synthetic generator).
CROP_VOL = {
    "tomato": 0.045, "onion": 0.03, "potato": 0.02, "green_chilli": 0.04, "banana": 0.02,
    "paddy": 0.006, "maize": 0.009, "ragi": 0.008, "tur": 0.01, "cotton": 0.008,
}

# code, name, district, agmarknet market name, lat, lon, market fee %, commission %, hamali Rs/qtl
MANDIS = [
    ("blr_ypr", "Bengaluru (Yeshwanthpur)", "Bengaluru Urban", "Bangalore", 13.0280, 77.5409, 1.0, 5.0, 25),
    ("kolar", "Kolar", "Kolar", "Kolar", 13.1370, 78.1290, 1.0, 6.0, 20),
    ("chikkaballapur", "Chikkaballapur", "Chikkaballapur", "Chikkaballapur", 13.4350, 77.7280, 1.0, 6.0, 18),
    ("mysuru", "Mysuru (Bandipalya)", "Mysuru", "Mysore (Bandipalya)", 12.2680, 76.6770, 1.0, 5.0, 20),
    ("tumakuru", "Tumakuru", "Tumakuru", "Tumkur", 13.3400, 77.1010, 1.0, 4.0, 18),
    ("hassan", "Hassan", "Hassan", "Hassan", 13.0070, 76.0960, 1.0, 4.0, 18),
    ("shivamogga", "Shivamogga", "Shivamogga", "Shimoga", 13.9300, 75.5680, 1.0, 4.0, 18),
    ("davanagere", "Davanagere", "Davanagere", "Davangere", 14.4640, 75.9210, 1.0, 3.5, 15),
    ("hubballi", "Hubballi (Amargol)", "Dharwad", "Hubli (Amaragol)", 15.3640, 75.1240, 1.0, 4.0, 18),
    ("belagavi", "Belagavi", "Belagavi", "Belgaum", 15.8490, 74.4970, 1.0, 4.0, 18),
    ("kalaburagi", "Kalaburagi", "Kalaburagi", "Gulbarga", 17.3290, 76.8340, 1.0, 3.0, 15),
    ("raichur", "Raichur", "Raichur", "Raichur", 16.2050, 77.3550, 1.0, 3.0, 15),
]

# Which crops trade at which mandi, with the mandi's typical price premium vs state average.
MANDI_CROPS = {
    "blr_ypr": {"tomato": 0.06, "onion": 0.05, "potato": 0.05, "green_chilli": 0.06, "banana": 0.07, "ragi": 0.04, "maize": 0.02},
    "kolar": {"tomato": -0.02, "potato": 0.0, "green_chilli": -0.01, "ragi": 0.0},
    "chikkaballapur": {"tomato": -0.03, "potato": -0.01, "green_chilli": -0.02, "maize": -0.01},
    "mysuru": {"tomato": 0.03, "onion": 0.02, "banana": 0.0, "paddy": 0.01, "ragi": 0.02},
    "tumakuru": {"ragi": -0.01, "maize": 0.0, "onion": 0.0, "banana": -0.02, "tur": -0.01},
    "hassan": {"potato": -0.02, "maize": -0.01, "paddy": 0.0, "ragi": -0.02},
    "shivamogga": {"paddy": 0.02, "maize": 0.01, "banana": -0.01},
    "davanagere": {"maize": -0.02, "paddy": -0.01, "onion": -0.01, "cotton": 0.0},
    "hubballi": {"onion": 0.01, "tomato": 0.01, "green_chilli": 0.03, "cotton": 0.02, "maize": 0.0, "tur": 0.01},
    "belagavi": {"onion": 0.0, "potato": 0.02, "tomato": 0.0, "maize": 0.01},
    "kalaburagi": {"tur": -0.02, "cotton": -0.01, "onion": -0.03},
    "raichur": {"cotton": -0.01, "paddy": 0.0, "tur": 0.0},
}

# Typical daily arrivals (tonnes) at a large mandi.
CROP_ARRIVALS = {
    "tomato": 300, "onion": 450, "potato": 250, "green_chilli": 60, "banana": 80,
    "paddy": 400, "maize": 500, "ragi": 150, "tur": 120, "cotton": 200,
}

# Minimum Support Price, Rs/quintal, by kharif marketing-year start. None for non-MSP crops.
MSP = {
    "paddy": {2022: 2040, 2023: 2183, 2024: 2300, 2025: 2369},
    "maize": {2022: 1962, 2023: 2090, 2024: 2225, 2025: 2400},
    "ragi": {2022: 3578, 2023: 3846, 2024: 4290, 2025: 4886},
    "tur": {2022: 6600, 2023: 7000, 2024: 7550, 2025: 8000},
    "cotton": {2022: 6080, 2023: 6620, 2024: 7121, 2025: 7710},
}
MSP_ESTIMATE_GROWTH = 0.05

# (name, impact on demand/price, {year: "MM-DD"})
FESTIVALS = [
    ("Makar Sankranti", 0.05, {y: "01-14" for y in range(2022, 2029)}),
    ("Ugadi", 0.06, {2022: "04-02", 2023: "03-22", 2024: "04-09", 2025: "03-30", 2026: "03-19", 2027: "04-07", 2028: "03-27"}),
    ("Eid al-Fitr", 0.04, {2022: "05-03", 2023: "04-22", 2024: "04-11", 2025: "03-31", 2026: "03-20", 2027: "03-10", 2028: "02-27"}),
    ("Varamahalakshmi", 0.05, {2022: "08-05", 2023: "08-25", 2024: "08-16", 2025: "08-08", 2026: "08-28", 2027: "08-13", 2028: "08-04"}),
    ("Ganesh Chaturthi", 0.07, {2022: "08-31", 2023: "09-19", 2024: "09-07", 2025: "08-27", 2026: "09-14", 2027: "09-04", 2028: "08-23"}),
    ("Dasara", 0.08, {2022: "10-05", 2023: "10-24", 2024: "10-12", 2025: "10-02", 2026: "10-20", 2027: "10-09", 2028: "09-27"}),
    ("Deepavali", 0.09, {2022: "10-24", 2023: "11-12", 2024: "11-01", 2025: "10-21", 2026: "11-08", 2027: "10-29", 2028: "10-17"}),
    ("Christmas", 0.03, {y: "12-25" for y in range(2022, 2029)}),
]
