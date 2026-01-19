import math
import requests
import streamlit as st

st.set_page_config(page_title="Afstand & reistijd checker", page_icon="🚌", layout="centered")

# --- Vaste locaties als coördinaten (lat, lon) ---
# (plaatsniveau of exact: jij bepaalt)
LOCATIONS_LL = {
    "Vianen – Hagenweg 3c": (51.9919, 5.0912),
    "Amersfoort – De Stuwdam 5": (52.1561, 5.3878),
    "Woerden – Botnische Golf 24": (52.0867, 4.8833),
}

OSRM_BASE = "https://router.project-osrm.org"  # publieke OSRM demo server

def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Fallback: hemelsbrede afstand in km."""
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    h = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))

@st.cache_data(show_spinner=False)
def geocode_city(query: str):
    """Geocode woonplaats/postcode via OpenStreetMap Nominatim."""
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
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
def route_osrm_km_minutes(from_lat: float, from_lon: float, to_lat: float, to_lon: float):
    """
    Route over wegen + reistijd via OSRM.
    Returns: (km, minutes) of None bij fout.
    """
    # OSRM gebruikt lon,lat volgorde in de URL
    url = f"{OSRM_BASE}/route/v1/driving/{from_lon},{from_lat};{to_lon},{to_lat}"
    params = {
        "overview": "false",
        "alternatives": "false",
        "steps": "false",
        "annotations": "false",
    }
    r = requests.get(url, params=params, timeout=20)
    if r.status_code != 200:
        return None
    data = r.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        return None

    route = data["routes"][0]
    meters = route["distance"]
    seconds = route["duration"]
    km = meters / 1000.0
    minutes = seconds / 60.0
    return km, minutes

def fmt_minutes(mins: float) -> str:
    mins_round = int(round(mins))
    h = mins_round // 60
    m = mins_round % 60
    if h <= 0:
        return f"{m} min"
    return f"{h}u {m:02d}m"

st.title("🚌 Afstand & reistijd checker (woonplaats → 3 locaties)")
st.caption("Anoniem: je voert alleen woonplaats (optioneel postcode) in. Er wordt niets opgeslagen.")

with st.expander("Instellingen", expanded=False):
    max_minutes = st.number_input("Maximale reistijd (min) voor 'OK'", min_value=0, value=45, step=5)
    show_ok = st.checkbox("Toon OK/NIET OK", value=True)
    fallback_to_haversine = st.checkbox("Gebruik hemelsbreed als route niet lukt (fallback)", value=True)

plaats = st.text_input("Woonplaats", placeholder="Bijv. Houten")
postcode = st.text_input("Postcode (optioneel)", placeholder="Bijv. 3992")

if st.button("Bereken route-afstand en reistijd"):
    if not plaats.strip() and not postcode.strip():
        st.warning("Vul minimaal een woonplaats in (postcode is optioneel).")
        st.stop()

    query = ", ".join([p for p in [postcode.strip(), plaats.strip(), "Netherlands"] if p])

    with st.spinner("Even rekenen..."):
        cand_ll = geocode_city(query)

    if cand_ll is None:
        st.error("Ik kon deze woonplaats/postcode niet vinden. Probeer alleen woonplaats, of voeg postcode toe.")
        st.stop()

    clat, clon = cand_ll

    results = []
    route_failures = 0

    for name, (lat, lon) in LOCATIONS_LL.items():
        routed = route_osrm_km_minutes(clat, clon, lat, lon)
        if routed is None:
            route_failures += 1
            if fallback_to_haversine:
                km = haversine_km(clat, clon, lat, lon)
                # ruwe tijdschatting bij fallback: 1.1 min per km (ongeveer 55 km/u gemiddeld)
                minutes = km * 1.1
                results.append((name, km, minutes, "fallback"))
            else:
                results.append((name, None, None, "failed"))
        else:
            km, minutes = routed
            results.append((name, km, minutes, "route"))

    # Filter resultaten die gelukt zijn (of fallback)
    ok_results = [r for r in results if r[1] is not None]
    if not ok_results:
        st.error("Geen routes kunnen berekenen (OSRM). Probeer later opnieuw of zet fallback aan.")
        st.stop()

    ok_results.sort(key=lambda x: x[2])  # sorteer op reistijd (meestal eerlijker dan km)
    closest_name, closest_km, closest_min, closest_kind = ok_results[0]

    st.subheader("Resultaat (gesorteerd op reistijd)")
    st.write(f"**Beste match:** {closest_name} — **{closest_km:.1f} km** — **{fmt_minutes(closest_min)}**")

    if route_failures > 0:
        st.info(f"Let op: {route_failures} route(s) konden niet via OSRM berekend worden. "
                f"{'Er is hemelsbreed (fallback) gebruikt.' if fallback_to_haversine else 'Geen fallback gebruikt.'}")

    st.divider()

    for name, km, minutes, kind in ok_results:
        line = f"**{name}**: {km:.1f} km — {fmt_minutes(minutes)}"
        if kind == "fallback":
            line += " _(fallback)_"
        if show_ok:
            line += "  ✅" if minutes <= max_minutes else "  ❌"
        st.write(line)

    st.caption(
        "Reistijd is een schatting op basis van een route-model (geen live verkeer). "
        "Dat betekent: het kan per tijdstip verschillen, maar het is wél veel realistischer dan hemelsbreed."
    )
