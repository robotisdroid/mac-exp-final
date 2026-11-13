
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import folium
from streamlit_folium import st_folium


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="BMTC Transit Analytics",
    page_icon="🚌",
    layout="wide"
)

DATA_DIR = Path(__file__).parent / "data"


# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

@st.cache_data
def load_json(filename):
    path = DATA_DIR / filename

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


try:
    summary = load_json("summary.json")
    stops = load_json("stops.json")
    routes = load_json("routes.json")
    stop_routes = load_json("stop_routes.json")
    stop_hourly = load_json("stop_hourly.json")
    route_hourly = load_json("route_hourly.json")

except Exception as error:
    st.error(f"Could not load project data: {error}")
    st.stop()


stops_df = pd.DataFrame(stops)
routes_df = pd.DataFrame(routes)

route_lookup = {
    str(route["idx"]): route
    for route in routes
}


# --------------------------------------------------
# HEADER
# --------------------------------------------------

st.title("BMTC Transit Analytics")

st.markdown(
    "### Analysing and Optimising Public Transport Waiting Times"
)

st.caption(
    "A data-driven study of Bengaluru Metropolitan "
    "Transport Corporation (BMTC) bus services."
)

st.divider()


# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

st.sidebar.title("Navigation")

page = st.sidebar.radio(
    "Select a section",
    [
        "Overview",
        "Bus Stop Explorer",
        "Route Explorer",
        "Hourly Analysis",
        "Methodology"
    ]
)

st.sidebar.divider()

st.sidebar.caption(
    "Data source: BMTC GTFS dataset by Vonter."
)


# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------

def format_minutes(value):
    if pd.isna(value):
        return "N/A"

    return f"{value:.2f} min"


def get_hour_labels(length):
    return [
        f"{hour:02d}:00"
        for hour in range(length)
    ]


def get_stop_routes(stop_id):
    indices = stop_routes.get(str(stop_id), [])

    results = []

    for index in indices:
        route = route_lookup.get(str(index))

        if route:
            results.append(route)

    return results


def get_route_name(route):
    short = route.get("short", "Unknown")
    long = route.get("long", "")

    return f"{short} — {long}" if long else str(short)


# --------------------------------------------------
# PAGE 1: OVERVIEW
# --------------------------------------------------

if page == "Overview":

    st.header("Project Overview")

    st.write(
        "This dashboard analyses scheduled BMTC bus arrivals "
        "to understand service intervals, route patterns and "
        "the distribution of bus services across Bengaluru."
    )

    dataset = summary["dataset"]
    day = summary["day_counts"]
    overall = summary["intervals"]["overall"]

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Bus stops mapped",
        f"{len(stops_df):,}"
    )

    col2.metric(
        "Routes in dataset",
        f"{len(routes_df):,}"
    )

    col3.metric(
        "Monday trips",
        f"{day['trips']:,}"
    )

    col4.metric(
        "Monday timetable records",
        f"{day['stop_time_rows']:,}"
    )

    st.divider()

    st.subheader("Scheduled Interval Statistics")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Median interval",
        format_minutes(overall["median"])
    )

    c2.metric(
        "Average interval",
        format_minutes(overall["mean"])
    )

    c3.metric(
        "90th percentile",
        format_minutes(overall["p90"])
    )

    c4.metric(
        "Longest interval",
        format_minutes(overall["max"])
    )

    st.info(
        "These figures describe scheduled intervals between "
        "bus arrivals at stops. They are not measurements of "
        "actual passenger waiting times."
    )

    st.divider()

    st.subheader("Scheduled Intervals by Time of Day")

    bands = summary["intervals"]["by_band"]

    band_df = pd.DataFrame([
        {
            "Time period": band,
            "Median interval": values["median"],
            "Average interval": values["mean"],
            "Number of intervals": values["n"]
        }
        for band, values in bands.items()
    ])

    fig = px.bar(
        band_df,
        x="Time period",
        y="Median interval",
        color="Median interval",
        color_continuous_scale="Blues",
        title="Median Scheduled Interval by Time Period",
        labels={
            "Median interval": "Minutes",
            "Time period": "Time of day"
        },
        hover_data=["Average interval", "Number of intervals"]
    )

    fig.update_layout(
        showlegend=False,
        xaxis_title="",
        yaxis_title="Minutes"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Distribution of Scheduled Intervals")

    hist = summary["hist"]

    edges = hist["edges"]
    counts = hist["all"]["counts"]

    histogram_df = pd.DataFrame({
        "Interval": [
            f"{edges[i]}–{edges[i+1]} min"
            for i in range(len(counts))
        ],
        "Frequency": counts
    })

    fig = px.bar(
        histogram_df,
        x="Interval",
        y="Frequency",
        title="Distribution of Intervals (up to 180 minutes)",
        labels={
            "Frequency": "Number of intervals",
            "Interval": "Scheduled interval"
        }
    )

    fig.update_layout(
        xaxis_tickangle=-45
    )

    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        f"Additional intervals exceeding 180 minutes: "
        f"{hist['all']['over_180']:,}."
    )

    st.divider()

    st.subheader("Key Observations")

    st.markdown(
        """
        - The median scheduled interval is 15 minutes overall.
        - Evening and night periods have higher median intervals
          than the morning peak.
        - The mean interval is considerably higher than the median,
          indicating a distribution with some very long gaps.
        - Scheduled service patterns vary across stops and routes.
        """
    )


# --------------------------------------------------
# PAGE 2: BUS STOP EXPLORER
# --------------------------------------------------

elif page == "Bus Stop Explorer":

    st.header("Bus Stop Explorer")

    st.write(
        "Explore bus stops in Bengaluru, compare scheduled "
        "arrival intervals and identify the routes serving each stop."
    )

    search = st.text_input(
        "Search for a bus stop",
        placeholder="Enter a stop name..."
    )

    filtered_stops = stops_df.copy()

    if search:
        filtered_stops = filtered_stops[
            filtered_stops["name"].str.contains(
                search,
                case=False,
                na=False
            )
        ]

    st.write(
        f"Matching stops: {len(filtered_stops):,}"
    )

    if len(filtered_stops) > 0:

        filtered_stops = filtered_stops.sort_values(
            "arrivals_day",
            ascending=False
        )

        selected_name = st.selectbox(
            "Select a bus stop",
            filtered_stops["name"].tolist()
        )

        selected = filtered_stops[
            filtered_stops["name"] == selected_name
        ].iloc[0]

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Scheduled arrivals",
            f"{int(selected['arrivals_day']):,}"
        )

        col2.metric(
            "Routes serving stop",
            int(selected["n_routes"])
        )

        col3.metric(
            "Median interval",
            format_minutes(selected["median"])
        )

        col4.metric(
            "90th percentile",
            format_minutes(selected["p90"])
        )

        st.divider()

        st.subheader("Bus Stop Location")

        map_data = folium.Map(
            location=[
                float(selected["lat"]),
                float(selected["lon"])
            ],
            zoom_start=15
        )

        folium.Marker(
            [
                float(selected["lat"]),
                float(selected["lon"])
            ],
            tooltip=selected["name"],
            popup=selected["name"],
            icon=folium.Icon(color="red")
        ).add_to(map_data)

        st_folium(
            map_data,
            width=None,
            height=400,
            key="selected_stop_map"
        )

        st.divider()

        st.subheader("Routes Serving This Stop")

        serving_routes = get_stop_routes(selected["id"])

        if serving_routes:

            route_table = pd.DataFrame([
                {
                    "Route number": route.get("short", "Unknown"),
                    "Route": route.get("long", ""),
                    "Trips per day": route.get("trips_day", 0),
                    "Stops on route": route.get("n_stops", 0),
                    "Median interval (min)": route.get("median", 0)
                }
                for route in serving_routes
            ])

            st.dataframe(
                route_table,
                use_container_width=True,
                hide_index=True
            )

        else:
            st.info("No route information available for this stop.")

    else:
        st.warning("No matching bus stops found.")

    st.divider()

    st.subheader("Bengaluru Bus Stop Map")

    st.write(
        "The map displays up to 400 stops with the highest "
        "scheduled arrival counts."
    )

    map_stops = stops_df.nlargest(
        400,
        "arrivals_day"
    )

    city_map = folium.Map(
        location=[12.9716, 77.5946],
        zoom_start=11
    )

    for _, stop in map_stops.iterrows():

        folium.CircleMarker(
            location=[
                float(stop["lat"]),
                float(stop["lon"])
            ],
            radius=3,
            color="#1769aa",
            fill=True,
            fill_opacity=0.65,
            tooltip=stop["name"]
        ).add_to(city_map)

    st_folium(
        city_map,
        width=None,
        height=500,
        key="bengaluru_stops_map"
    )


# --------------------------------------------------
# PAGE 3: ROUTE EXPLORER
# --------------------------------------------------

elif page == "Route Explorer":

    st.header("Route Explorer")

    st.write(
        "Search BMTC routes and examine their scheduled "
        "service characteristics."
    )

    route_search = st.text_input(
        "Search by route number or destination",
        placeholder="Example: 104 or Majestic"
    )

    filtered_routes = routes_df.copy()

    if route_search:

        mask = (
            filtered_routes["short"].astype(str).str.contains(
                route_search,
                case=False,
                na=False
            )
            |
            filtered_routes["long"].astype(str).str.contains(
                route_search,
                case=False,
                na=False
            )
        )

        filtered_routes = filtered_routes[mask]

    st.write(
        f"Matching routes: {len(filtered_routes):,}"
    )

    if len(filtered_routes) > 0:

        filtered_routes = filtered_routes.head(500)

        route_options = {
            get_route_name(row): row
            for row in filtered_routes.to_dict("records")
        }

        selected_route_name = st.selectbox(
            "Select a route",
            list(route_options.keys())
        )

        route = route_options[selected_route_name]

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Trips per day",
            int(route.get("trips_day", 0))
        )

        c2.metric(
            "Stops on route",
            int(route.get("n_stops", 0))
        )

        c3.metric(
            "Median interval",
            format_minutes(route.get("median"))
        )

        c4.metric(
            "90th percentile",
            format_minutes(route.get("p90"))
        )

        st.subheader("Route Information")

        st.write("**Route:**", route.get("short", "Unknown"))
        st.write("**Direction / destination:**", route.get("long", "Not available"))
        st.write("**Service description:**", route.get("desc", "Not available"))

        st.caption(
            "Route statistics describe the schedule data "
            "represented in the dataset."
        )

    else:
        st.warning("No matching routes found.")


# --------------------------------------------------
# PAGE 4: HOURLY ANALYSIS
# --------------------------------------------------

elif page == "Hourly Analysis":

    st.header("Hourly Analysis")

    st.write(
        "Examine how scheduled bus arrivals are distributed "
        "throughout the service day."
    )

    analysis_type = st.radio(
        "Choose analysis",
        [
            "Bus stop",
            "Bus route"
        ],
        horizontal=True
    )

    if analysis_type == "Bus stop":

        selected_stop_name = st.selectbox(
            "Select a bus stop",
            sorted(stops_df["name"].dropna().unique().tolist()),
            key="hourly_stop"
        )

        selected_stop = stops_df[
            stops_df["name"] == selected_stop_name
        ].iloc[0]

        hourly_values = stop_hourly.get(
            str(selected_stop["id"])
        )

        if hourly_values:

            hourly_df = pd.DataFrame({
                "Service hour": get_hour_labels(len(hourly_values)),
                "Scheduled arrivals": hourly_values
            })

            fig = px.bar(
                hourly_df,
                x="Service hour",
                y="Scheduled arrivals",
                title=f"Hourly Arrivals: {selected_stop_name}"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

        else:
            st.info("Hourly information is unavailable for this stop.")

    else:

        route_options = {
            get_route_name(row): row
            for row in routes
        }

        selected_route_name = st.selectbox(
            "Select a bus route",
            list(route_options.keys()),
            key="hourly_route"
        )

        selected_route = route_options[selected_route_name]

        hourly_values = route_hourly.get(
            str(selected_route["idx"])
        )

        if hourly_values:

            hourly_df = pd.DataFrame({
                "Service hour": get_hour_labels(len(hourly_values)),
                "Scheduled arrivals": hourly_values
            })

            fig = px.bar(
                hourly_df,
                x="Service hour",
                y="Scheduled arrivals",
                title=f"Hourly Arrivals: Route {selected_route['short']}"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

        else:
            st.info("Hourly information is unavailable for this route.")

    st.caption(
        "Hours beyond 23:00 represent extended GTFS service-day "
        "times, which may refer to services after midnight."
    )


# --------------------------------------------------
# PAGE 5: METHODOLOGY
# --------------------------------------------------

elif page == "Methodology":

    st.header("Methodology")

    st.subheader("1. Data Source")

    st.write(
        "The analysis uses the publicly available BMTC GTFS "
        "dataset published by Vonter."
    )

    st.markdown(
        "[View BMTC GTFS dataset on GitHub]"
        "(https://github.com/Vonter/bmtc-gtfs)"
    )

    st.subheader("2. Data Processing")

    st.markdown(
        """
        - GTFS files were loaded and processed using Python and DuckDB.
        - Stop, route, trip and timetable information was combined.
        - Scheduled arrival times were converted into minutes.
        - Duplicate scheduled arrivals were removed.
        - Consecutive arrival times were compared to calculate
          scheduled intervals.
        - Arrival patterns were grouped by time of day.
        """
    )

    st.subheader("3. Statistical Measures")

    st.markdown(
        """
        **Mean:** Arithmetic average of scheduled intervals.

        **Median:** Middle value of the scheduled intervals.

        **90th percentile:** The value below which 90% of the
        calculated intervals fall.

        **Maximum:** Largest calculated interval in the dataset.
        """
    )

    st.subheader("4. Important Limitations")

    st.markdown(
        """
        - The dataset contains scheduled timetable information,
          not historical real-time bus arrival observations.
        - Scheduled intervals do not necessarily equal actual
          passenger waiting times.
        - The main overview uses Monday as its representative day.
        - Some very long intervals may represent overnight
          service gaps or timetable limitations.
        - Timetable accuracy depends on the underlying data source.
        - The mapped stop dataset excludes stops outside the
          selected Bengaluru geographical area.
        """
    )

    st.subheader("5. Interpretation")

    st.write(
        "The dashboard provides a mathematical analysis of "
        "scheduled public transport service patterns. Its "
        "statistics can help identify differences between "
        "routes, stops and time periods, but should not be "
        "interpreted as direct measurements of actual waiting "
        "experiences."
    )

    st.divider()

    st.caption(
        "Project: Analysing and Optimising Public Transport "
        "Waiting Times for College Students"
    )


# --------------------------------------------------
# FOOTER
# --------------------------------------------------

st.divider()

st.caption(
    "BMTC Transit Analytics | Academic Project | "
    "Data source: Vonter BMTC GTFS"
)
