import math
import time
import requests
import streamlit as st

st.set_page_config(page_title="Afstand checker (woonplaats)", page_icon="🚌", layout="centered")

# --- Vaste locaties (Pouw) ---
# Tip: als een adres niet gevonden wordt, voeg postcode/plaats toe.
LOCATIONS = {
    "Vianen – Hagenweg 3c": "Hagenweg 3c, 4131 LX Vianen, Netherlands",
    "Amersfoort – De Stuwdam 5": "De Stuwdam 5, 3825 KP Amersfoort, Netherlands",
    "Woerden – Botnische Golf 24": "Botnische Golf 24, Woerden, Netherlands",
}

# --- Helpers ---
def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Hemelsbrede afstand in km."""
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    h = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))

@st.cache_data(show_spinner=False)
def geocode(address: str):
    """
    Geocode via OpenStreetMap Nominatim.
    Let op: dit stuurt de woonplaats/postcode (geen naam) naar Nominatim om coords op te halen.
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": address,
        "format": "json",
        "limit": 1,
        "countrycodes": "nl",
    }
    headers = {"User-Agent": "Pouw-Afstand-Checker/1.0"}

    r = requests.get(url, params=params, headers=headers, timeout=20)
    r.raise_for_status()
    data = r.json()
    if not data:
        return None
    return float(data[0]["lat"]), float(data[0]["lon"])

@st.cache_data(show_spinner=False)
def geocode_locations():
    """Geocode vaste locaties. Geeft ook terug welke locaties (nog) niet gevonden worden."""
    loc_ll = {}
    failures = []
    for name, addr in LOCATIONS.items():
        ll = geocode(addr)
        time.sleep(1.0)  # beleefd richting Nominatim
        if ll is None:
            failures.append((name, addr))
        else:
            loc_ll[name] = ll
    return loc_ll, failures

# --- UI ---
st.title("🚌 Afstand checker (woonplaats → 3 locaties)")
st.caption("Anoniem: je voert alleen woonplaats (optioneel postcode) in. Deze app slaat niets op.")

with st.expander("Instellingen", expanded=False):
    max_km = st.number_input("Maximale afstand (km) voor 'OK'", min_value=0.0, value=35.0, step=1.0)
    show_ok = st.checkbox("Toon OK/NIET OK", value=True)

plaats = st.text_input("Woonplaats", placeholder="Bijv. Houten")
postcode = st.text_input("Postcode (optioneel)", placeholder="Bijv. 3992")

if st.button("Bereken afstanden"):
    if not plaats.strip() and not postcode.strip():
        st.warning("Vul minimaal een woonplaats in (postcode is optioneel).")
        st.stop()

    query = ", ".join([p for p in [postcode.strip(), plaats.strip(), "Netherlands"] if p])

    with st.spinner("Even rekenen..."):
        cand_ll = geocode(query)
        loc_ll, failures = geocode_locations()

    if failures:
        st.error("Ik kan (nog) niet alle vaste locaties vinden bij OpenStreetMap.")
        for name, addr in failures:
            st.write(f"❌ **{name}** — {addr}")
        st.info(
            "Oplossing: controleer de spelling van het adres, of voeg postcode/plaats toe in LOCATIONS. "
            "Als je wilt, kan je ook vaste coördinaten (lat/lon) gebruiken zodat dit nooit meer fout gaat."
        )
        st.stop()

    if cand_ll is None:
        st.error("Ik kon deze woonplaats/postcode niet vinden. Probeer alleen woonplaats, of voeg postcode toe.")
        st.stop()

    clat, clon = cand_ll

    results = []
    for name, (lat, lon) in loc_ll.items():
        km = haversine_km(clat, clon, lat, lon)
        results.append((name, km))

    results.sort(key=lambda x: x[1])
    closest_name, closest_km = results[0]

    st.subheader("Resultaat")
    st.write(f"**Dichtstbij:** {closest_name} — **{closest_km:.1f} km**")
    st.divider()

    for name, km in results:
        line = f"**{name}**: {km:.1f} km"
        if show_ok:
            line += "  ✅" if km <= max_km else "  ❌"
        st.write(line)

    st.caption("Let op: dit is hemelsbrede afstand. Reistijd kan in de praktijk afwijken.")
