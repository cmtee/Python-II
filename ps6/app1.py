from shiny import App, ui
from shinywidgets import render_altair, output_widget
import pandas as pd
import altair as alt
import os
import json

# Load your data
directory = r'C:\Users\clari\OneDrive\Documents\Python II\problem set 6'
merged_df_path = os.path.join(directory, "merged_df.csv")
merged_df = pd.read_csv(merged_df_path)
crosswalk_df_path = os.path.join(directory, "crosswalk_df.csv")
crosswalk_df = pd.read_csv(crosswalk_df_path)

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

app_ui = ui.page_fluid(
    ui.input_select("type_subtype_subsubtype", "Select Type - Subtype - Subsubtype", type_subtype_subsubtype_combinations),
    output_widget("map_plot")
)

def server(input, output, session):
    @output
    @render_altair
    def map_plot():
        selected = input.type_subtype_subsubtype()
        selected_parts = selected.split(" - ")
        selected_type = selected_parts[0]
        selected_subtype = selected_parts[1]
        selected_subsubtype = selected_parts[2] if len(selected_parts) > 2 else None

        # Filter data based on selection
        filtered_data = merged_df[ 
            (merged_df['updated_type'] == selected_type) & 
            (merged_df['updated_subtype'] == selected_subtype)
        ]
        if selected_subsubtype:
            filtered_data = filtered_data[filtered_data['updated_subsubtype'] == selected_subsubtype]
        
        # Aggregate and get top 10 locations
        aggregated = filtered_data.groupby(['binned_latitude', 'binned_longitude', 'user_friendly_label']).size().reset_index(name='alert_count')
        top_10 = aggregated.nlargest(10, 'alert_count')
        
        # Base map using identity projection and flipped Y-axis
        base = alt.Chart(geo_data).mark_geoshape(
            fill='lightgray',
            stroke='white'
        ).project(
            type='identity',  # Identity projection
            reflectY=True  # Flip y-axis
        ).properties(
            width=600,
            height=400
        )
        
        # Points layer with user_friendly_label for color
        points = alt.Chart(top_10).mark_circle().encode(
            longitude='binned_longitude:Q',
            latitude='binned_latitude:Q',
            size=alt.Size('alert_count:Q', scale=alt.Scale(range=[50, 500])),
            color=alt.Color('user_friendly_label:N', legend=None),  # Color by use_friendly_label
            tooltip=['binned_longitude', 'binned_latitude', 'alert_count', 'user_friendly_label']  # Show label in tooltip
        )

        # Combine the base map and points layers
        chart = alt.layer(base, points).properties(
            width=600,
            height=400,
            title=f'Top 10 Locations for {selected_type} - {selected_subtype}'
        ).configure_view(
            strokeWidth=0
        ).configure_axis(
            grid=False
        )
        
        return chart

app = App(app_ui, server)

if __name__ == "__main__":
    app.run()
