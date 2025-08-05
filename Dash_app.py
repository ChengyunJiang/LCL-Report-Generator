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
st.title("LCL Report Generator")

st.markdown("""
<div style='padding: 1rem; border-radius: 0.5rem; background-color: #F0F7F6;'>
  <h3 style='color: #225560;'>👋 欢迎使用LCL报表生成器</h3>
  <p style='font-size:16px; color:#444;'>
    本工具帮助您按 <b>周 / 月 / 季度</b> 维度分析 <b>TEU 运量</b> 与 <b>分成利润</b>，
    快速生成清晰的图表，追踪各条路线的运营表现。
  </p>
  <p style='font-size:15px; color:#444; margin-top:1em;'>
    👉 上传盈利表格时请注意标题需要包含<b>rail</b>(不用区分大小写)。
  </p>
</div>
""", unsafe_allow_html=True)

uploaded_files = st.file_uploader("📤 上传表格", accept_multiple_files=True, type=["xlsx"])
time_unit = st.selectbox("View by", ["Weekly", "Monthly", "Quarterly"])
if time_unit == "Weekly":
    time_col = "weeknum"
elif time_unit == "Monthly":
    time_col = "month"
else:
    time_col = "quarter"

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
                if "WEEKNUM" in df.columns:
                    df = df.drop(columns=["WEEKNUM"])
                df["ETD"] = pd.to_datetime(df["ETD"], errors="coerce") 
                df["weeknum"] = df["ETD"].dt.strftime("%U").astype(float).astype("Int64") + 1
                df["month"] = df["ETD"].dt.to_period("M").astype(str)
                df["quarter"] = df["ETD"].dt.to_period("Q").astype(str)
                df = df.dropna(subset=["weeknum", "month", "quarter"], how="any")
                dfs.append(df)
    status_placeholder.empty()

    df = pd.concat(dfs, ignore_index=True)
    df = df.sort_values(by=["route", time_col])

    if loss_dfs:
        loss_df = pd.concat(loss_dfs, ignore_index=True)
        df = pd.merge(df, loss_df, on="MMSCN", how="left")

    status_placeholder.empty()
    cbm = df.groupby(["route", time_col], as_index=False)[["Chrgb CBM"]].sum()

    if "Shared_Profit" in df.columns:
        profit_summary = df.groupby(["route", time_col], as_index=False)["Shared_Profit"].sum()
        profit_summary = profit_summary.sort_values(time_col)
        profit_summary["color"] = profit_summary["Shared_Profit"].apply(lambda x: "#CA001D" if x < 0 else "#498684")

    unique_counts = df.drop_duplicates(subset=["route", "Containerno", "ETD", time_col])
    weekly_unique_counts = unique_counts.groupby(["route", time_col]).size().reset_index(name="FEU")
    total_unique_pairs = weekly_unique_counts.sum()

    summary = pd.merge(cbm, weekly_unique_counts, on=["route",time_col], how="outer")
    summary["TEU"] = summary["FEU"]*2
    summary["AVG L/D"] = summary["Chrgb CBM"]/summary["FEU"]/76.3*100
    summary = summary.sort_values(["route"])

    tab1, tab2, tab3 = st.tabs(["Charts", "Profits", "Period-over-Period"])
    with tab1:
        selected_route = st.selectbox("📍 Select a Route", ["ALL"] + sorted(summary["route"].dropna().unique()), key = "tab1")
        if time_col == "month":
            teu_range = 50
            cbm_range = 1000
        elif time_col == "quarter":
            teu_range = 100
            cbm_range = 3000
        else:
            teu_range = 20
            cbm_range = 500
        if selected_route == "ALL":
            charts = []
            for route in summary["route"].dropna().unique():
                route_data = summary[summary["route"] == route]
                profit_data = profit_summary[profit_summary["route"] == route]
#-------------# TEU chart####################################################################################################################################################################
                teu_chart = alt.Chart(route_data).mark_bar(color="#498684").encode(
                    x=alt.X(f"{time_col}:O", title=""),
                    y=alt.Y("TEU:Q", title="", scale=alt.Scale(domain=[0, teu_range])),
                    tooltip=[time_col, "TEU"]
                ).properties(
                    title=alt.TitleParams(text=f"Vol(TEU) - {route}", fontSize=20, fontWeight="bold", anchor="start", offset=10),
                    width=200, height=300)
                total_teu = alt.Chart(pd.DataFrame({"x": [0], "y": [0]})).mark_text(
                    text=f"TTL {route_data['TEU'].sum():.0f} TEU",
                    color="#CA001D", fontSize=20, fontWeight="bold", align="center", dy=-30).encode(x=alt.value(0), y=alt.value(0))

#-------------# CBM chart####################################################################################################################################################################
                cbm_chart = alt.Chart(route_data).mark_bar(color="#498684").encode(
                    x=alt.X(f"{time_col}:O", title=""),
                    y=alt.Y("Chrgb CBM:Q", title="", scale=alt.Scale(domain=[0, cbm_range])),
                    tooltip=[time_col, "Chrgb CBM"]
                ).properties(
                    title=alt.TitleParams(text=f"Vol(C.CBM) - {route}", fontSize=20, fontWeight="bold", anchor="start", offset=10),
                    width=200, height=300
                )
                total_cbm = alt.Chart(pd.DataFrame({"x": [0], "y": [0]})).mark_text(
                    text=f"TTL {route_data['Chrgb CBM'].sum():.0f} CBM",
                    color="#CA001D", fontSize=20, fontWeight="bold", align="center", dy=-30
                ).encode(x=alt.value(0), y=alt.value(0))
                cbm_text = alt.Chart(route_data).mark_text(
                    color="#498684", align="center", baseline="bottom", dy=-5, fontSize=8
                ).encode(x=f"{time_col}:O", y="Chrgb CBM:Q", text=alt.Text("Chrgb CBM:Q"))

#--------------#LD chart####################################################################################################################################################################
                avg_ld = route_data["AVG L/D"].mean()
                ld_chart = alt.Chart(route_data).mark_line(color="#498684").encode(
                    x=alt.X(f"{time_col}:O", title=""),
                    y=alt.Y("AVG L/D:Q", title="", scale=alt.Scale(domain=[0, 100])),
                    tooltip=[time_col, "AVG L/D"]
                ).properties(
                    title=alt.TitleParams(text=f"LD(%) - {route}", fontSize=20, fontWeight="bold", anchor="start", offset=10),
                    width=200, height=300
                )
                ld_points = alt.Chart(route_data).mark_point(color="#498684", filled=True, size=80).encode(
                    x=f"{time_col}:O", y="AVG L/D:Q", tooltip=[time_col, "AVG L/D"]
                )
                avg_line = alt.Chart(pd.DataFrame({"y": [avg_ld]})).mark_rule(
                    color="#E4BDC2", strokeWidth=2).encode(y="y:Q")
                avg_text = alt.Chart(pd.DataFrame({"x": [0], "y": [0]})).mark_text(
                    text=f"AVG {avg_ld:.0f} %",
                    color="#CA001D", fontSize=20, fontWeight="bold", align="center", dy=-30
                ).encode(x=alt.value(0), y=alt.value(0))
                route_charts = alt.vconcat(
                    teu_chart + total_teu,
                    cbm_chart + total_cbm,
                    ld_chart + ld_points + avg_line + avg_text
                ).resolve_scale(y='independent')
                charts.append(route_charts)
            full_chart = alt.hconcat(*charts)
        else:
            data = summary[summary["route"] == selected_route]
            profit_data = profit_summary[profit_summary["route"] == selected_route]
#-----------TEU##################################################################################################################################
            teu_chart = alt.Chart(data).mark_bar(color = "#498684").encode(
                x=alt.X(f"{time_col}:O", title="", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("TEU:Q", title="", scale=alt.Scale(domain=[0, teu_range])),
                tooltip=[time_col, "TEU"]
                ).properties(
                title=alt.TitleParams(text="Vol(TEU)", fontSize=20, fontWeight="bold", anchor="start", offset=10),
                width=600,
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
                x=f"{time_col}:O",
                y="TEU:Q",
                text=alt.Text("TEU:Q"))
    #-------CBM##################################################################################################################################
            cbm_chart = alt.Chart(data).mark_bar(color = "#498684").encode(
                x=alt.X(f"{time_col}:O", title="", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("Chrgb CBM:Q", title="", scale=alt.Scale(domain=[0, cbm_range])),
                tooltip=[time_col, "Chrgb CBM"]
                ).properties(
                title=alt.TitleParams(
            text="Vol(C.CBM)",
            fontSize=20,
            fontWeight="bold",
            anchor="start",
            offset=10
        ),
                width=600,
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
                x=f"{time_col}:O",
                y="Chrgb CBM:Q",
                text=alt.Text("Chrgb CBM:Q", format=".1f"))

    #-------AVG L/D##################################################################################################################################
            avg_ld = data["AVG L/D"].mean()
            ld_chart = alt.Chart(data).mark_line(color = "#498684").encode(
                x=alt.X(f"{time_col}:O", title="", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("AVG L/D:Q", title="", scale=alt.Scale(domain=[0, 100])),
                tooltip=[time_col, "AVG L/D"]).properties(
                title=alt.TitleParams(text="LD(%)", fontSize=20,fontWeight="bold",anchor="start",offset=10),
                width=600,
                height=300)
            ld_points = alt.Chart(data).mark_point(color="#498684", filled=True, size=80).encode(
                x=f"{time_col}:O",
                y="AVG L/D:Q",
                tooltip=[time_col, "AVG L/D"])
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
        # with st.expander("📋 View raw data"):
        #     st.dataframe(route_data)
            

    route_summary = summary.copy()
    agg_summary = route_summary.groupby("route", as_index=False).agg({
        "TEU": "sum",
        "Chrgb CBM": "sum",
        "AVG L/D": "mean"
    })

    def make_profit_chart(df, title, time_col):
        base = alt.Chart(df).encode(x=alt.X(f"{time_col}:O", title="", axis=alt.Axis(labelAngle=0)))

        bars = base.mark_bar().encode(
            y=alt.Y("Shared_Profit:Q", axis=alt.Axis(title="USD", titleAngle=0, titleFontSize=14,titleAnchor="start",titleY=-5)),
            color=alt.Color("color:N", scale=None, legend=None),
            tooltip=["route", time_col, "Shared_Profit"],
        )

        pos_text = (
        base.mark_text(
            dy=-5,           
            align="center",
            baseline="bottom", 
            fontSize=12,
            color="#498684",
        )
        .encode(
            y=alt.Y("Shared_Profit:Q"),
            text=alt.Text("Shared_Profit:Q", format=".0f"),
        )
        .transform_filter(alt.datum.Shared_Profit >= 0)
    )

        neg_text = (
            base.mark_text(
                dy=5,            
                align="center",
                baseline="top",   
                fontSize=12,
                color="#CA001D",
            )
            .encode(
                y=alt.Y("Shared_Profit:Q"),
                text=alt.Text("Shared_Profit:Q", format=".0f"),
            )
            .transform_filter(alt.datum.Shared_Profit < 0)
        )

        layered = alt.layer(bars, pos_text, neg_text).properties(
            width=600,
            height=150,
            title=alt.TitleParams(
                text=title, fontSize=20, color="#498684", anchor="start", offset=10
            ),
        ).resolve_scale(y="shared") 
        return layered

    with tab2:
        profit_route = st.selectbox(
            "📍 Select a Route",
            ["ALL"] + sorted(summary["route"].dropna().unique()),
            key="tab2")
        full_chart = None
        if profit_route == "ALL":
            charts = []
            for route in sorted(summary["route"].dropna().unique()):
                profit_data = profit_summary[profit_summary["route"] == route]
                if profit_data.empty:
                    continue
                if profit_data["Shared_Profit"].dropna().abs().max() == 0:
                    continue
                charts.append(make_profit_chart(profit_data, route, time_col))
            if charts:
                full_chart = (alt.vconcat(*charts).resolve_scale(y="independent"))
            else:
                st.warning("No valid charts to display.")
        else:
            profit_data = profit_summary[profit_summary["route"] == profit_route]
            if not profit_data.empty:
                full_chart = make_profit_chart(profit_data, profit_route, time_col)
            else:
                st.info(f"This route ({profit_route}) does not have the profit data.")
        if full_chart is not None:
            st.altair_chart(full_chart, use_container_width=True)
    
    def prepare_weekly_profit(profit_summary, route, time_col):
        df = profit_summary.copy()
        if route != "ALL":
            df = df[df["route"] == route]
        if time_col == "weeknum":
            df[time_col] = pd.to_numeric(df[time_col], errors="coerce")
        df = df.dropna(subset=[time_col])
        df["Shared_Profit"] = pd.to_numeric(df["Shared_Profit"], errors="coerce").fillna(0)
        df = df.groupby(time_col, as_index=False)["Shared_Profit"].sum()
        return df.sort_values(time_col)

    def compute_wow(weekly, time_col):
        weekly = weekly.sort_values(time_col).copy()
        weekly["wow_pct"] = weekly["Shared_Profit"].pct_change() 
        return weekly 
    
    def make_wow_chart(weekly, time_col):
        time_label = {
            "weeknum": "Week-over-Week",
            "month": "Month-over-Month",
            "quarter": "Quarter-over-Quarter"
            }.get(time_col, "Period-over-Period")
        base = alt.Chart(weekly)
        bars = base.mark_bar().encode(
            x=alt.X(f"{time_col}:O", title=time_label, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("wow_pct:Q", title=f"{time_label} % Change", axis=alt.Axis(format=".0%")),
            color=alt.condition(
                alt.datum.wow_pct >= 0,
                alt.value("#2ca02c"),
                alt.value("#d62728"),
            ),
            tooltip=[
                alt.Tooltip(f"{time_col}:O", title=""),
                alt.Tooltip("Shared_Profit:Q", title="Profit", format=","),
                alt.Tooltip("wow_pct:Q", title="Change", format=".1%")
            ],
        )
        zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(strokeDash=[4,4], color="gray").encode(
            y=alt.Y("y:Q")
        )
        labels = (
            base.mark_text(dy=-5, align="center", baseline="bottom", fontSize=11)
            .encode(
                x=alt.X(f"{time_col}:O", sort=alt.EncodingSortField(field = time_col, order="ascending")),
                y=alt.Y("wow_pct:Q"),
                text=alt.Text("wow_pct:Q", format=".1%"),
            )
            .transform_filter(alt.datum.wow_pct != None)
        )
        return (bars + zero + labels).properties(
            title="",
            width=700,
            height=250,
        )

    with tab3:  
        weekly = prepare_weekly_profit(profit_summary, profit_route, time_col) 
        if weekly.empty:
            st.info("No data to show WoW.")
        else:
            wow_df = compute_wow(weekly, time_col)
            st.altair_chart(make_wow_chart(wow_df, time_col), use_container_width=True)