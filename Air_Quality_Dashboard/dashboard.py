from bokeh.models import (
    ColumnDataSource, Whisker, FixedTicker, Dropdown, Checkbox, CheckboxGroup, BoxAnnotation, DateRangeSlider, LinearColorMapper, ColorBar, FactorRange, Dodge, RangeSlider, DataTable, Select, HoverTool, Button, Tabs, TabPanel, MultiSelect, CustomJS, Div, WMTSTileSource
)
from bokeh.plotting import figure, curdoc
from bokeh.models import LabelSet
from bokeh.layouts import column, row, gridplot
from bokeh.palettes import Viridis256, RdYlGn, Category20, Category10
from bokeh.models import CategoricalColorMapper, Slider
import geopandas as gpd 
import pandas as pd
from bokeh.io import output_file, show
from bokeh.models import GeoJSONDataSource
from bokeh.palettes import RdYlGn11 as palette
from math import pi
from bokeh.transform import cumsum
from bokeh.palettes import Category20c
from bokeh.models import DataTable, TableColumn, NumberFormatter, Button, Legend, DateFormatter, LegendItem, CustomJSTickFormatter
from bokeh.plotting import curdoc
from bokeh.transform import dodge
from bokeh.transform import linear_cmap
from random import choice
from bokeh.transform import factor_cmap

from scipy.ndimage import gaussian_filter1d 

from pyproj import Transformer
from bokeh.models import Range1d
from bokeh.plotting import figure
import numpy as np

from bokeh.models import Slider
from bokeh.layouts import layout
from itertools import cycle

from random import randint
from datetime import datetime, timedelta

import requests
from bokeh.palettes import Spectral6


# Load dataset
df = pd.read_csv('expanded_air_quality_data.csv')
df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
df = df.dropna(subset=['Date'])  # Drop invalid dates
df['Year'] = df['Date'].dt.year

# ---- Scatter Plot Tab ----
scatter_df = df.sample(n=5000, random_state=42)  # Sample data to reduce density
scatter_df['PM10_Scaled'] = (scatter_df['PM10'] - scatter_df['PM10'].min()) / (scatter_df['PM10'].max() - scatter_df['PM10'].min()) * 10 + 5

# Add AQI categories
def categorize_aqi(aqi):
    if aqi <= 50:
        return 'Good'
    elif aqi <= 100:
        return 'Moderate'
    elif aqi <= 150:
        return 'Unhealthy'
    elif aqi <= 200:
        return 'Very Unhealthy'
    else:
        return 'Hazardous'

scatter_df['AQI_Category'] = scatter_df['AQI'].apply(categorize_aqi)
scatter_source = ColumnDataSource(scatter_df)

scatter_fig = figure(title="AQI vs PM2.5 Scatter Plot", tools="pan,box_zoom,reset,save", width=1000, height=600, background_fill_color="#CCF2F3", background_fill_alpha=0.8)
scatter_fig.scatter(
    x='PM2.5', y='AQI', source=scatter_source, size='PM10_Scaled', alpha=0.5,
    color={'field': 'AQI', 'transform': LinearColorMapper(palette=RdYlGn[11], low=scatter_df['AQI'].min(), high=scatter_df['AQI'].max())}
    
)
scatter_fig.xaxis.axis_label = "PM2.5"
scatter_fig.yaxis.axis_label = "AQI"

# Hover tool for scatter plot
scatter_hover = HoverTool(tooltips=[
    ('PM2.5', '@{PM2.5}'),
    ('AQI', '@AQI'),
    ('Category', '@{AQI_Category}'),
    ('City', '@City'),
    ('Country', '@Country'),
    ('Date', '@Date{%F}')
], formatters={'@Date': 'datetime'}, mode='mouse')
scatter_fig.add_tools(scatter_hover)

# Filters for scatter plot
country_select = Select(title="Country", value="All", options=["All"] + list(df['Country'].unique()), width=200)
city_select = Select(title="City", value="All", options=["All"], width=200)

# Scatter update functions
def update_city_dropdown(attr, old, new):
    selected_country = country_select.value
    if selected_country == "All":
        city_select.options = ["All"]
    else:
        cities = ["All"] + list(df[df['Country'] == selected_country]['City'].unique())
        city_select.options = cities
    city_select.value = "All"
    update_scatter(None, None, None)

def update_scatter(attr, old, new):
    filtered = scatter_df
    if country_select.value != "All":
        filtered = filtered[filtered['Country'] == country_select.value]
    if city_select.value != "All":
        filtered = filtered[filtered['City'] == city_select.value]
    scatter_source.data = ColumnDataSource.from_df(filtered)

country_select.on_change('value', update_city_dropdown)
city_select.on_change('value', update_scatter)

scatter_tab = TabPanel(
    child=column(row(country_select, city_select), scatter_fig),
    title="Scatter Plot"
)

# ---- Regional Trends Tab ----
regional_data = df.groupby(['Country', 'Year'])['AQI'].mean().reset_index()
regional_data['Year'] = regional_data['Year'].astype(str)
regional_source = ColumnDataSource(regional_data)

regional_fig = figure(
    title="Regional AQI Trends", x_axis_label="Year", y_axis_label="Average AQI",
    tools="pan,box_zoom,reset,save", width=1200, height=700, x_range=sorted(regional_data['Year'].unique())
)

color_map = Category20[20]
countries = regional_data['Country'].unique()

lines = {}
for i, country in enumerate(countries):
    country_data = regional_data[regional_data['Country'] == country]
    source = ColumnDataSource(country_data)
    lines[country] = regional_fig.line(
        x='Year', y='AQI', source=source, line_width=2, color=color_map[i % len(color_map)], legend_label=country, alpha=0.7
    )

regional_hover = HoverTool(tooltips=[
    ("Year", "@Year"),
    ("Average AQI", "@AQI{0.2f}"),
    ("Country", "@Country")
], mode='mouse')
regional_fig.add_tools(regional_hover)
regional_fig.legend.click_policy = "hide"

multi_select = MultiSelect(title="Select Countries:", options=[(c, c) for c in countries], size=8, width=200)
callback = CustomJS(
    args=dict(lines=lines, multi_select=multi_select),
    code="""
    const selected = multi_select.value;
    for (const [country, line] of Object.entries(lines)) {
        line.visible = selected.includes(country);
    }
    """
)
multi_select.js_on_change("value", callback)

regional_tab = TabPanel(
    child=column(row(multi_select, regional_fig)),
    title="Regional Trends"
)



# --- Heatmap Tab ----
# Load Dataset
hm_df = pd.read_csv('expanded_air_quality_data.csv')

# Ensure 'Date' is in datetime format and drop invalid rows
hm_df['Date'] = pd.to_datetime(hm_df['Date'], errors='coerce')
hm_df = hm_df.dropna(subset=['Date'])

# Define pollutants and months
pollutant_columns = ['PM2.5', 'PM10', 'Ozone', 'NO2', 'SO2', 'CO']
months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

# Define units for pollutants
pollutant_units = {
    "PM2.5": "µg/m³",
    "PM10": "µg/m³",
    "Ozone": "ppb",
    "NO2": "ppb",
    "SO2": "ppb",
    "CO": "ppm"
}
# Prepare Heatmap Data
hm_df['Month'] = hm_df['Date'].dt.strftime('%b')  # Extract month abbreviation
hm_df['MonthNum'] = hm_df['Date'].dt.month        # Numeric month for slider
hm_df['Year'] = hm_df['Date'].dt.year             # Extract year

# Group data for pollutants by country, year, and month
hm_data = hm_df.groupby(['Country', 'Year', 'Month', 'MonthNum'])[pollutant_columns].mean().reset_index()

# Initialize default data
default_year = hm_data['Year'].min()
default_pollutant = 'PM2.5'
default_month = 1  # January
filtered_monthly_data = hm_data[(hm_data['Year'] == default_year) & (hm_data['MonthNum'] == default_month)]
filtered_yr_data = hm_data[hm_data['Year'] == default_year]

# Initialize ColumnDataSources
monthly_source = ColumnDataSource(data=dict(
    Month=filtered_monthly_data['Month'],
    Country=filtered_monthly_data['Country'],
    Value=filtered_monthly_data[default_pollutant]
))

yr_source = ColumnDataSource(data=dict(
    Month=filtered_yr_data['Month'],
    Country=filtered_yr_data['Country'],
    Value=filtered_yr_data[default_pollutant]
))

# Color Mappers
monthly_color_mapper = LinearColorMapper(palette="Viridis256", low=filtered_monthly_data[default_pollutant].min(),
                                         high=filtered_monthly_data[default_pollutant].max())

yr_color_mapper = LinearColorMapper(palette="Viridis256", low=filtered_yr_data[default_pollutant].min(),
                                    high=filtered_yr_data[default_pollutant].max())

# Create Monthly Heatmap Figure
monthly_fig = figure(
    title=f"Monthly Pollutant Concentrations ({default_pollutant}, {default_year}, {months[default_month - 1]})",
    x_range=months,
    y_range=sorted(filtered_monthly_data['Country'].unique(), key=lambda c: -filtered_monthly_data[filtered_monthly_data['Country'] == c][default_pollutant].values[0]),
    height=400,
    width=1200,
    tools="pan,box_zoom,reset,save,wheel_zoom"
)
monthly_fig.rect(
    x="Month", y="Country", width=1, height=1, source=monthly_source,
    fill_color={'field': 'Value', 'transform': monthly_color_mapper}, line_color=None
)

# Add the hover tool only once
monthly_hover = HoverTool(tooltips=[
    ("Month", "@Month"),
    ("Country", "@Country"),
    ("Concentration", "@Value{0.2f}")
])
monthly_fig.add_tools(monthly_hover)

monthly_fig.add_layout(ColorBar(color_mapper=monthly_color_mapper, title=f"{default_pollutant} Concentration"), 'right')

# Create Yearly Heatmap Figure
yr_fig = figure(
    title=f"Yearly Pollutant Concentrations ({default_pollutant}, {default_year})",
    x_range=months,
    y_range=sorted(filtered_yr_data['Country'].unique()),
    height=400,
    width=1200,
    tools="pan,box_zoom,reset,save,wheel_zoom"
)
yr_fig.rect(
    x="Month", y="Country", width=1, height=1, source=yr_source,
    fill_color={'field': 'Value', 'transform': yr_color_mapper}, line_color=None
)

# Add the hover tool only once
yr_hover = HoverTool(tooltips=[
    ("Month", "@Month"),
    ("Country", "@Country"),
    ("Concentration", "@Value{0.2f}")
])
yr_fig.add_tools(yr_hover)

yr_fig.add_layout(ColorBar(color_mapper=yr_color_mapper, title=f"{default_pollutant} Concentration"), 'right')

# Dropdowns
pollutant_dropdown = Select(title="Select Pollutant:", value=default_pollutant, options=pollutant_columns, width=200)
yr_dropdown = Select(title="Select Year:", value=str(default_year), options=[str(year) for year in sorted(hm_data['Year'].unique())], width=200)

# Slider for Month Selection
month_slider = Slider(title="Select Month:", start=1, end=12, value=default_month, step=1, width=800, bar_color="#FAFAFA", css_classes=["custom-slider"])

# Update Function
# Update Function
def update_plots(attr, old, new):
    selected_pollutant = pollutant_dropdown.value  # Get selected pollutant
    selected_unit = pollutant_units[selected_pollutant]  # Get the unit for the pollutant
    selected_year = int(yr_dropdown.value)  # Get selected year
    selected_month = month_slider.value  # Get selected month

    # Update Monthly Heatmap
    filtered_monthly = hm_data[(hm_data['Year'] == selected_year) & (hm_data['MonthNum'] == selected_month)]
    if not filtered_monthly.empty:
        # Sort countries by descending pollutant values
        sorted_countries_monthly = (
            filtered_monthly.groupby("Country")[selected_pollutant]
            .mean()
            .sort_values(ascending=True)
            .index.tolist()
        )

        monthly_source.data = {
            "Month": filtered_monthly['Month'],
            "Country": filtered_monthly['Country'],
            "Value": filtered_monthly[selected_pollutant],
        }
        monthly_fig.y_range.factors = sorted_countries_monthly
        monthly_color_mapper.low = filtered_monthly[selected_pollutant].min()
        monthly_color_mapper.high = filtered_monthly[selected_pollutant].max()
        monthly_fig.title.text = (
            f"Monthly Pollutant Concentrations ({selected_pollutant}, {selected_year}, {months[selected_month - 1]})"
        )
    else:
        monthly_source.data = {"Month": [], "Country": [], "Value": []}
        monthly_fig.y_range.factors = []
        monthly_color_mapper.low, monthly_color_mapper.high = 0, 1
        monthly_fig.title.text = f"No Data Available for {selected_pollutant} ({selected_year}, {months[selected_month - 1]})"

    # Update Yearly Heatmap
    filtered_yr = hm_data[hm_data['Year'] == selected_year]
    if not filtered_yr.empty:
        sorted_countries_yr = (
            filtered_yr.groupby("Country")[selected_pollutant]
            .mean()
            .sort_values(ascending=False)
            .index.tolist()
        )
        yr_source.data = {
            "Month": filtered_yr['Month'],
            "Country": filtered_yr['Country'],
            "Value": filtered_yr[selected_pollutant],
        }
        yr_fig.y_range.factors = sorted_countries_yr
        yr_color_mapper.low = filtered_yr[selected_pollutant].min()
        yr_color_mapper.high = filtered_yr[selected_pollutant].max()
        yr_fig.title.text = f"Yearly Pollutant Concentrations ({selected_pollutant}, {selected_year})"
    else:
        yr_source.data = {"Month": [], "Country": [], "Value": []}
        yr_fig.y_range.factors = []
        yr_color_mapper.low, yr_color_mapper.high = 0, 1
        yr_fig.title.text = f"No Data Available for {selected_pollutant} ({selected_year})"


# Attach Callbacks
pollutant_dropdown.on_change('value', update_plots)
yr_dropdown.on_change('value', update_plots)
month_slider.on_change('value', update_plots)

# Combine Controls and Plots
layout = column(row(pollutant_dropdown, yr_dropdown), yr_fig, month_slider, monthly_fig)

# Create Heatmap Tab
heatmap_tab = TabPanel(
    child=layout,
    title="Heatmap"
)







# ---- Time Series Tab ----


# Pollutant Columns (example data) 
# Pollutant Columns (example data) 
from itertools import cycle
from bokeh.models import GlyphRenderer
# Read Dataset
# Read Dataset
air_quality_data = pd.read_csv("expanded_air_quality_data.csv")

# Ensure 'Date' is converted to datetime
air_quality_data['Date'] = pd.to_datetime(air_quality_data['Date'], errors='coerce')

# Extract 'Year' and 'YearMonth'
air_quality_data['Year'] = air_quality_data['Date'].dt.year
air_quality_data['YearMonth'] = air_quality_data['Date'].dt.to_period('M').dt.to_timestamp()

# Drop rows with missing required data
air_quality_data = air_quality_data.dropna(subset=['Date', 'Year', 'YearMonth'])

# Define pollutants, units, and line styles
pollutants = {
    'PM2.5': 'µg/m³',
    'PM10': 'µg/m³',
    'Ozone': 'ppb',
    'NO2': 'ppb',
    'SO2': 'ppb',
    'CO': 'ppm'
}
line_styles = ['solid', 'dashed', 'dotted', 'dotdash', 'dashdot', 'solid']

# Custom color palette for cities
custom_colors = ['red', 'yellow', 'black', 'blue', 'green', 'orange', 'purple', 'pink', 'brown', 'cyan']
color_cycle = cycle(custom_colors)
cities = air_quality_data['City'].dropna().unique()
city_color_map = {city: next(color_cycle) for city in cities}

# Widgets
time_year_select = Select(
    title="Select Year:",
    value=str(int(air_quality_data['Year'].max())),
    options=[str(int(year)) for year in sorted(air_quality_data['Year'].unique())],
    width=200
)

time_city_select = MultiSelect(
    title="Select Cities (Max 3):",
    value=[],
    options=sorted(cities),
    size=8, width=300
)

unit_filter_checkboxes = CheckboxGroup(
    labels=list(set(pollutants.values())),
    active=list(range(len(set(pollutants.values()))))
)

legend_toggle_button = Button(label="Toggle Legend", button_type="primary")

# Time-Series Figure
time_series_fig = figure(
    title="Time-Series Pollutant Trends",
    x_axis_type="datetime",
    x_axis_label="Date",
    y_axis_label="Concentration",
    width=1000, height=500,
    tools="pan,box_zoom,reset,save",
    toolbar_location="above"
)

# Hover Tool
time_series_fig.add_tools(HoverTool(
    tooltips=[
        ("Date", "@x{%F}"),
        ("Value", "@y{0.00}"),
        ("Pollutant", "@pollutant"),
        ("City", "@city"),
        ("Unit", "@unit")
    ],
    formatters={
        "@x": "datetime",
    },
    mode="mouse"
))

# Update function
def update_time_series(attr, old, new):
    # Clear all renderers
    time_series_fig.renderers.clear()

    # Remove existing legends completely
    legends_to_remove = [obj for obj in time_series_fig.right if isinstance(obj, Legend)]
    for legend in legends_to_remove:
        time_series_fig.right.remove(legend)

    # Enforce maximum city selection limit
    selected_cities = time_city_select.value[:3]
    time_city_select.value = selected_cities

    # Parse selected year
    selected_year = int(time_year_select.value)

    if not selected_cities:
        return

    unit_renderers = {unit: [] for unit in set(pollutants.values())}
    active_units = [unit_filter_checkboxes.labels[i] for i in unit_filter_checkboxes.active]

    # Loop through pollutants and cities
    for pollutant_idx, (pollutant, unit) in enumerate(pollutants.items()):
        if unit not in active_units:
            continue

        for city in selected_cities:
            city_data = air_quality_data[
                (air_quality_data['City'] == city) & (air_quality_data['Year'] == selected_year)
            ].copy()

            if city_data.empty:
                continue

            grouped_data = city_data.groupby('YearMonth')[pollutant].mean().reset_index()

            source = ColumnDataSource(data={
                "x": grouped_data['YearMonth'],
                "y": grouped_data[pollutant],
                "pollutant": [pollutant] * len(grouped_data),
                "city": [city] * len(grouped_data),
                "unit": [unit] * len(grouped_data)
            })
            line = time_series_fig.line(
                'x', 'y', source=source, line_width=2,
                line_dash=line_styles[pollutant_idx % len(line_styles)],
                line_color=city_color_map[city]
            )
            unit_renderers[unit].append(line)

    # Add a single legend for units without lines
    legend_items = [LegendItem(label=unit, renderers=renderers) for unit, renderers in unit_renderers.items() if renderers]

    if legend_items:
        legend = Legend(items=legend_items, click_policy="hide", title="Units")
        time_series_fig.add_layout(legend, 'right')

# Toggle legend visibility
def toggle_legend():
    for legend in time_series_fig.right:
        if isinstance(legend, Legend):
            legend.visible = not legend.visible

legend_toggle_button.on_click(toggle_legend)

# Attach callbacks
def limit_city_selection(attr, old, new):
    if len(new) > 3:
        time_city_select.value = old[:3]

unit_filter_checkboxes.on_change("active", update_time_series)
time_city_select.on_change("value", limit_city_selection)
time_year_select.on_change("value", update_time_series)
time_city_select.on_change("value", update_time_series)

# Initial call to update
update_time_series(None, None, None)

# Layout
time_series_layout = column(
    row(time_year_select, time_city_select),
    unit_filter_checkboxes,
    legend_toggle_button,
    time_series_fig
)


time_series_tab = TabPanel(child=time_series_layout, title="Time-Series Trends")






# ---- Grouped Bar Chart Tab ---- 
# Example pollutant columns (replace with your actual pollutant column names)
pollutant_columns = ["PM2.5", "PM10", "Ozone", "NO2", "SO2", "CO"]

# Sample dataframe structure (replace with your dataset path)
# Load data and inspect columns
air_quality_df = pd.read_csv("expanded_air_quality_data.csv")
#print("Columns in dataset:", air_quality_df.columns)  # Debugging: check column names

# Ensure Year column exists
if 'Year' not in air_quality_df.columns:
    if 'Date' in air_quality_df.columns:  # If Date column exists, extract Year
        air_quality_df['Date'] = pd.to_datetime(air_quality_df['Date'], errors='coerce')
        air_quality_df['Year'] = air_quality_df['Date'].dt.year
    else:
        raise KeyError("The dataset must contain either 'Year' or 'Date' column.")

# Drop invalid rows where Year is not present
air_quality_df = air_quality_df.dropna(subset=['Year'])
air_quality_df['Year'] = pd.to_numeric(air_quality_df['Year'], errors='coerce')

# Prepare Grouped Bar Chart Data with Sorting
def prepare_grouped_bar_chart_data(selected_countries, selected_year, sort_by_pollutant='PM2.5'):
    filtered_data = air_quality_df[air_quality_df['Year'] == selected_year]
    filtered_data = filtered_data[filtered_data['Country'].isin(selected_countries)]
    grouped_data = filtered_data.groupby(['Country'])[pollutant_columns].mean().reset_index()
    
    # Sort based on the selected pollutant values (descending order)
    grouped_data = grouped_data.sort_values(by=sort_by_pollutant, ascending=False)
    
    return grouped_data

# Initialize ColumnDataSource for Grouped Bar Chart
grouped_bar_source = ColumnDataSource(data=dict(Country=[], PM2_5=[], PM10=[], Ozone=[], NO2=[], SO2=[], CO=[]))

# Create Grouped Bar Chart Figure
grouped_bar_fig = figure(
    y_range=FactorRange(),
    height=600,
    width=1000,
    title="Grouped Bar Chart: Pollutant Concentrations",
    tools="pan,box_zoom,reset,save",
    toolbar_location="above"
)

# Add grouped bars for each pollutant (horizontal bars)
pollutant_colors = Category20[len(pollutant_columns)]
bar_width = 0.15  # Width for each bar

for i, pollutant in enumerate(pollutant_columns):
    grouped_bar_fig.hbar(
        y=dodge('Country', -0.3 + (i * bar_width), range=grouped_bar_fig.y_range),
        right=pollutant,
        height=bar_width,
        source=grouped_bar_source,
        color=pollutant_colors[i],
        legend_label=pollutant
    )

# Customize axes and legend
grouped_bar_fig.yaxis.axis_label = "Country"
grouped_bar_fig.xaxis.axis_label = "Average Concentration"
grouped_bar_fig.legend.title = "Pollutants"
grouped_bar_fig.legend.location = "top_right"
grouped_bar_fig.legend.click_policy = "hide"

# Dropdown for country selection
grouped_bar_country_select = MultiSelect(
    title="Select Countries:",
    value=["USA", "India", "China"],
    options=list(air_quality_df['Country'].unique()),
    size=8,
    width=300
)

# Slider for Single Year Selection
grouped_bar_year_slider = Slider(
    title="Select Year:",
    start=int(air_quality_df['Year'].min()),
    end=int(air_quality_df['Year'].max()),
    value=int(air_quality_df['Year'].max()),
    step=1,
    width=400,
    bar_color="#FAFAFA",
    css_classes=["custom-slider"]
)

# Update Grouped Bar Chart Data
def update_grouped_bar_chart(attr, old, new):
    selected_countries = grouped_bar_country_select.value
    selected_year = grouped_bar_year_slider.value

    # Call the function and automatically sort by 'PM2.5'
    grouped_data = prepare_grouped_bar_chart_data(selected_countries, selected_year, sort_by_pollutant='PM2.5')

    # Update the grouped bar chart data source
    grouped_bar_source.data = {
        'Country': grouped_data['Country'],
        'PM2.5': grouped_data['PM2.5'],
        'PM10': grouped_data['PM10'],
        'Ozone': grouped_data['Ozone'],
        'NO2': grouped_data['NO2'],
        'SO2': grouped_data['SO2'],
        'CO': grouped_data['CO']
    }

    # Update y_range with sorted country names for horizontal bar chart
    grouped_bar_fig.y_range.factors = list(grouped_data['Country'])
    grouped_bar_fig.title.text = f"Grouped Bar Chart: Pollutant Concentrations ({selected_year})"

# Attach update functions to widgets
grouped_bar_country_select.on_change("value", update_grouped_bar_chart)
grouped_bar_year_slider.on_change("value", update_grouped_bar_chart)

# Initialize Grouped Bar Chart Data
update_grouped_bar_chart(None, None, None)

# Layout for Grouped Bar Chart Tab
grouped_bar_tab = TabPanel(
    child=column(row(grouped_bar_country_select, grouped_bar_year_slider), grouped_bar_fig),
    title="Grouped Bar Chart"
)


# ---- Map Plot Tab ----

# Load Dataset
file_path = 'expanded_air_quality_data.csv'
data = pd.read_csv(file_path)

# Ensure numeric columns are correctly typed
for col in ['PM2.5', 'AQI', 'PM10', 'CO', 'SO2', 'NO2', 'Ozone']:
    data[col] = pd.to_numeric(data[col], errors='coerce')

# Parse dates with the correct format (dd-mm-yyyy)
data['Date'] = pd.to_datetime(data['Date'], format='%d-%m-%Y', errors='coerce')

# Add year column
data['Year'] = data['Date'].dt.year

# Select only numeric columns for aggregation
numeric_columns = ['PM2.5', 'AQI', 'PM10', 'CO', 'SO2', 'NO2', 'Ozone']
map_data = data.groupby(['Country', 'Year'])[numeric_columns].mean().reset_index()

# Load GeoJSON File (replace with the path to your shapefile)
shapefile_path = "ne_110m_admin_0_countries/ne_110m_admin_0_countries.shp"
world = gpd.read_file(shapefile_path)

# Merge GeoJSON with Dataset
merged_data = world.merge(map_data, left_on='NAME', right_on='Country', how='left')

# Initialize GeoJSONDataSource
geo_source = GeoJSONDataSource(geojson=merged_data.to_json())

# Prepare Map Figure
map_fig = figure(
    title="Interactive Map: PM2.5 by Country",
    width=1000,
    height=600,
    tools="pan,wheel_zoom,reset,save,hover",
    toolbar_location="left",
    background_fill_color="lightblue",
    background_fill_alpha=0.9,
    x_range=(-180, 180),  # Fix x-axis range to cover the world
    y_range=(-90, 90)     # Fix y-axis range to cover the world
)

# Define Color Mapping
color_mapper = LinearColorMapper(
    palette=Viridis256,
    low=merged_data['PM2.5'].min(skipna=True),
    high=merged_data['PM2.5'].max(skipna=True),
    nan_color="white"
)

# Add Patches to Map
# Add Patches to Map (Only Once)
map_fig.patches(
    'xs', 'ys',
    source=geo_source,
    fill_color=linear_cmap(
        'display_value', palette=Viridis256, low=color_mapper.low, high=color_mapper.high, nan_color="white"
    ),
    line_color="black",
    line_width=0.5,
    fill_alpha=0.7
)

# Add Enhanced Hover Tool
map_hover = HoverTool(tooltips=[
    ("Country", "@NAME"),
    ("Year", "@Year"),
    ("PM2.5 (µg/m³)", "@{PM2.5}{0.2f}"),
    ("AQI", "@AQI{0.2f}"),
    ("PM10 (µg/m³)", "@PM10{0.2f}"),
    ("CO (ppm)", "@CO{0.2f}"),
    ("SO2 (µg/m³)", "@SO2{0.2f}"),
    ("NO2 (µg/m³)", "@NO2{0.2f}"),
    ("Ozone (µg/m³)", "@Ozone{0.2f}"),
    ("Selected Pollutant", "@display_value{0.2f}")
])
map_fig.add_tools(map_hover)

# Add Color Bar
color_bar = ColorBar(
    color_mapper=color_mapper,
    label_standoff=12,
    location=(0, 0),
    title="Pollutant Level"
)
map_fig.add_layout(color_bar, 'right')

# Create a dynamic pollutant selector
pollutant_select = Select(
    title="Select Pollutant:",
    value="PM2.5",
    options=numeric_columns
)

# Create year dropdown
year_select = Select(
    title="Select Year:",
    value=str(int(data['Year'].min())),
    options=[str(year) for year in sorted(data['Year'].dropna().unique())]
)

# Create a Slider for Year Selection
year_slider = Slider(
    start=int(data['Year'].min()), 
    end=int(data['Year'].max()), 
    value=int(data['Year'].min()), 
    step=1, 
    title="Select Year",
    bar_color='#FAFAFA',  # Ensures the slider starts with a white bar
    css_classes=["custom-slider"]
)

# Updated Map Initialization
def update_map(attr, old, new):
    selected_pollutant = pollutant_select.value
    selected_year = int(year_slider.value)

    # Step 1: Filter and prepare data for the selected year
    year_data = map_data[map_data['Year'] == selected_year]
    merged = world.merge(year_data, left_on='NAME', right_on='Country', how='left')

    # Step 2: Update display_value for the selected pollutant
    merged['display_value'] = merged[selected_pollutant].apply(
        lambda x: None if pd.isna(x) or x == 0 else x
    )

    # Step 3: Update GeoJSON data without re-rendering the map
    geo_source.geojson = merged.to_json()

    # Step 4: Dynamically adjust the color mapper range without recreating it
    valid_data = merged['display_value'].dropna()
    if not valid_data.empty:
        color_mapper.low = valid_data.min()
        color_mapper.high = valid_data.max()

    # Step 5: Update only the title dynamically
    map_fig.title.text = f"Interactive Map: {selected_pollutant} in {selected_year}"


# Global Variables for Animation State
animation_running = False
callback_id = None  # Initialize callback_id to None globally

# Animation Logic
def animate():
    current_year = int(year_slider.value)
    if current_year < int(year_slider.end):
        year_slider.value = current_year + 1  # Increment year slider
    else:
        stop_animation()  # Stop when reaching the last year

def toggle_animation():
    """Start or stop the animation."""
    global animation_running, callback_id
    if not animation_running:
        animation_running = True
        animate_button.label = "Stop"
        callback_id = curdoc().add_periodic_callback(animate, 1000)  # 1000ms interval
    else:
        stop_animation()

def stop_animation():
    """Stop the animation and reset the button."""
    global animation_running, callback_id
    if animation_running and callback_id:
        curdoc().remove_periodic_callback(callback_id)
        animation_running = False
        animate_button.label = "Play"

# Reset Functionality
def reset_animation():
    """Reset slider to start year and stop animation."""
    stop_animation()
    year_slider.value = year_slider.start  # Reset slider to the starting year
    update_map(None, None, None)  # Update the map to reflect the reset year

# Attach Button Callbacks
animate_button = Button(label="Play", button_type="success")
reset_button = Button(label="Reset", button_type="warning", width=100)

animate_button.on_click(toggle_animation)
reset_button.on_click(reset_animation)

# Update Map Function
def update_map(attr, old, new):
    selected_pollutant = pollutant_select.value
    selected_year = int(year_slider.value)

    # Filter and merge data for the selected year
    year_data = map_data[map_data['Year'] == selected_year]
    filtered_data = world.copy()
    merged = filtered_data.merge(year_data, left_on='NAME', right_on='Country', how='left')

    # Assign display_value for visualization
    merged['display_value'] = merged[selected_pollutant].apply(
        lambda x: None if pd.isna(x) or x == 0 else x
    )
    # Update GeoJSON source
    geojson_data = merged.to_json()
    geo_source.geojson = geojson_data

    # Update color mapper range dynamically
    valid_data = merged['display_value'].dropna()
    if not valid_data.empty:
        color_mapper.low = valid_data.min()  # Dynamically set low value
        color_mapper.high = valid_data.max()  # Dynamically set high value
    else:
        color_mapper.low, color_mapper.high = 0, 1  # Default values if no data
        
    map_fig.renderers = []  # Clear previous patches
    map_fig.patches(
        'xs', 'ys',
        source=geo_source,
        fill_color=linear_cmap(
            'display_value', palette=Viridis256, 
            low=color_mapper.low, high=color_mapper.high, 
            nan_color="white"
        ),
        line_color="black",
        line_width=0.5,
        fill_alpha=0.7
    )

    # Update map title
    map_fig.title.text = f"Interactive Map: {selected_pollutant} in {selected_year}"




# Link Dropdowns and Slider to Map Update
pollutant_select.on_change('value', lambda attr, old, new: update_map(None, None, None))
year_slider.on_change('value', update_map)

# Add a JavaScript callback to modify the slider bar
# Add a JavaScript callback to ensure the slider bar stays white
slider_callback = CustomJS(args=dict(slider=year_slider), code="""
    // Access the slider element in the DOM
    let sliderElement = slider.el.querySelector('.noUi-connects');
    
    // Ensure the slider's line is fully #FAFAFA at all times
    if (sliderElement) {
        sliderElement.style.background = 'white';  // Set the slider line color to #FAFAFA
    }
""");

# Attach the callback to the slider's value change
year_slider.js_on_change("value", slider_callback)


# Layout
buttons_layout = row(animate_button, reset_button, sizing_mode='stretch_width')
map_layout = column(pollutant_select, year_slider, buttons_layout, map_fig)


# Initialize Map with Default Settings
update_map(None, None, None)

goespa_tab = TabPanel(child=map_layout, title="Pollutants Map")



# ---- Box Plot Tab ----
# Pollutant Columns with Units
# Define a function to get units for pollutants
def get_unit(pollutant):
    units = {
        "PM2.5": "µg/m³",
        "PM10": "µg/m³",
        "Ozone": "ppb",
        "NO2": "ppb",
        "SO2": "ppb",
        "CO": "ppm"
    }
    return units.get(pollutant, "")


# Prepare Data
df['Month'] = df['Date'].dt.strftime('%b')  # Extract Month Abbreviation
df['Year'] = df['Date'].dt.year  # Extract Year

# Function to Prepare Boxplot Data
def prepare_boxplot_data(data, pollutant, year, city):
    filtered_data = data[(data['Year'] == year) & (data['City'] == city)]
    boxplot_data = []
    
    for month in filtered_data['Month'].unique():
        month_data = filtered_data[filtered_data['Month'] == month][pollutant].dropna()
        if not month_data.empty:
            boxplot_data.append({
                'Month': month,
                'Q1': month_data.quantile(0.25),
                'Q2': month_data.median(),
                'Q3': month_data.quantile(0.75),
                'Lower': month_data.min(),
                'Upper': month_data.max()
            })
    
    return pd.DataFrame(boxplot_data)

# Initialize Default Data
# Define a function to get units for pollutants
def get_unit(pollutant):
    units = {
        "PM2.5": "µg/m³",
        "PM10": "µg/m³",
        "Ozone": "ppb",
        "NO2": "ppb",
        "SO2": "ppb",
        "CO": "ppm"
    }
    return units.get(pollutant, "")

# Prepare Data
df['Month'] = df['Date'].dt.strftime('%b')  # Extract Month Abbreviation
df['Year'] = df['Date'].dt.year  # Extract Year

# Group data for pollutants by city, year, and month
box_data = df.groupby(['City', 'Year', 'Month'])[pollutant_columns].describe().reset_index()

# Default selections
default_city = box_data['City'].unique()[0]
default_year = box_data['Year'].min()
default_pollutant = 'PM2.5'

# Function to prepare boxplot data
# Function to prepare boxplot data
def prepare_boxplot_data(city, year, pollutant):
    filtered = box_data[(box_data['City'] == city) & (box_data['Year'] == year)]
    
    # Extract quartile statistics
    q1 = filtered[(pollutant, '25%')]
    q2 = filtered[(pollutant, '50%')]  # Median
    q3 = filtered[(pollutant, '75%')]
    lower = filtered[(pollutant, 'min')]
    upper = filtered[(pollutant, 'max')]
    months = filtered['Month']

    return ColumnDataSource(data=dict(
        Month=months,
        Lower=lower,
        Q1=q1,
        Median=q2,
        Q3=q3,
        Upper=upper
    )), lower.min(), upper.max()  # Return min and max for y-axis adjustment


# Initialize data for the default display
box_source, global_min, global_max = prepare_boxplot_data(default_city, default_year, default_pollutant)

# Box Plot Figure
box_fig = figure(
    title=f"{default_pollutant} ({get_unit(default_pollutant)}) Distribution by Month for {default_city} ({default_year})",
    x_axis_label="Month",
    y_axis_label=f"Concentration ({get_unit(default_pollutant)})",
    width=1000,
    height=600,
    tools="pan,box_zoom,reset,save",
    x_range=sorted(box_source.data['Month']),  # Ensure month names are sorted
    y_range=(global_min * 0.9, global_max * 1.1)  # Dynamically set y-range
)

# Add boxes (Q1 to Q3)
box_fig.vbar(
    x='Month', width=0.7, top='Q3', bottom='Q1',
    source=box_source, fill_color="lightblue", line_color="black"
)

# Add whiskers for min and max
whisker = Whisker(base="Month", lower="Lower", upper="Upper", source=box_source, line_width=2)
box_fig.add_layout(whisker)

# Add median markers
box_fig.scatter(x='Month', y='Median', size=8, color="red", source=box_source)

# Add hover tool
hover = HoverTool(
    tooltips=[
        ("Month", "@Month"),
        ("Q1 (25%)", "@Q1{0.2f}"),
        ("Median (50%)", "@Median{0.2f}"),
        ("Q3 (75%)", "@Q3{0.2f}"),
        ("Min", "@Lower{0.2f}"),
        ("Max", "@Upper{0.2f}")
    ],
    mode="mouse"
)
box_fig.add_tools(hover)

# Dropdowns for city, year, and pollutant
box_city_select = Select(title="Select City:", value=default_city, options=sorted(box_data['City'].unique()))
box_year_select = Select(
    title="Select Year:",
    value=str(default_year),
    options=[str(year) for year in sorted(box_data['Year'].unique())]
)
box_pollutant_select = Select(title="Select Pollutant:", value=default_pollutant, options=pollutant_columns)

# Update function
def update_box_plot(attr, old, new):
    selected_city = box_city_select.value
    selected_year = int(box_year_select.value)
    selected_pollutant = box_pollutant_select.value
    
    # Prepare new data
    new_source, new_min, new_max = prepare_boxplot_data(selected_city, selected_year, selected_pollutant)
    box_source.data.update(new_source.data)
    
    # Update y-range dynamically
    box_fig.y_range.start = new_min * 0.9
    box_fig.y_range.end = new_max * 1.1

    # Update title
    box_fig.title.text = f"{selected_pollutant} ({get_unit(selected_pollutant)}) Distribution by Month for {selected_city} ({selected_year})"

# Attach callbacks
box_city_select.on_change("value", update_box_plot)
box_year_select.on_change("value", update_box_plot)
box_pollutant_select.on_change("value", update_box_plot)

# Layout
box_plot_layout = column(row(box_city_select, box_year_select, box_pollutant_select), box_fig)

boxplot_tab = TabPanel(child=box_plot_layout, title="Box Plot")


# ---- stacked area plot Tab ----


# Load dataset
df = pd.read_csv('expanded_air_quality_data.csv')  # Update this path
df['Date'] = pd.to_datetime(df['Date'], dayfirst=True)

# Pollutant and unit mappings
pollutants_units = {
    'PM2.5': 'µg/m³',
    'PM10': 'µg/m³',
    'Ozone': 'ppb',
    'NO2': 'ppb',
    'SO2': 'ppb',
    'CO': 'ppm'
}

# Add colors for pollutants
pollutant_colors = {
    'PM2.5': 'dodgerblue',
    'PM10': 'orange',
    'Ozone': 'green',
    'NO2': 'red',
    'SO2': 'purple',
    'CO': 'brown'
}

# Preprocess data
df_long = pd.melt(df, id_vars=['Date'], value_vars=pollutants_units.keys(),
                  var_name='Pollutant', value_name='Concentration')
df_long['Unit'] = df_long['Pollutant'].map(lambda x: pollutants_units[x])
df_long['Color'] = df_long['Pollutant'].map(lambda x: pollutant_colors[x])

# Extract unique years and units
years = sorted(df_long['Date'].dt.year.unique())
units = list(set(pollutants_units.values()))  # Unique units
initial_unit = units[0]
initial_year = years[0]

# Initialize ColumnDataSource
source = ColumnDataSource(data={'Date': [], 'Concentration': []})

# Create the figure
plot = figure(title=f"Pollutant Concentrations Over Time ({initial_year})",
              x_axis_label="Date", y_axis_label="Concentration",
              x_axis_type="datetime", width=900, height=500,
              tools="pan,box_zoom,reset,save")

# Add hover tool
hover = HoverTool(tooltips=[
    ("Date", "@Date{%F}"),
    ("Pollutant", "$name"),
    ("Concentration", "@$name{0.2f}"),
    ("Unit", "@Unit")
], formatters={'@Date': 'datetime'}, mode='vline')
plot.add_tools(hover)



# Function to prepare data
def prepare_data(unit, year):
    filtered = df_long[(df_long['Unit'] == unit) & (df_long['Date'].dt.year == year)]
    if filtered.empty:  # If no data exists, return an empty DataFrame
        return pd.DataFrame({'Date': [], 'Pollutant': [], 'Concentration': []})
    grouped = filtered.groupby(['Date', 'Pollutant'])['Concentration'].mean().reset_index()
    pivoted = grouped.pivot(index='Date', columns='Pollutant', values='Concentration').fillna(0)
    return pivoted

def update_plot(attr, old, new):
    selected_unit = unit_dropdown.label
    selected_year = int(year_dropdown.value)

    pivoted = prepare_data(selected_unit, selected_year)
    if pivoted.empty:  # Handle empty dataset
        source.data = {'Date': []}
        for col in pollutants_units.keys():
            source.data[col] = []
        plot.title.text = f"No data available for {selected_unit} in {selected_year}"
        plot.renderers = []  # Remove existing renderers
        plot.legend.items = []  # Clear legend
        return

    # Update source data directly
    new_data = {'Date': pivoted.index.tolist()}
    for col in pivoted.columns:
        new_data[col] = pivoted[col].tolist()
    source.data = new_data

    # Update the title
    plot.title.text = f"Pollutant Concentrations Over Time ({selected_year})"

    # Update the varea_stack
    stackers = list(pivoted.columns)
    colors = [pollutant_colors[stacker] for stacker in stackers]

    # Remove existing renderers to avoid duplication
    plot.renderers = []

    renderers = plot.varea_stack(
        stackers=stackers,
        x='Date',
        source=source,
        color=colors,
        legend_label=[f"{stacker} ({pollutants_units[stacker]})" for stacker in stackers],
        name=stackers  # Assign `name` to each renderer for dynamic updates
    )

    # Dynamically update the legend
    legend_items = [
        LegendItem(label=f"{stacker} ({pollutants_units[stacker]})", renderers=[renderer])
        for stacker, renderer in zip(stackers, renderers)
    ]
    plot.legend.items = legend_items
    plot.legend.click_policy = "hide"  # Make legend items clickable

# Dropdown for unit selection
unit_dropdown = Dropdown(label=initial_unit, button_type="success",
                         menu=[(unit, unit) for unit in units])

def update_unit(event):
    unit_dropdown.label = event.item
    update_plot(None, None, None)

unit_dropdown.on_click(update_unit)

# Dropdown for year selection
year_dropdown = Select(title="Select Year", value=str(initial_year),
                       options=[str(year) for year in years])
year_dropdown.on_change("value", update_plot)

# Initial plot setup
update_plot(None, None, None)

# Layout
layout = column(row(unit_dropdown, year_dropdown), plot)
stacked_tab = TabPanel(child=layout, title="Stacked Area Chart")



# Custom CSS for the slider
custom_css = """
<style>
    .custom-slider .bk-slider-bar {
        background-color: #FAFAFA !important;
    }
    .custom-slider .bk-slider-title {
        color: black !important;
    }
    .custom-slider .noUi-connects {
        background-color: #FAFAFA !important;
    }
    .noUi-connects {
        background-color: #FAFAFA !important;
    }
    .bk-input-group .noUi-target .noUi-base .noUi-connects {
        background-color: #FAFAFA !important;
    }
    .noUi-connects, 
    .bk-input-group .noUi-target .noUi-base .noUi-connects {
        background-color: #FAFAFA !important;
    }
</style>
"""
css_div = Div(text=custom_css)




# Store initial states
initial_scatter_source = scatter_source.data.copy()
initial_regional_source = regional_source.data.copy()
initial_monthly_source = monthly_source.data.copy()
initial_yr_source = yr_source.data.copy()
initial_grouped_bar_source = grouped_bar_source.data.copy()
initial_box_source = box_source.data.copy()
initial_time_series_fig_renderers = time_series_fig.renderers.copy()
initial_map_geojson = geo_source.geojson

def reset_dashboard(event):
    # Reset data sources
    scatter_source.data = initial_scatter_source
    regional_source.data = initial_regional_source
    monthly_source.data = initial_monthly_source
    yr_source.data = initial_yr_source
    grouped_bar_source.data = initial_grouped_bar_source
    box_source.data = initial_box_source

    # Reset plot renderers and legends
    time_series_fig.renderers = initial_time_series_fig_renderers.copy()
    geo_source.geojson = initial_map_geojson
    
    # Reset dropdowns, sliders, and titles
    country_select.value = "All"
    city_select.value = "All"
    pollutant_dropdown.value = 'PM2.5'
    yr_dropdown.value = str(default_year)
    month_slider.value = 1
    grouped_bar_year_slider.value = grouped_bar_year_slider.start
    box_city_select.value = default_city
    box_year_select.value = str(default_year)
    box_pollutant_select.value = 'PM2.5'
    unit_dropdown.label = initial_unit
    year_dropdown.value = str(initial_year)
    animate_button.label = "Play"

# Attach reset callback to each figure
scatter_fig.on_event('reset', reset_dashboard)
regional_fig.on_event('reset', reset_dashboard)
monthly_fig.on_event('reset', reset_dashboard)
yr_fig.on_event('reset', reset_dashboard)
grouped_bar_fig.on_event('reset', reset_dashboard)
box_fig.on_event('reset', reset_dashboard)
time_series_fig.on_event('reset', reset_dashboard)
map_fig.on_event('reset', reset_dashboard)



# Define Tabs
tabs = Tabs(tabs=[
    scatter_tab, regional_tab, heatmap_tab, time_series_tab,
    grouped_bar_tab,
    goespa_tab, boxplot_tab,stacked_tab
])



# Assemble Dashboard
dashboard_layout = column(css_div,tabs)
curdoc().add_root(dashboard_layout)
curdoc().title = "Air Quality Dashboard"
