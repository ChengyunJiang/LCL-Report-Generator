import streamlit as st
import pandas as pd
import datetime
import altair as alt

st.markdown("""
    <style>
    .refresh-button {
        position: fixed;
        top: 10px;
        right: 10px;
        z-index: 100;
    }
    </style>
    <div class="refresh-button">
        <form action="" method="get">
            <button type="submit"> Refresh</button>
        </form>
    </div>
""", unsafe_allow_html=True)

hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .css-1dp5vir {display: none;} 
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

st.set_page_config(layout="wide")
st.title("Monthly Report Generator")

uploaded_files = st.file_uploader("Upload Excel files", accept_multiple_files=True, type=["xlsx"])

if uploaded_files:
    status_placeholder = st.empty()
    status_placeholder.info("Data Procesing...")
    dfs = []
    loss_dfs = []
    for file in uploaded_files:
        filename = file.name.lower()
        if "rail" in filename:
            loss_df = pd.read_excel(file)
            if 'SHAE' in loss_df.columns:
                loss_df["MMSCN"] = loss_df["SHAE"]
            else:
                loss_df["MMSCN"] = loss_df.iloc[:, 4]
            if "Formula.7" in loss_df.columns:
                loss_df["Total_Profit"] = pd.to_numeric(loss_df["Formula.7"], errors="coerce")
                loss_df["Shared_Profit"] = loss_df["Total_Profit"]/2
            loss_dfs.append(loss_df[["Shared_Profit","MMSCN"]])
        else:
            sheets = pd.read_excel(file, sheet_name = None)
            for sheet_name, df in sheets.items():
                if df.dropna(how='all').empty:
                    continue
                df["route"] = sheet_name 
                df["ETD"] = pd.to_datetime(df["ETD"], errors="coerce") 
                df["weeknum"] = df["ETD"].dt.strftime("%U").astype(float).astype("Int64") + 1
                dfs.append(df)

    status_placeholder.empty()

    df = pd.concat(dfs, ignore_index=True)
    df["weeknum"] = df["weeknum"].astype(str)
    # 合并所有盈亏表
    if loss_dfs:
        loss_df = pd.concat(loss_dfs, ignore_index=True)
        df = pd.merge(df, loss_df, on="MMSCN", how="left")

    status_placeholder.empty()
    cbm = df.groupby(["route", "weeknum"], as_index=False)[["Chrgb CBM"]].sum()
    with st.expander("📋 Data Uploaded"):
        st.dataframe(df.drop(columns=["Type of packaging"]))

    profit_summary = df.groupby(["route", "weeknum"], as_index=False)["Shared_Profit"].sum()
    profit_summary["color"] = profit_summary["Shared_Profit"].apply(lambda x: "#CA001D" if x < 0 else "#498684")


    unique_counts = df.drop_duplicates(subset=["route", "Containerno", "ETD", "weeknum"])
    weekly_unique_counts = unique_counts.groupby(["route","weeknum"]).size().reset_index(name="FEU")
    total_unique_pairs = weekly_unique_counts.sum()

    summary = pd.merge(cbm, weekly_unique_counts, on=["route","weeknum"], how="outer")
    summary["TEU"] = summary["FEU"]*2
    summary["AVG L/D"] = summary["Chrgb CBM"]/summary["FEU"]/76.3*100
    summary = summary.sort_values(["route", "weeknum"])

    tab1, tab2 = st.tabs(["Charts", "Pies"])
    with tab1:
        selected_route = st.selectbox("📍 Select a Route", ["ALL"] + sorted(summary["route"].dropna().unique()))
        if selected_route == "ALL":
            charts = []
            for route in summary["route"].dropna().unique():
                route_data = summary[summary["route"] == route]
                profit_data = profit_summary[profit_summary["route"] == route]
                # TEU chart
                teu_chart = alt.Chart(route_data).mark_bar(color="#498684").encode(
                    x=alt.X("weeknum:O", title="Week Number"),
                    y=alt.Y("TEU:Q", title=""),
                    tooltip=["weeknum", "TEU"]
                ).properties(
                    title=alt.TitleParams(text=f"Vol(TEU) - {route}", fontSize=20, fontWeight="bold", anchor="start", offset=10),
                    width=200, height=300
                )
                total_teu = alt.Chart(pd.DataFrame({"x": [0], "y": [0]})).mark_text(
                    text=f"TTL {route_data['TEU'].sum():.0f} TEU",
                    color="#CA001D", fontSize=20, fontWeight="bold", align="center", dy=-30
                ).encode(x=alt.value(0), y=alt.value(0))
                teu_text = alt.Chart(route_data).mark_text(
                    color="#498684", align="center", baseline="bottom", dy=-5, fontSize=12
                ).encode(x="weeknum:O", y="TEU:Q", text=alt.Text("TEU:Q"))

                # CBM chart
                cbm_chart = alt.Chart(route_data).mark_bar(color="#498684").encode(
                    x=alt.X("weeknum:O", title="Week Number"),
                    y=alt.Y("Chrgb CBM:Q", title=""),
                    tooltip=["weeknum", "Chrgb CBM"]
                ).properties(
                    title=alt.TitleParams(text=f"Vol(C.CBM) - {route}", fontSize=20, fontWeight="bold", anchor="start", offset=10),
                    width=200, height=300
                )
                total_cbm = alt.Chart(pd.DataFrame({"x": [0], "y": [0]})).mark_text(
                    text=f"TTL {route_data['Chrgb CBM'].sum():.0f} CBM",
                    color="#CA001D", fontSize=20, fontWeight="bold", align="center", dy=-30
                ).encode(x=alt.value(0), y=alt.value(0))
                cbm_text = alt.Chart(route_data).mark_text(
                    color="#498684", align="center", baseline="bottom", dy=-5, fontSize=12
                ).encode(x="weeknum:O", y="Chrgb CBM:Q", text=alt.Text("Chrgb CBM:Q", format=".1f"))

                # LD chart
                avg_ld = route_data["AVG L/D"].mean()
                ld_chart = alt.Chart(route_data).mark_line(color="#498684").encode(
                    x=alt.X("weeknum:O", title="Week Number"),
                    y=alt.Y("AVG L/D:Q", title=""),
                    tooltip=["weeknum", "AVG L/D"]
                ).properties(
                    title=alt.TitleParams(text=f"LD(%) - {route}", fontSize=20, fontWeight="bold", anchor="start", offset=10),
                    width=200, height=300
                )
                ld_points = alt.Chart(route_data).mark_point(color="#498684", filled=True, size=80).encode(
                    x="weeknum:O", y="AVG L/D:Q", tooltip=["weeknum", "AVG L/D"]
                )
                avg_line = alt.Chart(pd.DataFrame({"y": [avg_ld]})).mark_rule(
                    color="#E4BDC2", strokeWidth=2).encode(y="y:Q")
                avg_text = alt.Chart(pd.DataFrame({"x": [0], "y": [0]})).mark_text(
                    text=f"AVG {avg_ld:.0f} %",
                    color="#CA001D", fontSize=20, fontWeight="bold", align="center", dy=-30
                ).encode(x=alt.value(0), y=alt.value(0))

                if profit_data is not None:
                    profit_chart = alt.Chart(profit_data).mark_bar().encode(
                        x=alt.X("weeknum:N", title="Week Number"),
                        y=alt.Y("Shared_Profit:Q", title="Shared_Profit"),
                        color=alt.Color("color:N", scale=None, legend=None),
                        tooltip=["route", "weeknum", "Shared_Profit"]
                    ).properties(
                        width=200,
                        height=300,
                        title="Weekly Shared Profit"
                    )
                    total_profit = alt.Chart(pd.DataFrame({"x": [0], "y": [0]})).mark_text(
                        text=f"TTL {profit_data['Shared_Profit'].sum():.0f} USD",
                        color="#CA001D", fontSize=20, fontWeight="bold", align="center", dy=-30
                        ).encode(x=alt.value(0), y=alt.value(0))
                    route_charts = alt.vconcat(
                        teu_chart + total_teu + teu_text,
                        cbm_chart + total_cbm + cbm_text,
                        ld_chart + ld_points + avg_line + avg_text,
                        profit_chart + total_profit
                    ).resolve_scale(y='independent')
                else:
                    route_charts = alt.vconcat(
                        teu_chart + total_teu + teu_text,
                        cbm_chart + total_cbm + cbm_text,
                        ld_chart + ld_points + avg_line + avg_text
                    ).resolve_scale(y='independent')
                charts.append(route_charts)
            full_chart = alt.hconcat(*charts)
        else:
            data = summary[summary["route"] == selected_route]
            profit_data = profit_summary[profit_summary["route"] == selected_route]
#-------TEU##################################################################################################################################
            teu_chart = alt.Chart(data).mark_bar(color = "#498684").encode(
                x=alt.X("weeknum:O", title="Week Number"),
                y=alt.Y("TEU:Q", title=""),
                tooltip=["weeknum", "TEU"]
                ).properties(
                title=alt.TitleParams(text="Vol(TEU)", fontSize=20, fontWeight="bold", anchor="start", offset=10),
                width=200,
                height=300
                )
            total_teu = alt.Chart(pd.DataFrame({"x": [0], "y": [0]})).mark_text(
                text=f"TTL {data["TEU"].sum():.0f} TEU",
                color="#CA001D",
                fontSize=20,
                fontWeight="bold",
                align="center",
                dy=-30  # 上移
            ).encode(
                x=alt.value(0),
                y=alt.value(0))
            teu_text = alt.Chart(data).mark_text(
                color = "#498684",
                align="center",
                baseline="bottom",
                dy=-5,
                fontSize=12).encode(
                x="weeknum:O",
                y="TEU:Q",
                text=alt.Text("TEU:Q"))
    #-------CBM##################################################################################################################################
            cbm_chart = alt.Chart(data).mark_bar(color = "#498684").encode(
                x=alt.X("weeknum:O", title="Week Number"),
                y=alt.Y("Chrgb CBM:Q", title=""),
                tooltip=["weeknum", "Chrgb CBM"]
                ).properties(
                title=alt.TitleParams(
            text="Vol(C.CBM)",
            fontSize=20,
            fontWeight="bold",
            anchor="start",
            offset=10
        ),
                width=200,
                height=300
                )
            total_cbm = alt.Chart(pd.DataFrame({"x": [0], "y": [0]})).mark_text(
                text=f"TTL {data["Chrgb CBM"].sum():.0f} CBM",
                color="#CA001D",
                fontSize=20,
                fontWeight="bold",
                align="center",
                dy=-30  # 上移
            ).encode(
                x=alt.value(0),
                y=alt.value(0))
            cbm_text = alt.Chart(data).mark_text(
                color = "#498684",
                align="center",
                baseline="bottom",
                dy=-5,
                fontSize=12).encode(
                x="weeknum:O",
                y="Chrgb CBM:Q",
                text=alt.Text("Chrgb CBM:Q", format=".1f"))

    #-------AVG L/D##################################################################################################################################
            avg_ld = data["AVG L/D"].mean()
            ld_chart = alt.Chart(data).mark_line(color = "#498684").encode(
                x=alt.X("weeknum:O", title="Week Number"),
                y=alt.Y("AVG L/D:Q", title=""),
                tooltip=["weeknum", "AVG L/D"]).properties(
                title=alt.TitleParams(text="LD(%)", fontSize=20,fontWeight="bold",anchor="start",offset=10),
                width=200,
                height=300)
            ld_points = alt.Chart(data).mark_point(color="#498684", filled=True, size=80).encode(
                x="weeknum:O",
                y="AVG L/D:Q",
                tooltip=["weeknum", "AVG L/D"])
            avg_line = alt.Chart(pd.DataFrame({"y": [avg_ld]})).mark_rule(
                color="#E4BDC2", strokeWidth=2).encode(y="y:Q")
            # avg_text = alt.Chart(pd.DataFrame({"y": [avg_ld]})).mark_text(
            #     text=f"Average: {avg_ld:.1f}%",
            #     align="left", baseline="bottom", dx=5, dy=-5, color="#CA001D").encode(x=alt.value(0), y="y:Q")
            avg_text = alt.Chart(pd.DataFrame({"x": [0], "y": [0]})).mark_text(
                text=f"AVG {data["AVG L/D"].mean():.0f} %",
                color="#CA001D",
                fontSize=20,
                fontWeight="bold",
                align="center",
                dy=-30  # 上移
            ).encode(
                x=alt.value(0),
                y=alt.value(0))
            
            if profit_data is not None:
                profit_chart = alt.Chart(profit_data).mark_bar().encode(
                    x=alt.X("weeknum:N", title="Week Number"),
                    y=alt.Y("Shared_Profit:Q", title="Shared_Profit"),
                    color=alt.Color("color:N", scale=None, legend=None),
                    tooltip=["route", "weeknum", "Shared_Profit"]
                ).properties(
                    width=200,
                    height=300,
                    title="Weekly Shared Profit"
                )
                total_profit = alt.Chart(pd.DataFrame({"x": [0], "y": [0]})).mark_text(
                        text=f"TTL {profit_data['Shared_Profit'].sum():.0f} USD",
                        color="#CA001D", fontSize=20, fontWeight="bold", align="center", dy=-30
                        ).encode(x=alt.value(0), y=alt.value(0))
                full_chart = alt.vconcat(
                teu_chart + total_teu + teu_text,
                cbm_chart + cbm_text + total_cbm,
                ld_chart + ld_points + avg_line + avg_text,
                profit_chart + total_profit).resolve_scale(
                    y='independent').properties(
                    title=f"{selected_route}").configure_title( 
                    fontSize=20,
                    color="#498684",
                    anchor='start')
            else:
    ##################################################################################################################################
                full_chart = alt.vconcat(
                    teu_chart + total_teu + teu_text,
                    cbm_chart + cbm_text + total_cbm,
                    ld_chart + ld_points + avg_line + avg_text).resolve_scale(
                        y='independent').properties(
                        title=f"{selected_route}").configure_title( 
                        fontSize=20,
                        color="#498684",
                        anchor='start')
        st.altair_chart(full_chart, use_container_width=True)
        with st.expander("📋 View raw data"):
            st.dataframe(profit_data)
            

    route_summary = summary.copy()
    agg_summary = route_summary.groupby("route", as_index=False).agg({
        "TEU": "sum",
        "Chrgb CBM": "sum",
        "AVG L/D": "mean"
    })

    def make_pie_chart(column, title, format_str):
        chart = alt.Chart(agg_summary).mark_arc(innerRadius=50).encode(
            theta=alt.Theta(f"{column}:Q"),
            color=alt.Color("route:N", legend=alt.Legend(title="Route")),
            tooltip=["route", column]
        ).properties(width=250, height=250, title=title)
        return chart


    with tab2:
        st.subheader("Route Share with Value Labels")
        pie_teu = make_pie_chart("TEU", "TEU Share", "f")
        pie_cbm = make_pie_chart("Chrgb CBM", "CBM Share", ".1f")
        pie_ld = make_pie_chart("AVG L/D", "Load Rate Share", ".1f")
        st.altair_chart(pie_teu | pie_cbm | pie_ld, use_container_width=False)

        # bar_chart = alt.Chart(agg_summary).mark_bar(color="#ca001d").encode(
        #     x=alt.X("route:N", sort='-y', title="Route"),
        #     y=alt.Y("TEU:Q", title="Total TEU"),
        #     tooltip=["route", "TEU"]
        # ).properties(width=600, height=400)

        # text = alt.Chart(agg_summary).mark_text(
        #     align='center', baseline='bottom', dy=-5
        # ).encode(
        #     x="route:N",
        #     y="TEU:Q",
        #     text=alt.Text("TEU:Q", format=".0f")
        # )

        # st.altair_chart(bar_chart + text, use_container_width=True)
        with st.expander("📋 View raw data"):
            st.dataframe(agg_summary)