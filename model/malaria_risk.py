"""Malaria-risk tier classifier for Trellis.

This module turns the environmental forecast (rainfall, temperature) into a
likely / possible / watch tier specifically for malaria, distinct from the
generic environmental alert tier.

Methodological lineage
----------------------
The thresholds used here follow the EPIDEMIA / Wimberly et al. (Ethiopia)
tradition of environmental-driver malaria-risk forecasting:

  * Rainfall: too dry, no breeding habitat. Too wet, larvae are flushed.
    Optimal monthly rainfall for breeding sites is roughly 50-300 mm,
    with the strongest signal when monthly rainfall is moderately above
    seasonal climatology (i.e. recent wetting events that create new
    standing water without flushing it away).

  * Temperature: Plasmodium falciparum extrinsic incubation period (EIP)
    is shortest at 22-30 deg C. Below 18 deg C development effectively
    stops; above 33 deg C vector mortality rises sharply. Mosquito
    survival peaks in the 22-28 deg C range.

References:
  - Wimberly MC et al. (2016). Spatio-temporal modeling of malaria
    incidence... Journal of Health Geographics.
  - WHO (2003). Climate change and human health: risks and responses.
  - Reiter P. (2008). Climate change and mosquito-borne disease.
    Environmental Health Perspectives 109(S1).

Important framing
-----------------
This module produces an *environmental risk* classification, not a case
incidence forecast. We claim "this ward has an environment conducive to
malaria transmission this month". To make incidence claims we would need
DHIS2 surveillance case data integrated as the eighth predictor. That is
explicitly an open question in trellis.md.
"""

from __future__ import annotations

# -- Threshold parameters (constants kept here so they're reviewable) --

# Rainfall (mm per month)
RAIN_MIN_OPTIMAL = 50.0  # below this, breeding habitat is too sparse
RAIN_MAX_OPTIMAL = 300.0  # above this, larvae flushing dominates
RAIN_MIN_ACCEPTABLE = 30.0  # extended range, partial breeding possible
RAIN_MAX_ACCEPTABLE = 400.0  # extended range, partial flushing
RAIN_HIGH_SIGNAL = 100.0  # strong recent wetting threshold

# Temperature (deg C, monthly mean)
TEMP_MIN_OPTIMAL = 22.0  # below this, EIP becomes very long
TEMP_MAX_OPTIMAL = 30.0  # above this, vector mortality climbs
TEMP_MIN_ACCEPTABLE = 18.0  # extended range
TEMP_MAX_ACCEPTABLE = 33.0  # extended range


def classify_malaria_risk(
    rainfall_mm: float | None,
    temperature_c: float | None,
    rainfall_climatology_mm: float | None = None,
) -> str:
    """Return one of 'likely', 'possible', 'watch' for malaria transmission risk.

    Parameters
    ----------
    rainfall_mm : forecast or observed monthly rainfall in millimetres.
    temperature_c : forecast or observed monthly mean temperature in deg C.
    rainfall_climatology_mm : optional same-month climatological mean. If
        provided, "wetter than climatology" is used as a tie-breaker for
        the high-signal flag.

    Returns
    -------
    str : 'likely' | 'possible' | 'watch'
    """
    # Defensive: with neither input available, return watch (no judgement)
    if rainfall_mm is None or temperature_c is None:
        return "watch"

    rain_optimal = RAIN_MIN_OPTIMAL <= rainfall_mm <= RAIN_MAX_OPTIMAL
    rain_acceptable = RAIN_MIN_ACCEPTABLE <= rainfall_mm <= RAIN_MAX_ACCEPTABLE
    temp_optimal = TEMP_MIN_OPTIMAL <= temperature_c <= TEMP_MAX_OPTIMAL
    temp_acceptable = TEMP_MIN_ACCEPTABLE <= temperature_c <= TEMP_MAX_ACCEPTABLE

    # High-signal: rainfall above 100mm AND, if climatology known, above climatology
    high_signal = rainfall_mm >= RAIN_HIGH_SIGNAL
    if rainfall_climatology_mm is not None:
        high_signal = high_signal and (rainfall_mm > rainfall_climatology_mm)

    # Likely: optimal rain AND optimal temp AND high-signal wetting
    if rain_optimal and temp_optimal and high_signal:
        return "likely"

    # Possible: at least one optimal, the other acceptable
    if (rain_optimal and temp_acceptable) or (temp_optimal and rain_acceptable):
        return "possible"

    # Watch: anything else
    return "watch"


def explain_classification(
    rainfall_mm: float | None,
    temperature_c: float | None,
    rainfall_climatology_mm: float | None = None,
) -> str:
    """Return a one-line human-readable rationale for the tier."""
    tier = classify_malaria_risk(rainfall_mm, temperature_c, rainfall_climatology_mm)
    if rainfall_mm is None or temperature_c is None:
        return f"{tier}: insufficient environmental data"
    parts = []
    if RAIN_MIN_OPTIMAL <= rainfall_mm <= RAIN_MAX_OPTIMAL:
        parts.append(f"rainfall {rainfall_mm:.0f}mm in optimal breeding range")
    elif RAIN_MIN_ACCEPTABLE <= rainfall_mm <= RAIN_MAX_ACCEPTABLE:
        parts.append(f"rainfall {rainfall_mm:.0f}mm in extended acceptable range")
    else:
        parts.append(f"rainfall {rainfall_mm:.0f}mm outside acceptable range")
    if TEMP_MIN_OPTIMAL <= temperature_c <= TEMP_MAX_OPTIMAL:
        parts.append(f"temperature {temperature_c:.1f}C optimal for parasite development")
    elif TEMP_MIN_ACCEPTABLE <= temperature_c <= TEMP_MAX_ACCEPTABLE:
        parts.append(f"temperature {temperature_c:.1f}C in extended range")
    else:
        parts.append(f"temperature {temperature_c:.1f}C outside acceptable range")
    return f"{tier}: " + "; ".join(parts)


if __name__ == "__main__":
    # Quick manual sanity check
    cases = [
        (180, 27, 120, "should be likely"),
        (250, 26, 200, "should be likely"),
        (40, 28, 100, "should be possible (rain below optimal)"),
        (350, 31, 200, "should be possible or watch"),
        (10, 35, 50, "should be watch (both extremes)"),
        (None, 27, None, "should be watch (missing data)"),
    ]
    for rain, temp, climo, comment in cases:
        result = classify_malaria_risk(rain, temp, climo)
        print(f"  rain={rain} temp={temp} climo={climo} -> {result}  ({comment})")
        if rain is not None and temp is not None:
            print(f"    {explain_classification(rain, temp, climo)}")
