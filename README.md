# ndvi-change-detection

# 🛰️ NDVI Change Detection — Sentinel-2, Bavaria, Germany

A geospatial data science project that uses **real Sentinel-2 satellite imagery** from the Copernicus Data Space API to analyze vegetation change between **August 2022 and August 2023** over an agricultural and forested region in Bavaria, Germany.

---

## 📌 Project Overview

This project demonstrates a full end-to-end remote sensing workflow in Python — from API authentication and satellite data download, through NDVI computation and land cover classification, to interactive web map generation.

| Item | Details |
|---|---|
| **Satellite** | Sentinel-2 L2A (ESA / Copernicus) |
| **Bands used** | B04 (Red, 10m) + B08 (NIR, 10m) |
| **Study area** | Bavaria, Germany |
| **Period** | August 2022 vs August 2023 |
| **Resolution** | 10 metres per pixel |

---

## 📊 Key Results

| Metric | August 2022 | August 2023 |
|---|---|---|
| Mean NDVI | 0.394 | 0.415 |
| % Vegetation (NDVI > 0.3) | 73.2% | 79.7% |
| % Water (NDVI < 0) | 3.0% | 3.5% |

**Change Detection Summary (2022 → 2023):**
- 🟢 Improved (NDVI > +0.05): **29.1%** of pixels
- 🟡 Stable: **48.5%** of pixels
- 🔴 Degraded (NDVI < −0.05): **22.5%** of pixels

---

## 🗺️ Outputs

| File | Description |
|---|---|
| `ndvi_change_detection.png` | Side-by-side NDVI maps + change map |
| `classification.png` | NDVI-based land cover classification (5 classes) |
| `ndvi_interactive_map.html` | Interactive Folium web map (open in browser) |

---

## 🔧 Installation

```bash
# Create conda environment
conda create -n geoenv python=3.11
conda activate geoenv

# Install geospatial libraries
conda install -c conda-forge geopandas rasterio matplotlib jupyter notebook -y
conda install -c conda-forge libgdal-jp2openjpeg -y
pip install rioxarray folium pillow pandas
```

---

## 🚀 Usage

1. Register for a free account at [Copernicus Data Space](https://dataspace.copernicus.eu)
2. Create an OAuth client in your account settings
3. Edit the credentials section in `ndvi_change_detection.py`:

```python
USERNAME  = "your-email@gmail.com"
PASSWORD  = "your-password"
```

4. Run the script:

```bash
jupyter notebook
# or
python ndvi_change_detection.py
```

---

## 🧠 What I Learned

- Authenticating with the **Copernicus Data Space API** (OAuth2 + password flow)
- Navigating the **OData Node API** to download individual spectral bands
- Computing **NDVI** from raw reflectance values using NumPy and RioXarray
- **Change detection** by differencing multi-temporal NDVI rasters
- **Land cover classification** using NDVI thresholds
- Creating **interactive web maps** with Folium and base64 image overlays

---

## 📚 Technologies

`Python` `Sentinel-2` `Copernicus API` `STAC` `RioXarray` `Rasterio` `NumPy` `Matplotlib` `Folium` `GeoPandas` `Remote Sensing` `GIS`

---

## 👤 Author

**Ayoub Oihi** — Geomatics & Remote Sensing | Geospatial Data Science  
📧 ayouboihi9@gmail.com
