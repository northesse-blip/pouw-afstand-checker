import math
import time
import requests
import streamlit as st

st.set_page_config(page_title="Afstand & reistijd checker", page_icon="🚌", layout="centered")

# --- Vaste locaties als coördinaten (lat, lon) ---
LOCATIONS_LL = {
    "Vianen – Hagenweg 3c": (51.9919, 5.0912),
    "Amersfoort – De Stuwdam 5": (52.1561, 5.3878),
    "Woerden – Botnische Golf 24": (52.0867, 4.8833),
}

# Publieke OSRM demo-router
OSRM_BASE = "https://router.project-osrm.org"

# ---------- Helpers ----------
def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Hemelsbrede afstand in km (fallback)."""
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    h = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))

def fmt_minutes(mins: float) -> str:
    mins_round = int(round(mins))
    h = mins_round // 60
    m = mins_round % 60
    return f"{m} min" if h <= 0 else f"{h}u {m:02d}m"

def safe_get(url, *, params=None, headers=None, timeout=20, retries=3, backoff=1.0):
    """
    Requests GET met retries + simpele backoff.
    Geeft response terug of None als het steeds faalt.
    """
    last_err = None
    for i in range(retries):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=timeout)
            return r
        except requests.exceptions.RequestException as e:
            last_err = e
            time.sleep(backoff * (i + 1))
    return None

# ---------- Geocoding (Nominatim) ----------
@st.cache_data(show_spinner=False)
def geocode_city(query: str):
    """
    Geocode woonplaats/postcode via OSM Nominatim.
    Retourneert (lat, lon) of None.
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": query, "format": "json", "limit": 1, "countrycodes": "nl"}
    headers = {"User-Agent": "Pouw-Afstand-Checker/1.0"}

    r = safe_get(url, params=params, headers=headers, timeout=20, retries=3, backoff=1.2)
    if r is None:
        return None  # netwerk issue / rate limit / tijdelijk down

    if r.status_code != 200:
        return None

    data = r.json()
    if not data:
        return None

    return float(data[0]["lat"]), float(data[0]["lon"])

# ---------- Routing (OSRM) ----------
@st.cache_data(show_spinner=False)
def route_osrm_km_minutes(from_lat: float, from_lon: float, to_lat: float, to_lon: float):
    """
    Route over wegen + reistijd via OSRM.
    Returns (km, minutes) of None.
    """
    url = f"{OSRM_BASE}/route/v1/driving/{from_lon},{from_lat};{to_lon},{to_lat}"
    params = {"overview": "false", "alternatives": "false", "steps": "false"}

    r = safe_get(url, params=params, timeout=20, retries=3, backoff=1.0)
    if r is None or r.status_code != 200:
        return None

    data = r.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        return None

    route = data["routes"][0]
    km = route["distance"] / 1000.0
    minutes = route["duration"] / 60.0
    return km, minutes

# ---------- UI ----------
st.title("🚌 Afstand & reistijd checker (woonplaats → 3 locaties)")
st.caption("Anoniem: geen namen. Alleen woonplaats/postcode of coördinaten. De app slaat niets op.")

with st.expander("Instellingen", expanded=False):
    max_minutes = st.number_input("Maximale reistijd (min) voor 'OK'", min_value=0, value=45, step=5)
    show_ok = st.checkbox("Toon OK/NIET OK", value=True)
    fallback_to_haversine = st.checkbox("Gebruik hemelsbreed als route niet lukt (fallback)", value=True)

st.subheader("Invoer")
mode = st.radio(
    "Hoe wil je invoeren?",
    ["Woonplaats / postcode", "Coördinaten (lat/lon)"],
    horizontal=True
)

cand_ll = None

if mode == "Woonplaats / postcode":
    plaats = st.text_input("Woonplaats", placeholder="Bijv. Houten")
    postcode = st.text_input("Postcode (optioneel)", placeholder="Bijv. 3992")
else:
    lat_str = st.text_input("Latitude", placeholder="Bijv. 52.028")
    lon_str = st.text_input("Longitude", placeholder="Bijv. 5.168")

if st.button("Bereken route-afstand en reistijd"):
    # 1) Kandidaten-coords bepalen
    if mode == "Woonplaats / postcode":
        if not plaats.strip() and not postcode.strip():
            st.warning("Vul minimaal een woonplaats in (postcode is optioneel).")
            st.stop()

        query = ", ".join([p for p in [postcode.strip(), plaats.strip(), "Netherlands"] if p])

        with st.spinner("Woonplaats zoeken..."):
            cand_ll = geocode_city(query)

        if cand_ll is None:
            st.error(
                "Ik krijg nu geen betrouwbare verbinding met de geocode-service (OpenStreetMap) "
                "of deze woonplaats werd niet gevonden.\n\n"
                "Probeer opnieuw, voeg postcode toe, of kies hierboven 'Coördinaten (lat/lon)'."
            )
            st.stop()

    else:
        try:
            clat = float(lat_str.strip().replace(",", "."))
            clon = float(lon_str.strip().replace(",", "."))
            cand_ll = (clat, clon)
        except Exception:
            st.error("Vul geldige coördinaten in, bijv. 52.028 en 5.168")
            st.stop()

    clat, clon = cand_ll

    # 2) Routes berekenen
    with st.spinner("Routes berekenen..."):
        results = []
        route_failures = 0

        for name, (lat, lon) in LOCATIONS_LL.items():
            routed = route_osrm_km_minutes(clat, clon, lat, lon)

            if routed is None:
                route_failures += 1
                if fallback_to_haversine:
                    km = haversine_km(clat, clon, lat, lon)
                    # ruwe fallback tijd: ~55 km/u gemiddeld
                    minutes = km * 1.1
                    results.append((name, km, minutes, "fallback"))
                else:
                    results.append((name, None, None, "failed"))
            else:
                km, minutes = routed
                results.append((name, km, minutes, "route"))

    ok_results = [r for r in results if r[1] is not None]
    if not ok_results:
        st.error("Geen routes konden worden berekend (OSRM). Probeer later opnieuw of zet fallback aan.")
        st.stop()

    # Sorteren op reistijd (eerlijker dan km)
    ok_results.sort(key=lambda x: x[2])

    best_name, best_km, best_min, best_kind = ok_results[0]

    st.subheader("Resultaat (gesorteerd op reistijd)")
    st.write(f"**Beste match:** {best_name} — **{best_km:.1f} km** — **{fmt_minutes(best_min)}**")
    if show_ok:
        st.write("**Uitnodigen:** " + ("✅ JA" if best_min <= max_minutes else "❌ NEE"))

    if route_failures > 0:
        st.info(
            f"Let op: {route_failures} route(s) konden niet via OSRM berekend worden. "
            f"{'Fallback (hemelsbreed) is gebruikt.' if fallback_to_haversine else 'Geen fallback gebruikt.'}"
        )

    st.divider()
    for name, km, minutes, kind in ok_results:
        line = f"**{name}**: {km:.1f} km — {fmt_minutes(minutes)}"
        if kind == "fallback":
            line += " _(fallback)_"
        if show_ok:
            line += "  ✅" if minutes <= max_minutes else "  ❌"
        st.write(line)

    st.caption(
        "Reistijd is een schatting op basis van een route-model (zonder live verkeer). "
        "In de spits kan het afwijken, maar het is veel realistischer dan hemelsbreed."
    )
