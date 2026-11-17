"""Server-side text for explanations and alerts in English, Hindi and Kannada.

Alerts are stored language-neutral (kind + params) and rendered in the reader's language.
"""
from __future__ import annotations

LANGS = ("en", "hi", "kn")

T: dict[str, dict[str, str]] = {
    # ---- SHAP reason groups (why the forecast moves) ----
    "seasonal.up": {"en": "Prices usually rise at this time of year",
                    "hi": "साल के इस समय आमतौर पर भाव बढ़ते हैं",
                    "kn": "ವರ್ಷದ ಈ ಸಮಯದಲ್ಲಿ ಸಾಮಾನ್ಯವಾಗಿ ಬೆಲೆ ಏರುತ್ತದೆ"},
    "seasonal.down": {"en": "Prices usually fall at this time of year",
                      "hi": "साल के इस समय आमतौर पर भाव घटते हैं",
                      "kn": "ವರ್ಷದ ಈ ಸಮಯದಲ್ಲಿ ಸಾಮಾನ್ಯವಾಗಿ ಬೆಲೆ ಇಳಿಯುತ್ತದೆ"},
    "festival.up": {"en": "{festival} is coming - demand rises before festivals",
                    "hi": "{festival} आने वाला है - त्योहार से पहले मांग बढ़ती है",
                    "kn": "{festival} ಹಬ್ಬ ಬರುತ್ತಿದೆ - ಹಬ್ಬದ ಮುಂಚೆ ಬೇಡಿಕೆ ಹೆಚ್ಚುತ್ತದೆ"},
    "festival.down": {"en": "Festival demand fades after {festival}",
                      "hi": "{festival} के बाद त्योहार की मांग कम हो जाती है",
                      "kn": "{festival} ನಂತರ ಹಬ್ಬದ ಬೇಡಿಕೆ ಕಡಿಮೆಯಾಗುತ್ತದೆ"},
    "trend.up": {"en": "Prices have been rising over the last few weeks",
                 "hi": "पिछले कुछ हफ्तों से भाव बढ़ रहे हैं",
                 "kn": "ಕಳೆದ ಕೆಲವು ವಾರಗಳಿಂದ ಬೆಲೆ ಏರುತ್ತಿದೆ"},
    "trend.down": {"en": "Prices have been falling over the last few weeks",
                   "hi": "पिछले कुछ हफ्तों से भाव गिर रहे हैं",
                   "kn": "ಕಳೆದ ಕೆಲವು ವಾರಗಳಿಂದ ಬೆಲೆ ಇಳಿಯುತ್ತಿದೆ"},
    "level.up": {"en": "The price is below its usual level and tends to recover",
                 "hi": "भाव अपने सामान्य स्तर से नीचे है, आगे सुधार की उम्मीद है",
                 "kn": "ಬೆಲೆ ತನ್ನ ಸಾಮಾನ್ಯ ಮಟ್ಟಕ್ಕಿಂತ ಕಡಿಮೆ ಇದೆ, ಚೇತರಿಕೆಯ ನಿರೀಕ್ಷೆ ಇದೆ"},
    "level.down": {"en": "The price is above its usual level and tends to come down",
                   "hi": "भाव अपने सामान्य स्तर से ऊपर है, आगे नरमी की संभावना है",
                   "kn": "ಬೆಲೆ ಸಾಮಾನ್ಯ ಮಟ್ಟಕ್ಕಿಂತ ಹೆಚ್ಚಿದೆ, ಇಳಿಕೆಯ ಸಾಧ್ಯತೆ ಇದೆ"},
    "arrivals.up": {"en": "Less crop is arriving at mandis than usual",
                    "hi": "मंडियों में आवक सामान्य से कम है",
                    "kn": "ಮಂಡಿಗಳಿಗೆ ಆವಕ ಸಾಮಾನ್ಯಕ್ಕಿಂತ ಕಡಿಮೆ ಇದೆ"},
    "arrivals.down": {"en": "More crop is arriving at mandis than usual",
                      "hi": "मंडियों में आवक सामान्य से ज़्यादा है",
                      "kn": "ಮಂಡಿಗಳಿಗೆ ಆವಕ ಸಾಮಾನ್ಯಕ್ಕಿಂತ ಹೆಚ್ಚಿದೆ"},
    "rain.up": {"en": "Recent heavy rain may cut supply",
                "hi": "हाल की भारी बारिश से आपूर्ति घट सकती है",
                "kn": "ಇತ್ತೀಚಿನ ಭಾರೀ ಮಳೆಯಿಂದ ಪೂರೈಕೆ ಕಡಿಮೆಯಾಗಬಹುದು"},
    "rain.down": {"en": "Dry, clear weather keeps supply normal",
                  "hi": "मौसम साफ़ है, आपूर्ति सामान्य रहेगी",
                  "kn": "ಹವಾಮಾನ ಚೆನ್ನಾಗಿದೆ, ಪೂರೈಕೆ ಸಾಮಾನ್ಯವಾಗಿರುತ್ತದೆ"},
    "msp.up": {"en": "The government MSP is supporting the price",
               "hi": "सरकारी MSP भाव को सहारा दे रहा है",
               "kn": "ಸರ್ಕಾರದ ಬೆಂಬಲ ಬೆಲೆ (MSP) ಬೆಲೆಗೆ ಆಧಾರ ನೀಡುತ್ತಿದೆ"},
    "msp.down": {"en": "The price is well above MSP, so there is room to fall",
                 "hi": "भाव MSP से काफ़ी ऊपर है, इसलिए गिरावट की गुंजाइश है",
                 "kn": "ಬೆಲೆ MSP ಗಿಂತ ಸಾಕಷ್ಟು ಹೆಚ್ಚಿದೆ, ಇಳಿಕೆಗೆ ಅವಕಾಶವಿದೆ"},
    "market.up": {"en": "This mandi's usual pattern favours higher prices",
                  "hi": "इस मंडी का सामान्य रुझान ऊँचे भाव के पक्ष में है",
                  "kn": "ಈ ಮಂಡಿಯ ಸಾಮಾನ್ಯ ಪ್ರವೃತ್ತಿ ಹೆಚ್ಚಿನ ಬೆಲೆಗೆ ಅನುಕೂಲಕರ"},
    "market.down": {"en": "This mandi's usual pattern points to lower prices",
                    "hi": "इस मंडी का सामान्य रुझान कम भाव की ओर है",
                    "kn": "ಈ ಮಂಡಿಯ ಸಾಮಾನ್ಯ ಪ್ರವೃತ್ತಿ ಕಡಿಮೆ ಬೆಲೆಯ ಕಡೆಗಿದೆ"},
    # ---- decision-level explanation ----
    "decision.best_vs_nearest": {
        "en": "Selling at {best} earns ₹{gain} more than selling today at {nearest}, your nearest mandi.",
        "hi": "{best} में बेचने पर आज नज़दीकी मंडी {nearest} की तुलना में ₹{gain} ज़्यादा मिलेंगे।",
        "kn": "{best} ನಲ್ಲಿ ಮಾರಿದರೆ, ಇಂದು ಹತ್ತಿರದ ಮಂಡಿ {nearest} ಗಿಂತ ₹{gain} ಹೆಚ್ಚು ಸಿಗುತ್ತದೆ."},
    "decision.best_is_nearest": {
        "en": "Your nearest mandi, {best}, is also the most profitable.",
        "hi": "आपकी नज़दीकी मंडी {best} ही सबसे ज़्यादा फ़ायदेमंद है।",
        "kn": "ನಿಮ್ಮ ಹತ್ತಿರದ ಮಂಡಿ {best} ಅತ್ಯಂತ ಲಾಭದಾಯಕವೂ ಆಗಿದೆ."},
    "decision.wait": {
        "en": "Wait {days} days: the price is expected to rise from ₹{p0} to ₹{p1} per quintal.",
        "hi": "{days} दिन रुकें: भाव ₹{p0} से बढ़कर ₹{p1} प्रति क्विंटल होने की उम्मीद है।",
        "kn": "{days} ದಿನ ಕಾಯಿರಿ: ಬೆಲೆ ಕ್ವಿಂಟಾಲ್‌ಗೆ ₹{p0} ರಿಂದ ₹{p1} ಕ್ಕೆ ಏರುವ ನಿರೀಕ್ಷೆ ಇದೆ."},
    "decision.sell_now": {
        "en": "Sell now - after spoilage and costs, waiting does not pay.",
        "hi": "अभी बेचें - खराबी और खर्च के बाद रुकने का फ़ायदा नहीं है।",
        "kn": "ಈಗಲೇ ಮಾರಿ - ಹಾಳಾಗುವಿಕೆ ಮತ್ತು ಖರ್ಚಿನ ನಂತರ ಕಾಯುವುದರಿಂದ ಲಾಭವಿಲ್ಲ."},
    "decision.costs": {
        "en": "Transport ₹{transport} by {vehicle} ({km} km), mandi fees ₹{fees}, spoilage {spoil}%.",
        "hi": "ढुलाई ₹{transport} ({vehicle}, {km} किमी), मंडी शुल्क ₹{fees}, खराबी {spoil}%।",
        "kn": "ಸಾಗಣೆ ₹{transport} ({vehicle}, {km} ಕಿ.ಮೀ), ಮಂಡಿ ಶುಲ್ಕ ₹{fees}, ಹಾಳಾಗುವಿಕೆ {spoil}%."},
    "decision.risk": {
        "en": "Even in a bad case you should get about ₹{net_lo}.",
        "hi": "बुरी स्थिति में भी लगभग ₹{net_lo} मिलने चाहिए।",
        "kn": "ಕೆಟ್ಟ ಸಂದರ್ಭದಲ್ಲೂ ಸುಮಾರು ₹{net_lo} ಸಿಗಬೇಕು."},
    "decision.split": {
        "en": "Your lot is large: splitting it across {n} mandi trips earns ₹{gain} more than one market can absorb.",
        "hi": "आपका माल ज़्यादा है: इसे {n} मंडियों में बाँटकर बेचने से ₹{gain} ज़्यादा मिलेंगे।",
        "kn": "ನಿಮ್ಮ ಸರಕು ಹೆಚ್ಚಿದೆ: {n} ಮಂಡಿಗಳಿಗೆ ಹಂಚಿ ಮಾರಿದರೆ ₹{gain} ಹೆಚ್ಚು ಸಿಗುತ್ತದೆ."},
    "vehicle.pickup": {"en": "pickup", "hi": "पिकअप", "kn": "ಪಿಕಪ್"},
    "vehicle.tempo": {"en": "tempo", "hi": "टेम्पो", "kn": "ಟೆಂಪೋ"},
    "vehicle.truck": {"en": "truck", "hi": "ट्रक", "kn": "ಲಾರಿ"},
    # ---- alerts ----
    "alert.forecast_rise": {
        "en": "{crop} at {mandi}: price expected to rise {pct}% in {days} days (₹{p0} → ₹{p1}/qtl). Holding may pay.",
        "hi": "{mandi} में {crop}: {days} दिनों में भाव {pct}% बढ़ने की उम्मीद (₹{p0} → ₹{p1}/क्विंटल)। रुकना फ़ायदेमंद हो सकता है।",
        "kn": "{mandi} ನಲ್ಲಿ {crop}: {days} ದಿನಗಳಲ್ಲಿ ಬೆಲೆ {pct}% ಏರುವ ನಿರೀಕ್ಷೆ (₹{p0} → ₹{p1}/ಕ್ವಿಂ). ಕಾಯುವುದು ಲಾಭದಾಯಕವಾಗಬಹುದು."},
    "alert.forecast_drop": {
        "en": "{crop} at {mandi}: price expected to fall {pct}% in {days} days (₹{p0} → ₹{p1}/qtl). Consider selling soon.",
        "hi": "{mandi} में {crop}: {days} दिनों में भाव {pct}% गिरने की आशंका (₹{p0} → ₹{p1}/क्विंटल)। जल्दी बेचने पर विचार करें।",
        "kn": "{mandi} ನಲ್ಲಿ {crop}: {days} ದಿನಗಳಲ್ಲಿ ಬೆಲೆ {pct}% ಇಳಿಯುವ ಸಾಧ್ಯತೆ (₹{p0} → ₹{p1}/ಕ್ವಿಂ). ಬೇಗ ಮಾರುವುದನ್ನು ಪರಿಗಣಿಸಿ."},
    "alert.price_rise": {
        "en": "{crop} at {mandi} rose {pct}% to ₹{price}/qtl.",
        "hi": "{mandi} में {crop} का भाव {pct}% बढ़कर ₹{price}/क्विंटल हुआ।",
        "kn": "{mandi} ನಲ್ಲಿ {crop} ಬೆಲೆ {pct}% ಏರಿ ₹{price}/ಕ್ವಿಂ ಆಗಿದೆ."},
    "alert.price_drop": {
        "en": "{crop} at {mandi} fell {pct}% to ₹{price}/qtl.",
        "hi": "{mandi} में {crop} का भाव {pct}% गिरकर ₹{price}/क्विंटल हुआ।",
        "kn": "{mandi} ನಲ್ಲಿ {crop} ಬೆಲೆ {pct}% ಇಳಿದು ₹{price}/ಕ್ವಿಂ ಆಗಿದೆ."},
    "alert.match": {
        "en": "Buyer found for your {crop}: {qty} qtl at ₹{price}/qtl ({buyer}). Open AgriRoute to accept.",
        "hi": "आपकी फ़सल ({crop}) के लिए खरीदार मिला: {qty} क्विंटल ₹{price}/क्विंटल पर ({buyer})। स्वीकार करने के लिए AgriRoute खोलें।",
        "kn": "ನಿಮ್ಮ {crop}ಗೆ ಖರೀದಿದಾರರು ಸಿಕ್ಕಿದ್ದಾರೆ: {qty} ಕ್ವಿಂ, ₹{price}/ಕ್ವಿಂ ({buyer}). ಒಪ್ಪಿಕೊಳ್ಳಲು AgriRoute ತೆರೆಯಿರಿ."},
    "alert.match_buyer": {
        "en": "New lot matched to your demand: {qty} qtl of {crop} at ₹{price}/qtl, {km} km away.",
        "hi": "आपकी मांग के लिए नया माल मिला: {qty} क्विंटल {crop}, ₹{price}/क्विंटल, {km} किमी दूर।",
        "kn": "ನಿಮ್ಮ ಬೇಡಿಕೆಗೆ ಹೊಸ ಸರಕು: {qty} ಕ್ವಿಂ {crop}, ₹{price}/ಕ್ವಿಂ, {km} ಕಿ.ಮೀ ದೂರ."},
    "alert.deal": {
        "en": "Deal confirmed: {qty} qtl of {crop} at ₹{price}/qtl. You receive ₹{amount}.",
        "hi": "सौदा पक्का: {qty} क्विंटल {crop}, ₹{price}/क्विंटल। आपको ₹{amount} मिलेंगे।",
        "kn": "ಒಪ್ಪಂದ ಖಚಿತ: {qty} ಕ್ವಿಂ {crop}, ₹{price}/ಕ್ವಿಂ. ನಿಮಗೆ ₹{amount} ಸಿಗುತ್ತದೆ."},
    "alert.deal_buyer": {
        "en": "Deal confirmed: {qty} qtl of {crop} at ₹{price}/qtl. You pay ₹{amount} including the platform fee.",
        "hi": "सौदा पक्का: {qty} क्विंटल {crop}, ₹{price}/क्विंटल। प्लेटफ़ॉर्म शुल्क सहित आप ₹{amount} देंगे।",
        "kn": "ಒಪ್ಪಂದ ಖಚಿತ: {qty} ಕ್ವಿಂ {crop}, ₹{price}/ಕ್ವಿಂ. ವೇದಿಕೆ ಶುಲ್ಕ ಸೇರಿ ನೀವು ₹{amount} ಪಾವತಿಸುತ್ತೀರಿ."},
}


def fmt_num(v) -> str:
    """Indian digit grouping: 1234567 -> 12,34,567."""
    if not isinstance(v, (int, float)):
        return str(v)
    neg, n = v < 0, abs(int(round(v)))
    s = str(n)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups + [tail])
    return ("-" if neg else "") + s


def t(key: str, lang: str = "en", **params) -> str:
    lang = lang if lang in LANGS else "en"
    tpl = T.get(key, {}).get(lang) or T.get(key, {}).get("en") or key
    safe = {k: (fmt_num(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and k not in {"pct", "spoil", "km", "qty", "days", "n"} else v)
            for k, v in params.items()}
    try:
        return tpl.format(**safe)
    except (KeyError, IndexError):
        return tpl
