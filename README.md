# King County Flood Infrastructure Exposure (Demo)

Which roads and buildings fell inside the flood extent of the
[March 17-21, 2026 King County flood](https://kingcountyfloodcontrol.org/march-17-21-2026-flood-event-report/),
built entirely from free satellite data and real King County GIS layers. The
Snoqualmie and Tolt Rivers both reached Phase 3 (the report's highest alert
level) during the event, making the Snoqualmie Valley / Tolt River
confluence (Fall City-Carnation-Duvall) the most severely affected area in
the county - and the study area for this project.

**Live site: https://crikeli.github.io/kc-flood-infrastructure-exposure/**

## What this is - and isn't

**Exposure, not visual damage.** No confirmed very-high-resolution imagery
source exists for this specific event (no Maxar Open Data Program
activation found for it). At Sentinel's 10m resolution, a washed-out road
and a merely-flooded-but-intact road look identical - so this project
answers a narrower, honest question: which specific roads and buildings
fell inside the derived flood extent, not whether any individual structure
was actually damaged.

**Finding:** the SAR-derived flood extent covers 10.3 sq km, exposing 167
road segments (83 distinct named roads) and 463 buildings. **6 of the 7
road groups the flood report itself names as affected are independently
confirmed** by this satellite-only analysis, with no reference to the
report during detection.

## Real data problems hit along the way

**Sentinel-1 GRD uses GCP georeferencing, not a plain affine transform.**
A first windowed read assumed a standard CRS/transform and returned an
all-zero array. Fixed with a `WarpedVRT` built from the scene's ground
control points, then a second explicit `reproject()` pass onto one shared
canonical grid - the same two-source-independently-computed-different-grids
bug hit in the tree-canopy project's NAIP mosaic, fixed the same way.

**An ArcGIS REST query silently truncated at 1,000 records.** The county's
road network service caps results at 1,000 per request; an unpaginated
query returned only 182 of the real 1,551 road segments in the AOI - a
~8x undercount that would have significantly understated infrastructure
exposure. Caught by checking `returnCountOnly` before trusting the result,
not after.

**A CRS bug silently zeroed out the building layer.** The Overture Maps
buildings download needs a WGS84 bounding box, but the AOI variable in
scope at that point in the pipeline was in UTM meters - Overture accepted
the (nonsensical) bbox without erroring and just returned zero buildings.
Caught by an `assert len(buildings) > 0` added after the fact, not by
assuming the download worked.

**`geoai`'s deep-learning models crash on this machine.** `segment_water()`
and `changestar_detect()` (bi-temporal building change detection) both
segfault immediately at model load - even on a tiny 300x300px test crop
with every optional feature disabled - a genuine platform incompatibility
(Apple Silicon + PyTorch 2.14) with these specific pretrained models, not a
calling-code bug (confirmed by testing basic PyTorch tensor/conv2d ops in
isolation, which work fine). `geoai.raster_to_vector()` - no deep-learning
dependency - performed the actual segmentation-to-polygon step instead.

**King County has no FEMA-accredited levee coverage in this AOI.** The
report's own Remlinger Levee is a local/agricultural levee, not in the
county's formal levee inventory (97 features countywide, zero here) - a
real, reportable data-coverage gap, not a bug.

## The web map is vector-only, on purpose

Unlike the tree-canopy project (which needed a whole pre-rendered tile
pyramid to serve raster imagery fast), this project's core deliverable -
flood extent, exposed roads, exposed buildings - is inherently small vector
data. Total payload across all four GeoJSON layers is under 400KB, so the
site loads everything on page load and renders natively via Leaflet's
vector renderer - no raster decoding, no lazy-loading tricks needed at all.

## Repo layout

```
notebooks/
  flood_infrastructure_exposure.ipynb   # the full, executed analysis
data/
  build_static_site.py    # renders docs/index.html from the notebook's outputs
  mainstem_rivers.geojson, flood_roads_cluster.geojson   # real AOI-defining geometry
  aoi_sanity_check.png, sar_flood_check.png   # validation plots from the notebook
docs/
  index.html               # the deployed static site
  aoi.geojson, flood_extent.geojson, roads_exposed.geojson, buildings_flooded.geojson
environment.yml
```

Raw Sentinel-2 GeoTIFFs, the full Overture buildings download (45MB), and
the unpaginated road query are produced locally but git-ignored - the
notebook regenerates them from source on request.

## Setup

```bash
conda env create -f environment.yml
conda activate kc-flood-infrastructure-exposure
```

```bash
jupyter nbconvert --to notebook --execute --inplace notebooks/flood_infrastructure_exposure.ipynb
python data/build_static_site.py
```

## Stack

pystac-client + planetary-computer (Sentinel-1/2 via STAC), rasterio,
geoai (raster-to-vector segmentation), geopandas - King County GIS Open
Data (rivers, roads, levee inventory) and Overture Maps (buildings) for
infrastructure context - Leaflet for the deployed static site, Esri World
Imagery for basemap context.
