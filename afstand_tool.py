import math
import requests
import streamlit as st

st.set_page_config(page_title="ATS-light Recruitment Tool", page_icon="🚌", layout="centered")

# -----------------------------
# LOCATIES
# -----------------------------
POUW_LOCATIONS = {
    "Vianen": (51.9919, 5.0912),
    "Amersfoort": (52.1561, 5.3878),
    "Woerden": (52.0867, 4.8833),
}

BUSINEXT_LOCATIONS = {
    "Schiphol": (52.3105, 4.7683),
    "Wateringen": (52.0100, 4.2760),
    "Almere": (52.3508, 5.2647),
    "Dirksland": (51.7495, 4.1058),
    "Renesse": (51.7324, 3.7749),
    "Middelburg": (51.4988, 3.6100),
    "Bergen op Zoom": (51.4950, 4.2915),
    "Breda": (51.5719, 4.7683),
    "Oosterhout": (51.6450, 4.8597),
    "Waalwijk": (51.6826, 5.0700),
    "Deurne": (51.4519, 5.7882),
    "Gemert": (51.5555, 5.6906),
    "Heerlen": (50.8882, 5.9795),
}

# -----------------------------
# HELPERS
# -----------------------------
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def score_pouw(km):
    if km <= 20: return 100
    if km <= 40: return 80
    if km <= 60: return 60
    if km <= 80: return 30
    return 0


def score_businext(km):
    if km <= 10: return 100
    if km <= 25: return 90
    if km <= 40: return 75
    return 0


@st.cache_data(show_spinner=False)
def geocode_city(query):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": query, "format": "json", "limit": 1, "countrycodes": "nl"}
    headers = {"User-Agent": "ATS-Recruitment-Tool/1.0"}

    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        if not data:
            return None
        return float(data[0]["lat"]), float(data[0]["lon"])
    except:
        return None


# -----------------------------
# UI
# -----------------------------
st.title("🧠 ATS-light Recruitment Score Tool")
st.caption("Pouw + Businext match + score + advies")

plaats = st.text_input("Woonplaats kandidaat")

if st.button("Analyseer kandidaat"):

    if not plaats.strip():
        st.warning("Vul een woonplaats in")
        st.stop()

    with st.spinner("Analyseren..."):
        cand = geocode_city(f"{plaats}, Netherlands")

    if cand is None:
        st.error("Woonplaats niet gevonden")
        st.stop()

    lat, lon = cand

    # -------------------------
    # POUW ANALYSE
    # -------------------------
    pouw_results = []
    for name, (plat, plon) in POUW_LOCATIONS.items():
        km = haversine_km(lat, lon, plat, plon)
        pouw_results.append((name, km))

    best_pouw, best_pouw_km = min(pouw_results, key=lambda x: x[1])
    pouw_score = score_pouw(best_pouw_km)

    # -------------------------
    # BUSINEXT ANALYSE
    # -------------------------
    businext_hits = []
    businext_scores = []

    for name, (b_lat, b_lon) in BUSINEXT_LOCATIONS.items():
        km = haversine_km(lat, lon, b_lat, b_lon)
        score = score_businext(km)

        if score > 0:
            businext_hits.append((name, km))
            businext_scores.append(score)

    businext_score = max(businext_scores) if businext_scores else 0

    # -------------------------
    # MATCH TYPE
    # -------------------------
    if pouw_score >= 80 and businext_score > 0:
        match = "🟣 OVERLAP"
    elif pouw_score >= 80:
        match = "🟢 POUW"
    elif businext_score > 0:
        match = "🔵 BUSINEXT"
    else:
        match = "🔴 NO MATCH"

    # -------------------------
    # EIND SCORE
    # -------------------------
    final_score = max(pouw_score, businext_score)

    # -------------------------
    # OUTPUT
    # -------------------------
    st.subheader("📊 Resultaat")

    st.write(f"**Beste Pouw locatie:** {best_pouw} ({best_pouw_km:.1f} km)")
    st.write(f"**Pouw score:** {pouw_score}/100")

    st.divider()

    st.write(f"**Businext score:** {businext_score}/100")

    if businext_hits:
        st.write("**Businext matches:**")
        for name, km in sorted(businext_hits, key=lambda x: x[1]):
            st.write(f"- {name}: {km:.1f} km")

    st.divider()

    st.subheader("🎯 Recruitersadvies")
    st.write(f"**Matchtype:** {match}")
    st.write(f"**Eindscore:** {final_score}/100")

    if match == "🟣 OVERLAP":
        st.success("➡️ Eerst Pouw beoordelen, anders doorzetten naar Businext")

    elif match == "🟢 POUW":
        st.success("➡️ Uitnodigen voor kennismaking (Pouw)")

    elif match == "🔵 BUSINEXT":
        st.info("➡️ Doorverwijzen naar Businext")

    else:
        st.error("➡️ Niet geschikt op basis van afstand")

    st.caption("ATS-light scoring (op basis van hemelsbrede afstand + vaste thresholds)")