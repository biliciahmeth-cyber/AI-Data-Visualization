# AI Weather Data Visualization Pipeline

This project is an automated Python pipeline that fetches, processes, and visualizes AI-generated weather forecast data from NOAA's public S3 buckets. It is designed to run efficiently on a resource-constrained server, automating the entire data-to-image workflow.

## 🚀 Key Features

* **Automated Data Fetching:** The script automatically calculates the latest 00Z model run time and downloads the correct 5GB global dataset (NVIDIA's FourCastNet `FOUR_v200_GFS`) using `requests`.
* **Multi-Parameter Plotting:** Generates 9 distinct meteorological maps, including 2m Temperature, 10m Wind Speed, MSL Pressure, Precipitable Water, and 500hPa Geopotential Height.
* **Multi-Domain & Multi-Time:** Creates forecasts for 3 time steps (Analysis 00h, +24h, +48h) across 3 different geographical domains (Europe, Turkey, and Marmara).
* **Adaptive Color Scaling:** A key feature where the color scale dynamically adapts to the zoom level. It uses a high-resolution **0.5°C** step for the local Marmara domain (to show fine detail) while applying a broader **2°C** step for the synoptic Europe map.
* **Self-Cleaning:** Automatically deletes the 5GB source NetCDF file after processing is complete, ensuring the server's disk space is preserved.
* **Technology Stack:** `Python`, `xarray` (for data processing), `cartopy` (for map projections), `matplotlib` (for plotting), `numpy` (for calculations), and `requests` (for downloading).

## 🗺️ Technical Pipeline

The script executes the following workflow:

1.  **Initialize:** Calculates the correct UTC date for the latest model run.
2.  **Fetch:** Downloads the 5GB global NetCDF file from the NOAA S3 bucket.
3.  **Process & Plot:** Opens the dataset in-memory with `xarray`. It then loops through all 9 parameters, 3 time steps, and 3 domains (generating 81 maps in total).
4.  **Visualize:** Uses `cartopy` to project the data onto a Mercator map, applying the correct adaptive color scale for each domain.
5.  **Save & Clean Up:** Saves the final maps as `.png` files and immediately deletes the 5GB source file.

## 📊 Visualized Parameters

1.  **2m Temperature** (with adaptive 0.5°C scaling)
2.  **10m Wind Speed**
3.  **Mean Sea Level Pressure**
4.  **Precipitable Water**
5.  **700 hPa Relative Humidity**
6.  **850 hPa Temperature**
7.  **500 hPa Vertical Velocity**
8.  **Skin Temperature**
9.  **500 hPa Geopotential Height & Temperature**

## ⚙️ Setup and Automation

1.  **Install Dependencies:**
    ```bash
    pip install xarray netCDF4 matplotlib cartopy numpy requests
    ```
2.  **Run (Test):**
    ```bash
    python3 harita_uret.py
    ```
3.  **Automate (Cronjob):**
    The script is designed to be run automatically via `cron`. The following example runs the script every day at 07:00 UTC:
    ```bash
    0 7 * * * /usr/bin/python3 /path/to/harita_uret.py > /var/log/map_generator.log 2>&1
    ```
