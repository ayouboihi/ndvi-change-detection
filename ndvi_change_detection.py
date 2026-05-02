# =============================================================================
# NDVI Change Detection using Sentinel-2 Satellite Imagery
# Author: Ayoub Oihi
# Description: This script downloads Sentinel-2 bands from the Copernicus
#              Data Space API, computes NDVI for two different years,
#              performs change detection, land cover classification,
#              and generates an interactive HTML map.
# Study Area: Bavaria, Germany
# Period: August 2022 vs August 2023
# =============================================================================

import requests
import rioxarray as rxr
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import folium
import base64
from io import BytesIO
from PIL import Image
from matplotlib.colors import TwoSlopeNorm, ListedColormap, BoundaryNorm, Normalize
from matplotlib import cm
import matplotlib.patches as mpatches

# =============================================================================
# STEP 1 — AUTHENTICATION
# Connect to Copernicus Data Space using your credentials
# =============================================================================

CLIENT_ID     = "sh-f8e4feff-af55-42d4-be64-68518a76b9bd"       # Replace with your OAuth Client ID
CLIENT_SECRET = "CbS6PAfCmgIxmurbClLEhb1jJgLox5Gj"   # Replace with your OAuth Client Secret
USERNAME      = "ayouboihi9@gmail.com" # Replace with your Copernicus email
PASSWORD      = "OI134hi240299@"        # Replace with your Copernicus password

# Request an access token using username/password flow
auth_response = requests.post(
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
    data={
        "grant_type": "password",
        "client_id": "cdse-public",
        "username": USERNAME,
        "password": PASSWORD,
    }
)
token = auth_response.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print("✅ Authenticated with Copernicus API")

# =============================================================================
# STEP 2 — SEARCH SENTINEL-2 IMAGES USING STAC API
# We search for cloud-free Sentinel-2 L2A images over our study area
# =============================================================================

# Bounding box of our study area [lon_min, lat_min, lon_max, lat_max]
BBOX = [7.6300, 47.1236, 7.8639, 47.2739]
STAC_URL = "https://stac.dataspace.copernicus.eu/v1/search"

def search_sentinel2(date_start, date_end, limit=5):
    """
    Search for Sentinel-2 L2A images within a date range and bounding box.
    Returns a list of image features from the STAC API.
    """
    payload = {
        "bbox": BBOX,
        "datetime": f"{date_start}T00:00:00Z/{date_end}T00:00:00Z",
        "collections": ["sentinel-2-l2a"],
        "limit": limit
    }
    r = requests.post(STAC_URL, json=payload)
    return r.json()

# Search for summer images in 2022 and 2023
print("🔍 Searching for Sentinel-2 images...")
items_2022 = search_sentinel2("2022-06-01", "2022-08-31")
items_2023 = search_sentinel2("2023-06-01", "2023-08-31")
print(f"   Found {items_2022['numberReturned']} images in 2022")
print(f"   Found {items_2023['numberReturned']} images in 2023")

# =============================================================================
# STEP 3 — DOWNLOAD BANDS B04 (Red) AND B08 (NIR)
# We use the OData Node API to download individual bands (not the full product)
# This avoids downloading the entire 1GB+ SAFE archive
# =============================================================================

def get_safe_name(product_id):
    """Retrieve the SAFE folder name for a given product ID."""
    r = requests.get(
        f"https://download.dataspace.copernicus.eu/odata/v1/Products({product_id})/Nodes",
        headers=headers
    )
    return r.json()["result"][0]["Name"]

def get_granule_name(product_id, safe_name):
    """Retrieve the granule folder name inside the SAFE archive."""
    r = requests.get(
        f"https://download.dataspace.copernicus.eu/odata/v1/Products({product_id})"
        f"/Nodes({safe_name})/Nodes(GRANULE)/Nodes",
        headers=headers
    )
    return r.json()["result"][0]["Name"]

def get_band_files(product_id, safe_name, granule_name):
    """List all files available at 10m resolution."""
    r = requests.get(
        f"https://download.dataspace.copernicus.eu/odata/v1/Products({product_id})"
        f"/Nodes({safe_name})/Nodes(GRANULE)/Nodes({granule_name})"
        f"/Nodes(IMG_DATA)/Nodes(R10m)/Nodes",
        headers=headers
    )
    return r.json()["result"]

def download_band(product_id, safe_name, granule_name, band_filename, output_path):
    """
    Download a single band file (JP2 format) and save it locally.
    Band B04 = Red channel, Band B08 = Near-Infrared (NIR) channel
    """
    base = (
        f"https://download.dataspace.copernicus.eu/odata/v1/Products({product_id})"
        f"/Nodes({safe_name})/Nodes(GRANULE)/Nodes({granule_name})"
        f"/Nodes(IMG_DATA)/Nodes(R10m)/Nodes({band_filename})/$value"
    )
    r = requests.get(base, headers=headers)
    with open(output_path, "wb") as f:
        f.write(r.content)
    size_mb = len(r.content) / 1024 / 1024
    print(f"   ✅ {output_path} downloaded ({size_mb:.1f} MB)")

# --- Download 2022 bands ---
print("\n📥 Downloading 2022 bands...")
# Use OData search to get product ID for August 2022
params_2022 = {
    "$filter": (
        "Collection/Name eq 'SENTINEL-2' and "
        "Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' "
        "and att/OData.CSC.StringAttribute/Value eq 'S2MSI2A') and "
        "ContentDate/Start gt 2022-08-28T00:00:00.000Z and "
        "ContentDate/Start lt 2022-08-30T00:00:00.000Z and "
        "OData.CSC.Intersects(area=geography'SRID=4326;POLYGON("
        "(7.63 47.12, 7.86 47.12, 7.86 47.27, 7.63 47.27, 7.63 47.12))')"
    ),
    "$orderby": "ContentDate/Start desc",
    "$top": 5
}
r = requests.get("https://catalogue.dataspace.copernicus.eu/odata/v1/Products", params=params_2022)
products_2022 = r.json()["value"]

# Select the T32TMT tile (consistent tile ID across both years)
product_2022 = next(p for p in products_2022 if "T32TMT" in p["Name"])
pid_2022     = product_2022["Id"]
safe_2022    = get_safe_name(pid_2022)
gran_2022    = get_granule_name(pid_2022, safe_2022)
files_2022   = get_band_files(pid_2022, safe_2022, gran_2022)

# Find B04 and B08 filenames dynamically
b04_file_2022 = next(f["Name"] for f in files_2022 if "_B04_" in f["Name"])
b08_file_2022 = next(f["Name"] for f in files_2022 if "_B08_" in f["Name"])

download_band(pid_2022, safe_2022, gran_2022, b04_file_2022, "B04_2022.jp2")
download_band(pid_2022, safe_2022, gran_2022, b08_file_2022, "B08_2022.jp2")

# --- Download 2023 bands ---
print("\n📥 Downloading 2023 bands...")
params_2023 = {
    "$filter": (
        "Collection/Name eq 'SENTINEL-2' and "
        "Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' "
        "and att/OData.CSC.StringAttribute/Value eq 'S2MSI2A') and "
        "ContentDate/Start gt 2023-08-21T00:00:00.000Z and "
        "ContentDate/Start lt 2023-08-23T00:00:00.000Z and "
        "OData.CSC.Intersects(area=geography'SRID=4326;POLYGON("
        "(7.63 47.12, 7.86 47.12, 7.86 47.27, 7.63 47.27, 7.63 47.12))')"
    ),
    "$orderby": "ContentDate/Start desc",
    "$top": 5
}
r = requests.get("https://catalogue.dataspace.copernicus.eu/odata/v1/Products", params=params_2023)
products_2023 = r.json()["value"]

product_2023 = next(p for p in products_2023 if "T32TMT" in p["Name"])
pid_2023     = product_2023["Id"]
safe_2023    = get_safe_name(pid_2023)
gran_2023    = get_granule_name(pid_2023, safe_2023)
files_2023   = get_band_files(pid_2023, safe_2023, gran_2023)

b04_file_2023 = next(f["Name"] for f in files_2023 if "_B04_" in f["Name"])
b08_file_2023 = next(f["Name"] for f in files_2023 if "_B08_" in f["Name"])

download_band(pid_2023, safe_2023, gran_2023, b04_file_2023, "B04_2023.jp2")
download_band(pid_2023, safe_2023, gran_2023, b08_file_2023, "B08_2023.jp2")

# =============================================================================
# STEP 4 — COMPUTE NDVI
# NDVI = (NIR - Red) / (NIR + Red)
# Values range from -1 to 1:
#   < 0      : Water, bare rock
#   0 – 0.15 : Bare soil, urban
#   0.15–0.3 : Sparse vegetation
#   0.3–0.6  : Moderate vegetation / crops
#   > 0.6    : Dense vegetation / forest
# =============================================================================

print("\n🧮 Computing NDVI...")
b04_22 = rxr.open_rasterio("B04_2022.jp2", masked=True).squeeze().astype(float)
b08_22 = rxr.open_rasterio("B08_2022.jp2", masked=True).squeeze().astype(float)
b04_23 = rxr.open_rasterio("B04_2023.jp2", masked=True).squeeze().astype(float)
b08_23 = rxr.open_rasterio("B08_2023.jp2", masked=True).squeeze().astype(float)

ndvi_2022 = (b08_22 - b04_22) / (b08_22 + b04_22)
ndvi_2023 = (b08_23 - b04_23) / (b08_23 + b04_23)

# Change map: positive = vegetation increased, negative = vegetation decreased
ndvi_change = ndvi_2023 - ndvi_2022
print("   ✅ NDVI computed for 2022 and 2023")

# =============================================================================
# STEP 5 — STATISTICS
# Summarize NDVI distribution and quantify change across the study area
# =============================================================================

def ndvi_stats(ndvi, label):
    """Compute descriptive statistics for an NDVI array."""
    valid = ndvi.values[~np.isnan(ndvi.values)]
    return {
        "Period": label,
        "Mean NDVI": round(float(np.mean(valid)), 3),
        "Median NDVI": round(float(np.median(valid)), 3),
        "Std Dev": round(float(np.std(valid)), 3),
        "Min": round(float(np.min(valid)), 3),
        "Max": round(float(np.max(valid)), 3),
        "% Vegetation (>0.3)": round(float(np.sum(valid > 0.3) / len(valid) * 100), 1),
        "% Water (<0)": round(float(np.sum(valid < 0) / len(valid) * 100), 1),
    }

df_stats = pd.DataFrame([ndvi_stats(ndvi_2022, "August 2022"),
                          ndvi_stats(ndvi_2023, "August 2023")])
print("\n📊 NDVI Statistics:")
print(df_stats.to_string(index=False))

change_valid = ndvi_change.values[~np.isnan(ndvi_change.values)]
improved = np.sum(change_valid > 0.05)
degraded = np.sum(change_valid < -0.05)
stable   = np.sum(np.abs(change_valid) <= 0.05)
total    = len(change_valid)
print(f"\n📈 Change Detection Summary:")
print(f"   🟢 Improved  : {improved/total*100:.1f}%")
print(f"   🟡 Stable    : {stable/total*100:.1f}%")
print(f"   🔴 Degraded  : {degraded/total*100:.1f}%")

# =============================================================================
# STEP 6 — VISUALIZATION
# Plot NDVI maps side by side with change detection map
# =============================================================================

fig, axes = plt.subplots(1, 3, figsize=(18, 6))

im1 = axes[0].imshow(ndvi_2022.values, cmap='RdYlGn', vmin=-0.2, vmax=0.9)
axes[0].set_title("NDVI - August 2022", fontsize=13)
axes[0].axis('off')
plt.colorbar(im1, ax=axes[0], fraction=0.046, pad=0.04)

im2 = axes[1].imshow(ndvi_2023.values, cmap='RdYlGn', vmin=-0.2, vmax=0.9)
axes[1].set_title("NDVI - August 2023", fontsize=13)
axes[1].axis('off')
plt.colorbar(im2, ax=axes[1], fraction=0.046, pad=0.04)

norm_change = TwoSlopeNorm(vmin=-0.3, vcenter=0, vmax=0.3)
im3 = axes[2].imshow(ndvi_change.values, cmap='RdYlGn', norm=norm_change)
axes[2].set_title("NDVI Change (2023 - 2022)", fontsize=13)
axes[2].axis('off')
plt.colorbar(im3, ax=axes[2], fraction=0.046, pad=0.04)

plt.suptitle("NDVI Change Detection - Bavaria, Germany (2022 vs 2023)",
             fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig("ndvi_change_detection.png", dpi=150, bbox_inches='tight')
plt.show()
print("✅ NDVI map saved: ndvi_change_detection.png")

# =============================================================================
# STEP 7 — LAND COVER CLASSIFICATION
# Classify pixels into 5 land cover categories based on NDVI thresholds
# =============================================================================

def classify_ndvi(ndvi):
    """
    Classify land cover based on NDVI thresholds.
    Classes:
        1 = Water          (NDVI < 0)
        2 = Bare Soil      (0.00 – 0.15)
        3 = Sparse Veg     (0.15 – 0.30)
        4 = Moderate Veg   (0.30 – 0.60)
        5 = Dense Forest   (NDVI > 0.60)
    """
    classes = np.zeros_like(ndvi.values, dtype=np.uint8)
    classes[ndvi.values < 0]                                        = 1
    classes[(ndvi.values >= 0)    & (ndvi.values < 0.15)]          = 2
    classes[(ndvi.values >= 0.15) & (ndvi.values < 0.30)]          = 3
    classes[(ndvi.values >= 0.30) & (ndvi.values < 0.60)]          = 4
    classes[ndvi.values >= 0.60]                                    = 5
    return classes

classes_2022 = classify_ndvi(ndvi_2022)
classes_2023 = classify_ndvi(ndvi_2023)

colors  = ['#4A90D9', '#C8A96E', '#E8D5A3', '#90C96A', '#2D6A2D']
labels  = ['Water', 'Bare Soil', 'Sparse Veg', 'Moderate Veg', 'Dense Forest']
cmap_cls = ListedColormap(colors)
norm_cls = BoundaryNorm([0.5, 1.5, 2.5, 3.5, 4.5, 5.5], cmap_cls.N)

fig, axes = plt.subplots(1, 2, figsize=(14, 6))
axes[0].imshow(classes_2022, cmap=cmap_cls, norm=norm_cls)
axes[0].set_title("Land Cover - August 2022", fontsize=13)
axes[0].axis('off')
axes[1].imshow(classes_2023, cmap=cmap_cls, norm=norm_cls)
axes[1].set_title("Land Cover - August 2023", fontsize=13)
axes[1].axis('off')

patches = [mpatches.Patch(color=colors[i], label=labels[i]) for i in range(5)]
plt.legend(handles=patches, loc='lower center',
           bbox_to_anchor=(-0.1, -0.08), ncol=5, fontsize=10)
plt.suptitle("NDVI-based Land Cover Classification - Bavaria",
             fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig("classification.png", dpi=150, bbox_inches='tight')
plt.show()
print("✅ Classification map saved: classification.png")

# =============================================================================
# STEP 8 — INTERACTIVE MAP (Folium)
# Export the NDVI change layer as an interactive HTML map
# Users can zoom, pan, and toggle the layer
# =============================================================================

def ndvi_to_rgba(data, cmap_name='RdYlGn', vmin=-0.3, vmax=0.3):
    """Convert a 2D NDVI array to an RGBA image for overlay on a web map."""
    norm  = Normalize(vmin=vmin, vmax=vmax)
    cmap  = cm.get_cmap(cmap_name)
    rgba  = cmap(norm(np.clip(data, vmin, vmax)))
    rgba[np.isnan(data)] = [0, 0, 0, 0]  # Transparent for no-data pixels
    return (rgba * 255).astype(np.uint8)

center_lat = (BBOX[1] + BBOX[3]) / 2
center_lon = (BBOX[0] + BBOX[2]) / 2

m = folium.Map(location=[center_lat, center_lon], zoom_start=11,
               tiles='CartoDB positron')

# Encode NDVI change image as base64 PNG for embedding in HTML
change_img = ndvi_to_rgba(ndvi_change.values)
pil_img    = Image.fromarray(change_img)
buf        = BytesIO()
pil_img.save(buf, format='PNG')
img_b64    = base64.b64encode(buf.getvalue()).decode()

bounds = [[BBOX[1], BBOX[0]], [BBOX[3], BBOX[2]]]

folium.raster_layers.ImageOverlay(
    image=f"data:image/png;base64,{img_b64}",
    bounds=bounds,
    opacity=0.7,
    name="NDVI Change 2022–2023"
).add_to(m)

folium.LayerControl().add_to(m)

# Add a title box to the map
title_html = '''
<div style="position:fixed; top:10px; left:50px; z-index:9999;
     background-color:white; padding:10px; border-radius:8px;
     font-family:Arial; font-size:14px; font-weight:bold;
     box-shadow:2px 2px 6px rgba(0,0,0,0.3);">
    🛰️ NDVI Change Detection — Bavaria 2022 vs 2023<br>
    <span style="color:green">■</span> Improved &nbsp;
    <span style="color:#FFD700">■</span> Stable &nbsp;
    <span style="color:red">■</span> Degraded
</div>
'''
m.get_root().html.add_child(folium.Element(title_html))
m.save("ndvi_interactive_map.html")
print("✅ Interactive map saved: ndvi_interactive_map.html")
print("\n🎉 Project complete! All outputs saved.")
