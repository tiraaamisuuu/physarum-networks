# Frozen London geographic inputs

`geography.json` is a derived geographic database for the exploratory London example, retrieved on 17 November 2026. It is bundled for offline, reproducible use. The repository's software MIT licence does **not** replace the source data licences below.

| Layer | Source and attribution | Licence / terms |
| --- | --- | --- |
| 272 station entries | [TfL Unified API: Tube StopPoints](https://api.tfl.gov.uk/StopPoint/Mode/tube). Contains Transport for London data. Filter: `stopType=NaptanMetroStation`, ID prefix `940G`. | [TfL Transport Data Service terms](https://tfl.gov.uk/corporate/terms-and-conditions/transport-data-service) |
| 27 Thames river ways | © OpenStreetMap contributors. Overpass query for river ways named Thames within `(51.45,-0.25,51.57,0.05)`; way IDs retained. EU public mirror: `ovp.dresel.systems`. | [Open Database Licence 1.0 and attribution](https://www.openstreetmap.org/copyright). The derived OSM layer remains under ODbL; it is separately identifiable as `river`. |
| 247 elevation samples | Copernicus DEM 2021 GLO-90 ([data DOI](https://doi.org/10.5270/ESA-c5d3d65)), distributed by [Open-Meteo Elevation API](https://open-meteo.com/en/docs/elevation-api). | [Open-Meteo CC BY 4.0 attribution terms](https://open-meteo.com/en/terms) and Copernicus source attribution described in the API documentation. |

The JSON preserves request URLs, SHA-256 hashes of raw responses, retrieval time, attribution and licence links. This combined collection preserves each separately identifiable source layer's terms. Neither TfL, OpenStreetMap nor Open-Meteo endorses this project. No official Tube map artwork is included.

Station longitude/latitude was transformed with pyproj 3.8.0 to British National Grid EPSG:27700. Coordinates are stored in kilometres; the transformation operation and its advertised accuracy are recorded. That figure describes the coordinate operation, not station-location or tunnel-alignment accuracy.

The 46 default station IDs are explicitly selected in `analysis/fetch_london_data.py`; the subset is an example, not the whole Tube system. Hammersmith and Shepherd's Bush select particular TfL station entries. The Thames layer is a centreline, not river banks or tunnel geometry. Bounds are enforced by the application to avoid using missing river coverage as evidence of no crossing.

Elevation is sampled on a 19×13 projected grid spanning the default stations plus a 1 km margin. Its sample spacing is much coarser than the source DEM's nominal resolution and is recorded in the JSON. It is displayed as sampled context only, without affecting any cost. The application does not infer subsurface geology or tunnelling difficulty from it.

To reconstruct the frozen file using cached raw responses, run `.venv/bin/python analysis/fetch_london_data.py`. Raw caches live under ignored `tmp/london/`. To deliberately fetch current source data, add `--refresh`; review the diff, provenance, coverage and tests before adopting the new snapshot. Provider responses may change. Normal launch and tests do not call these APIs.
