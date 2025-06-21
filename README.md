# 🌍 Air Quality Data Visualization Dashboard

An interactive, multi-tab Bokeh dashboard developed as part of the **MSc Data Science – Data Visualization course (1st Semester)**. This project explores global air quality data using a rich set of visualizations including scatter plots, heatmaps, time series, box plots, geographic maps, and stacked area charts.

---

## 📊 Key Features

- **Scatter Plot (AQI vs PM2.5):**  
  Visualizes AQI values against PM2.5 with size-scaling by PM10 and color-coded AQI categories.

- **Regional Trends:**  
  Line charts of yearly average AQI across countries with multi-select filtering and dynamic interactivity.

- **Heatmaps:**  
  Monthly and yearly pollutant concentrations by country across six pollutants: PM2.5, PM10, CO, NO2, SO2, and Ozone.

- **Time-Series Trends:**  
  Filter by year and up to 3 cities; analyze trends of pollutants over months with unit-based checkboxes and legends.

- **Grouped Bar Charts:**  
  Compare pollutant concentrations across countries for a selected year with sorting by PM2.5.

- **Box Plots:**  
  Monthly distribution of a selected pollutant in a city for a specific year with detailed statistics (min, max, median, quartiles).

- **Geospatial Map:**  
  World map showing average PM2.5 (or selected pollutant) concentration per country per year, using GeoJSON and shapefiles.

- **Stacked Area Chart:**  
  Displays the contribution of each pollutant to overall concentration over time, filterable by unit and year.

---

## 📂 Dataset

- **File:** `expanded_air_quality_data.csv`
- **Description:** Contains country-wise and city-wise daily air quality measurements (PM2.5, PM10, CO, NO2, SO2, Ozone, AQI).
- **Shapefile:** Natural Earth shapefile used for geospatial mapping.

---

## 🛠 Technologies Used

- **Python**
- **Bokeh** – Interactive visualizations
- **Pandas / GeoPandas** – Data manipulation and geospatial processing
- **NumPy** – Numerical operations
- **JavaScript (CustomJS)** – Front-end interactivity for dropdowns and animations
- **HTML/CSS** – Custom styling for Bokeh widgets

---

## 🚀 Running the Dashboard

1. Clone the repo:
   ```bash
   git clone https://github.com/your-username/air-quality-dashboard.git
   cd air-quality-dashboard
