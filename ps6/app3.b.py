from shiny import App, ui
from shinywidgets import render_altair, output_widget
import pandas as pd
import altair as alt
import json
import os

# Load your data
directory = r'C:\Users\clari\OneDrive\Documents\Python II\problem set 6'

# Load merged_df.csv (for type-subtype-subsubtype dropdown)
merged_df_path = os.path.join(directory, "merged_df.csv")
merged_df = pd.read_csv(merged_df_path)

# Load crosswalk_df.csv
crosswalk_df_path = os.path.join(directory, "crosswalk_df.csv")
crosswalk_df = pd.read_csv(crosswalk_df_path)

# Load top_alerts_map_byhour.csv (for slider filtering)
top_alerts_map_byhour_path = os.path.join(directory, "top_alerts_map_byhour.csv")
top_alerts_map_byhour = pd.read_csv(top_alerts_map_byhour_path)

# Load Chicago boundaries GeoJSON
with open(os.path.join(directory, "chicago-boundaries.geojson")) as f:
    chicago_geojson = json.load(f)
geo_data = alt.Data(values=chicago_geojson["features"])

# Create a list of type-subtype-subsubtype combinations
type_subtype_subsubtype_combinations = crosswalk_df.apply(
    lambda row: f"{row['updated_type']} - {row['updated_subtype']} - {row['updated_subsubtype']}" 
    if pd.notna(row['updated_subsubtype']) else f"{row['updated_type']} - {row['updated_subtype']}",
    axis=1
).unique().tolist()

# Define the UI
app_ui = ui.page_fluid(
    # Dropdown for selecting combination of Type - Subtype - Subsubtype
    ui.input_select("type_subtype_subsubtype", 
                    "Select Type - Subtype - Subsubtype", 
                    type_subtype_subsubtype_combinations),
    
    # Conditional panel for the slider
    ui.input_checkbox("toggle_slider", "Enable Hour Filter", value=False),
    
    # Conditional rendering of the slider based on checkbox input
    ui.input_slider("selected_hour", 
                    "Select Hour (6 AM to 9 AM)", 
                    min=6, 
                    max=9, 
                    value=6, 
                    step=1),
    
    ui.input_slider("selected_hour_range", 
                    "Select Hour Range (e.g., 7-9)", 
                    min=6, 
                    max=9, 
                    value=[6, 9],  # Default range from 6 AM to 9 AM
                    step=1,
                    animate=True),
    
    # Output for the map
    output_widget("map_plot")
)

# Define the server logic
def server(input, output, session):
    
    # Render map
    @output
    @render_altair
    def map_plot():
        # Get user inputs
        selected = input.type_subtype_subsubtype()
        selected_parts = selected.split(" - ")
        selected_type = selected_parts[0]
        selected_subtype = selected_parts[1]
        selected_subsubtype = selected_parts[2] if len(selected_parts) > 2 else None
        toggle_slider = input.toggle_slider()
        
        # Check if the slider for hour range is enabled or not
        if toggle_slider:
            # Get the selected range of hours
            selected_hour_range = input.selected_hour_range()
            selected_hour = None  # We don't use selected_hour when range is selected
        else:
            # Get the selected single hour
            selected_hour = input.selected_hour()
            selected_hour_range = [selected_hour, selected_hour]  # Only one hour in the range
        
        # Filter `merged_df` for dropdown selection
        merged_filtered = merged_df[ 
            (merged_df['updated_type'] == selected_type) & 
            (merged_df['updated_subtype'] == selected_subtype)
        ]
        
        if selected_subsubtype:
            merged_filtered = merged_filtered[merged_filtered['updated_subsubtype'] == selected_subsubtype]

        # Ensure top_alerts_map_byhour['hour'] is in proper format
        top_alerts_map_byhour['hour'] = pd.to_datetime(top_alerts_map_byhour['hour']).dt.tz_localize(None)
        
        # Filter `top_alerts_map_byhour` for selected hour range (only between 6 AM to 9 AM)
        hour_filtered = top_alerts_map_byhour[
            top_alerts_map_byhour['hour'].dt.hour.between(selected_hour_range[0], selected_hour_range[1])
        ]
        
        # Merge the datasets on `binned_latitude` and `binned_longitude`
        combined_data = pd.merge(
            merged_filtered,
            hour_filtered,
            on=['binned_latitude', 'binned_longitude'],  # Match locations
            how='inner'
        )

        # Sort by alert_count and get top 10 locations
        top_10 = combined_data.sort_values(by='alert_count', ascending=False).head(10)

        if top_10.empty:
            return alt.Chart().mark_text(
                text="No data available for selected hour and type-subtype.",
                align="center",
                baseline="middle",
                fontSize=20
            ).properties(width=600, height=400)

        # Base map using the Chicago GeoJSON
        base_map = alt.Chart(geo_data).mark_geoshape(
            fill='lightgray',
            stroke='white'
        ).properties(
            width=600,
            height=400
        )

        # Add points layer for top locations (alerts)
        points_layer = alt.Chart(top_10).mark_circle().encode(
            longitude='binned_longitude:Q',
            latitude='binned_latitude:Q',
            size=alt.Size('alert_count:Q', scale=alt.Scale(range=[10, 100])),
            color=alt.value('red'),
            tooltip=['binned_longitude', 'binned_latitude', 'alert_count']
        )

        # Combine base map and points layer for the final chart
        jam_hour_chart = alt.layer(base_map, points_layer).project(
            type='mercator',
            scale=50000,
            center=[-87.65, 41.88]  # Approximate center of Chicago
        ).properties(
            title=f"Top 10 Locations for Alerts at {selected_hour_range[0]}:00 - {selected_hour_range[1]}:00" if toggle_slider else f"Top 10 Locations for Alerts at {selected_hour}:00",
            width=600,
            height=400
        )

        return jam_hour_chart

# Create the app
app = App(app_ui, server)

# Run the app
if __name__ == "__main__":
    app.run()
