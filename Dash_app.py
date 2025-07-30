import streamlit as st
import pandas as pd
import datetime
import altair as alt

import matplotlib.pyplot as plt
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import tempfile
import os

st.set_page_config(layout="wide")
st.title("Monthly Report Generator")

uploaded_files = st.file_uploader("Upload Excel files", accept_multiple_files=True, type=["xlsx"])

if uploaded_files:
    status_placeholder = st.empty()
    status_placeholder.info("Data Procesing...")
    dfs = []
    for uploaded_file in uploaded_files:
        #df = pd.read_excel(uploaded_file)
        sheets = pd.read_excel(uploaded_file, sheet_name = None)
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
    cbm = df.groupby(["route", "weeknum"], as_index=False)[["Chrgb CBM"]].sum()

    unique_counts = df.drop_duplicates(subset=["route", "Containerno", "ETD", "weeknum"])
    weekly_unique_counts = unique_counts.groupby(["route","weeknum"]).size().reset_index(name="FEU")
    total_unique_pairs = weekly_unique_counts.sum()

    summary = pd.merge(cbm, weekly_unique_counts, on=["route","weeknum"], how="outer")
    summary["TEU"] = summary["FEU"]*2
    summary["AVG L/D"] = summary["Chrgb CBM"]/summary["FEU"]/76.3*100
    summary = summary.sort_values(["route", "weeknum"])

    tab1, tab2 = st.tabs(["Charts", "Pies"])
    with tab1:
        selected_route = st.selectbox("📍 Select a Route", sorted(summary["route"].dropna().unique()))
        data = summary[summary["route"] == selected_route]
        st.subheader(f"📦 Summary for Route: {selected_route}")
        # 柱状图 - TEU
        chart = alt.Chart(data).mark_bar(color = "#498684").encode(
            x=alt.X("weeknum:O", title="Week Number"),
            y=alt.Y("TEU:Q"),
            tooltip=["weeknum", "TEU"]
            ).properties(
            title="Vol(TEU)",
            width=600,
            height=300
            )
        text = alt.Chart(data).mark_text(
            color = "#498684",
            align="center",
            baseline="bottom",
            dy=-5,
            fontSize=12).encode(
            x="weeknum:O",
            y="TEU:Q",
            text=alt.Text("TEU:Q"))
        st.altair_chart(chart + text, use_container_width=True)

        # 柱状图 - CBM
        chart = alt.Chart(data).mark_bar(color = "#498684").encode(
            x=alt.X("weeknum:O", title="Week Number"),
            y=alt.Y("Chrgb CBM:Q"),
            tooltip=["weeknum", "Chrgb CBM"]
            ).properties(
            title="Vol(C.CBM)",
            width=600,
            height=300
            )
        text = alt.Chart(data).mark_text(
            color = "#498684",
            align="center",
            baseline="bottom",
            dy=-5,
            fontSize=12).encode(
            x="weeknum:O",
            y="Chrgb CBM:Q",
            text=alt.Text("Chrgb CBM:Q", format=".1f"))
        st.altair_chart(chart + text, use_container_width=True)

        # 折线图 - AVG L/D
        avg_ld = data["AVG L/D"].mean()
        chart = alt.Chart(data).mark_line(color = "#498684").encode(
            x=alt.X("weeknum:O", title="Week Number"),
            y=alt.Y("AVG L/D:Q"),
            tooltip=["weeknum", "AVG L/D"]).properties(
            title="LD(%)",
            width=600,
            height=300)
        points = alt.Chart(data).mark_point(color="#498684", filled=True, size=80).encode(
            x="weeknum:O",
            y="AVG L/D:Q",
            tooltip=["weeknum", "AVG L/D"])
        avg_line = alt.Chart(pd.DataFrame({"y": [avg_ld]})).mark_rule(
            color="#CA001D", strokeWidth=1).encode(y="y:Q")
        avg_text = alt.Chart(pd.DataFrame({"y": [avg_ld]})).mark_text(
            text=f"Average: {avg_ld:.1f}%",
            align="left", baseline="bottom", dx=5, dy=-5, color="#CA001D").encode(x=alt.value(0), y="y:Q")
        st.altair_chart(chart + points + avg_line + avg_text, use_container_width=True)
        with st.expander("📋 View raw data"):
            st.dataframe(data)

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

    def export_route_charts_to_pdf(route_data, route_name):
        fig, axes = plt.subplots(1, 3, figsize=(15, 4))

        # TEU Bar
        axes[0].bar(route_data['weeknum'], route_data['TEU'], color="#498684")
        axes[0].set_title("TEU")
        axes[0].set_xlabel("Week")
        axes[0].set_ylabel("TEU")

        # CBM Bar
        axes[1].bar(route_data['weeknum'], route_data['Chrgb CBM'], color="#2aa198")
        axes[1].set_title("CBM")
        axes[1].set_xlabel("Week")
        axes[1].set_ylabel("CBM")

        # Load Rate Line
        axes[2].plot(route_data['weeknum'], route_data['AVG L/D'], marker='o', color="#ca001d")
        axes[2].axhline(y=100, color="gray", linestyle="--", linewidth=1)
        axes[2].set_title("Load Rate (%)")
        axes[2].set_xlabel("Week")
        axes[2].set_ylabel("Load %")

        fig.suptitle(f"{route_name} Weekly Report", fontsize=14)
        fig.tight_layout()

        # 保存为临时 PNG
        tmp_image = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        plt.savefig(tmp_image.name, bbox_inches="tight")
        plt.close(fig)

        # 生成 PDF 并插入图片
        tmp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        c = canvas.Canvas(tmp_pdf.name, pagesize=letter)
        c.drawImage(tmp_image.name, 30, 300, width=530, preserveAspectRatio=True)
        c.save()

        os.remove(tmp_image.name)
        return tmp_pdf.name

    # pdf_path = export_route_charts_to_pdf(data, selected_route)
    # with open(pdf_path, "rb") as f: 
    #     st.download_button(
    #         label="📄 Download PDF Report",
    #         data=f,
    #         file_name=f"{selected_route}_report.pdf",
    #         mime="application/pdf"
    #     )
