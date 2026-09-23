"""
Builds the published static site (docs/index.html) from the notebook's
outputs: docs/flood_extent.geojson (SAR-derived flood polygon),
docs/roads_exposed.geojson, docs/buildings_flooded.geojson, docs/aoi.geojson.

Entirely vector (GeoJSON) - no raster imagery, no client-side decoding, no
lazy-loading tricks needed. Total data payload is under 400KB, so
everything loads on page load, same as any other small web map.

Usage:
    python build_static_site.py
"""

import os

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(os.path.dirname(DATA_DIR), "docs")

CENTER = [47.6378, -121.9023]

PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>King County Flood Infrastructure Exposure (Demo)</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css">
<style>
  :root {{
    --bg: #ffffff; --ink: #1a1a1a; --muted: #5b5f66; --border: #e2e4e8;
    --surface: #f6f7f9; --accent: #2563a8; --flood: #2563a8; --road: #c1440e; --building: #a8322d;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #0e1117; --ink: #e6e8eb; --muted: #9aa1ab; --border: #2a2e35;
      --surface: #161a21; --accent: #5b9bd9; --flood: #5b9bd9; --road: #e8794a; --building: #d9615c;
    }}
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ height: 100%; margin: 0; }}
  body {{
    display: flex; flex-direction: column; background: var(--bg); color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  }}
  header {{ padding: 16px clamp(16px, 4vw, 32px) 0; }}
  h1 {{ margin: 0 0 4px; font-size: 1.4rem; }}
  .caption {{ color: var(--muted); margin: 0 0 12px; font-size: 0.9rem; }}
  .tabs {{ display: flex; gap: 20px; border-bottom: 1px solid var(--border); padding: 0 clamp(16px, 4vw, 32px); }}
  .tab-btn {{ background: none; border: none; padding: 10px 0; font-size: 15px; color: var(--muted); cursor: pointer; border-bottom: 2px solid transparent; }}
  .tab-btn.active {{ color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }}
  #tab-map {{ flex: 1 1 auto; min-height: 0; display: none; position: relative; }}
  #tab-map.active {{ display: block; }}
  #map {{ height: 100%; width: 100%; }}
  #tab-about {{ display: none; padding: 16px clamp(16px, 4vw, 32px) 48px; overflow-y: auto; }}
  #tab-about.active {{ display: block; }}
  .controls {{
    position: absolute; top: 12px; right: 12px; z-index: 1000; background: var(--surface);
    border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; font-size: 13px;
    max-width: 260px; max-height: calc(100% - 24px); overflow-y: auto;
  }}
  .controls label {{ display: flex; align-items: center; gap: 8px; margin: 6px 0; }}
  .swatch {{ width: 14px; height: 14px; border-radius: 3px; flex: none; }}
  .stat-row {{ display: flex; justify-content: space-between; font-size: 12px; color: var(--muted); margin: 2px 0; }}
  .stat-num {{ color: var(--ink); font-weight: 600; }}
  hr.sep {{ border: none; border-top: 1px solid var(--border); margin: 10px 0; }}
  code {{ background: var(--surface); padding: 1px 5px; border-radius: 4px; font-size: 0.9em; }}
  a {{ color: var(--accent); }}
  .inspect-popup {{ font-size: 12.5px; line-height: 1.6; }}
  .badge {{ display: inline-block; font-size: 11px; padding: 2px 7px; border-radius: 100px; font-weight: 600; }}
  .badge.confirmed {{ background: #dcecdd; color: #1c6b30; }}
  .badge.missed {{ background: #f3dede; color: #9c3030; }}
  @media (prefers-color-scheme: dark) {{
    .badge.confirmed {{ background: #16321d; color: #7fd196; }}
    .badge.missed {{ background: #3a1d1d; color: #e08b8b; }}
  }}
</style>
</head>
<body>
  <header>
    <h1>King County Flood Infrastructure Exposure (Demo)</h1>
    <p class="caption">Which roads and buildings fell inside the March 17-21, 2026 Snoqualmie/Tolt flood extent - see the About tab for method and honest limitations.</p>
    <div class="tabs">
      <button class="tab-btn active" data-tab="map">Map</button>
      <button class="tab-btn" data-tab="about">About</button>
    </div>
  </header>

  <div id="tab-map" class="active">
    <div id="map"></div>
    <div class="controls">
      <strong>Layers</strong>
      <label><input type="checkbox" id="toggle-flood" checked><span class="swatch" style="background:var(--flood);opacity:0.45"></span>Flood extent (SAR)</label>
      <label><input type="checkbox" id="toggle-roads" checked><span class="swatch" style="background:var(--road)"></span>Exposed roads</label>
      <label><input type="checkbox" id="toggle-buildings" checked><span class="swatch" style="background:var(--building)"></span>Exposed buildings</label>
      <hr class="sep">
      <div class="stat-row"><span>Flood extent</span><span class="stat-num">{flood_area_km2} sq km</span></div>
      <div class="stat-row"><span>Roads exposed</span><span class="stat-num">{road_count} segments</span></div>
      <div class="stat-row"><span>Buildings exposed</span><span class="stat-num">{building_count}</span></div>
      <hr class="sep">
      <div style="font-size:11px;color:var(--muted)">Click any flood polygon, road, or building for details.</div>
    </div>
  </div>

  <div id="tab-about">{about_html}</div>

<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
  document.querySelectorAll(".tab-btn").forEach(function (btn) {{
    btn.addEventListener("click", function () {{
      document.querySelectorAll(".tab-btn").forEach(function (b) {{ b.classList.remove("active"); }});
      document.querySelectorAll("#tab-map, #tab-about").forEach(function (p) {{ p.classList.remove("active"); }});
      btn.classList.add("active");
      document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
      if (btn.dataset.tab === "map") {{ setTimeout(function () {{ map.invalidateSize(); }}, 50); }}
    }});
  }});

  const CENTER = {center_json};
  const map = L.map("map", {{ zoomSnap: 0.25 }}).setView(CENTER, 12);
  L.control.scale({{ metric: true, imperial: true }}).addTo(map);

  L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}", {{
    maxZoom: 19,
    attribution: "Imagery &copy; Esri &mdash; Esri, Maxar, Earthstar Geographics, and the GIS User Community",
  }}).addTo(map);

  const rootStyle = getComputedStyle(document.documentElement);
  const floodColor = rootStyle.getPropertyValue("--flood").trim();
  const roadColor = rootStyle.getPropertyValue("--road").trim();
  const buildingColor = rootStyle.getPropertyValue("--building").trim();

  let floodLayer, roadsLayer, buildingsLayer;

  fetch("flood_extent.geojson").then(function (r) {{ return r.json(); }}).then(function (gj) {{
    floodLayer = L.geoJSON(gj, {{
      style: {{ fillColor: floodColor, fillOpacity: 0.45, color: floodColor, weight: 1 }},
    }}).bindPopup("SAR-derived flood extent (Mar 13 vs Mar 20, 2026)");
    if (document.getElementById("toggle-flood").checked) floodLayer.addTo(map);
  }});

  fetch("roads_exposed.geojson").then(function (r) {{ return r.json(); }}).then(function (gj) {{
    roadsLayer = L.geoJSON(gj, {{
      style: {{ color: roadColor, weight: 4, opacity: 0.9 }},
      onEachFeature: function (feature, layer) {{
        const p = feature.properties;
        const name = p.FULLNAME_L || p.FULLNAME_R || "Unnamed road";
        layer.bindPopup("<div class=\\"inspect-popup\\"><b>" + name + "</b><br>Intersects derived flood extent</div>");
      }},
    }});
    if (document.getElementById("toggle-roads").checked) roadsLayer.addTo(map);
  }});

  fetch("buildings_flooded.geojson").then(function (r) {{ return r.json(); }}).then(function (gj) {{
    buildingsLayer = L.geoJSON(gj, {{
      style: {{ fillColor: buildingColor, fillOpacity: 0.75, color: buildingColor, weight: 1 }},
      onEachFeature: function (feature, layer) {{
        layer.bindPopup("<div class=\\"inspect-popup\\">Building footprint<br>Intersects derived flood extent<br><span style=\\"color:#888\\">Source: Overture Maps</span></div>");
      }},
    }});
    if (document.getElementById("toggle-buildings").checked) buildingsLayer.addTo(map);
  }});

  document.getElementById("toggle-flood").addEventListener("change", function (e) {{
    if (!floodLayer) return;
    e.target.checked ? floodLayer.addTo(map) : map.removeLayer(floodLayer);
  }});
  document.getElementById("toggle-roads").addEventListener("change", function (e) {{
    if (!roadsLayer) return;
    e.target.checked ? roadsLayer.addTo(map) : map.removeLayer(roadsLayer);
  }});
  document.getElementById("toggle-buildings").addEventListener("change", function (e) {{
    if (!buildingsLayer) return;
    e.target.checked ? buildingsLayer.addTo(map) : map.removeLayer(buildingsLayer);
  }});
</script>
</body>
</html>
"""


def main() -> None:
    import json

    import geopandas as gpd

    flood = gpd.read_file(os.path.join(DOCS_DIR, "flood_extent.geojson"))
    roads = gpd.read_file(os.path.join(DOCS_DIR, "roads_exposed.geojson"))
    buildings = gpd.read_file(os.path.join(DOCS_DIR, "buildings_flooded.geojson"))

    flood_area_km2 = round(flood.to_crs(32610).geometry.area.sum() / 1e6, 1)
    road_count = len(roads)
    building_count = len(buildings)

    about_html = f"""
    <h2>What this is</h2>
    <p>An independent estimate of which roads and buildings fell inside the
    flood extent of the March 17-21, 2026 King County flood, based on real
    <a href="https://kingcountyfloodcontrol.org/march-17-21-2026-flood-event-report/" target="_blank" rel="noopener">King County Flood Control District event report</a>
    - the Snoqualmie and Tolt Rivers both reached Phase 3 (the report's
    highest alert level), making the Snoqualmie Valley / Tolt River
    confluence (Fall City - Carnation - Duvall) the most severely affected
    area in the county.</p>

    <h2>Exposure, not visual damage</h2>
    <p>No confirmed very-high-resolution imagery source was available for
    this specific event (no Maxar Open Data Program activation found for
    it). At Sentinel's 10m resolution, a washed-out road and a
    merely-flooded-but-intact road look identical - so this map answers a
    narrower, honest question: <strong>which specific roads and buildings
    fell inside the derived flood extent</strong>, not whether any
    individual structure was actually damaged.</p>

    <h2>Method, briefly (full detail in the notebook)</h2>
    <p>Flood extent comes from Sentinel-1 SAR: a backscatter-drop comparison
    between March 13 (pre-event) and March 20 (during the event - the only
    cloud-proof way to see standing water mid-storm) on the same descending
    orbit. The river channel visibly widens into a smooth, radar-dark band
    during the event - a direct visual signal, not just a threshold
    artifact. The raster mask was converted to clean polygons using
    <a href="https://github.com/opengeos/geoai" target="_blank" rel="noopener">geoai</a>'s
    <code>raster_to_vector()</code>. The flood extent is then spatially
    joined against real King County road data and
    <a href="https://overturemaps.org/" target="_blank" rel="noopener">Overture Maps</a>
    building footprints.</p>

    <h2>A real, free validation check</h2>
    <p>The flood report names specific roads it observed affected. The
    flood extent above was derived purely from satellite backscatter, with
    no reference to that list during detection - checking whether it
    independently covers those same roads is a real accuracy check, not a
    plausibility argument:</p>
    <p>
      <span class="badge confirmed">CONFIRMED</span> SE Reinig Rd &middot;
      <span class="badge confirmed">CONFIRMED</span> Meadowbrook Way SE &middot;
      <span class="badge confirmed">CONFIRMED</span> SE Mill Pond Rd &middot;
      <span class="badge confirmed">CONFIRMED</span> Neal Rd SE &middot;
      <span class="badge confirmed">CONFIRMED</span> NE Tolt Hill Rd &middot;
      <span class="badge confirmed">CONFIRMED</span> West Snoqualmie River/Valley Rd
    </p>
    <p><span class="badge missed">NOT FLAGGED</span> Tolt River Rd NE - the
    report describes water as <em>expected</em> over sections there; the
    March 20 SAR pass may have caught it just before that section
    crested.</p>
    <p><strong>6 of 7 reported road groups independently confirmed.</strong></p>

    <h2>geoai and a real platform limitation</h2>
    <p><code>geoai</code>'s two deep-learning models for this task -
    <code>segment_water()</code> and <code>changestar_detect()</code>
    (bi-temporal building change detection) - both segfaulted immediately
    on the machine this was built on (Apple Silicon, PyTorch 2.14), crashing
    at model load even on a tiny test crop with every optional feature
    disabled. Basic PyTorch operations work fine in isolation, so this is a
    genuine platform incompatibility with these specific pretrained models,
    not a bug in how they were called. <code>raster_to_vector()</code> (no
    deep-learning dependency) performed the actual segmentation-to-polygon
    step instead - see the notebook for the full trace.</p>

    <h2>Honest limitations</h2>
    <ul>
      <li>Exposure (fell inside the flood extent), not a visual damage
      classification.</li>
      <li>SAR threshold (&gt;3dB backscatter drop) is a standard
      quick-flood-mapping convention, not full radiometric terrain
      correction.</li>
      <li>No FEMA-accredited levee coverage exists in this area - the
      report's Remlinger Levee is a local/agricultural levee, not in that
      dataset.</li>
      <li>King County does not publish a public building-footprint layer;
      building data is from Overture Maps instead.</li>
    </ul>

    <h2>Data sources</h2>
    <ul>
      <li><a href="https://planetarycomputer.microsoft.com/" target="_blank" rel="noopener">Sentinel-1/2</a> via Microsoft Planetary Computer</li>
      <li><a href="https://gis-kingcounty.opendata.arcgis.com/" target="_blank" rel="noopener">King County GIS Open Data</a> - rivers, roads, levee inventory</li>
      <li><a href="https://overturemaps.org/" target="_blank" rel="noopener">Overture Maps</a> - building footprints</li>
      <li><a href="https://github.com/opengeos/geoai" target="_blank" rel="noopener">geoai</a> - raster-to-vector segmentation</li>
      <li><a href="../notebooks/flood_infrastructure_exposure.ipynb" target="_blank" rel="noopener">Full analysis notebook</a> on GitHub</li>
      <li><a href="https://github.com/crikeli/kc-flood-infrastructure-exposure" target="_blank" rel="noopener">Source code on GitHub</a></li>
    </ul>
    """

    page = PAGE_TEMPLATE.format(
        about_html=about_html,
        center_json=json.dumps(CENTER),
        flood_area_km2=flood_area_km2,
        road_count=road_count,
        building_count=building_count,
    )
    with open(os.path.join(DOCS_DIR, "index.html"), "w") as f:
        f.write(page)
    print(f"Wrote {os.path.join(DOCS_DIR, 'index.html')}")


if __name__ == "__main__":
    main()
