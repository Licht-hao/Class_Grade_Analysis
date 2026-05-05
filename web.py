import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import plotly.colors as pcolors

st.set_page_config(page_title="考试成绩分析", layout="wide")
st.title("📊 考试成绩分析工具 (by Licht)")

# ---------- 文件上传与 Sheet 选择 ----------
uploaded_file = st.file_uploader("上传 Excel 文件", type=["xlsx", "xls"])

# ---------- 示例表格格式 ----------
with st.expander("📋 查看示例数据格式"):
    example_data = pd.DataFrame({
        "学校": ["学校A", "学校A", "学校A", "学校B", "学校B"],
        "班级": ["1班", "2班", "1班", "1班", "5班"],
        "姓名": ["学生1", "学生2", "学生3", "学生4", "学生5"],
        "总分": [386, 385, 383, 376, 379],
        "学科A": [121, 115, 118, 117, 116],
        "学科B": [145, 142, 127, 133, 136],
        "学科C": [120, 128, 138, 126, 127]
    })
    st.dataframe(example_data, use_container_width=True)
    st.caption("上传的 Excel 文件需包含「班级」列以及各学科成绩列；「学校」列可选，若无则仅按班级分析。")

if uploaded_file is not None:
    try:
        xls = pd.ExcelFile(uploaded_file)
        sheet_names = xls.sheet_names
    except Exception as e:
        st.error(f"读取 Excel 文件失败：{e}")
        st.stop()

    if not sheet_names:
        st.error("文件中没有可用的 Sheet。")
        st.stop()

    sheet = st.selectbox("选择要分析的 Sheet", sheet_names)

    try:
        df = pd.read_excel(uploaded_file, sheet_name=sheet, dtype=str)
    except Exception as e:
        st.error(f"读取 Sheet 失败：{e}")
        st.stop()

    if df.empty:
        st.error("所选 Sheet 为空。")
        st.stop()

    df = df.loc[:, ~df.columns.duplicated()]

    # 检查必须包含“班级”列
    if "班级" not in df.columns:
        st.error("文件必须包含「班级」列。")
        st.stop()

    # 判断是否有“学校”列
    has_school = "学校" in df.columns

    # ---------- 选择学校（如有）与班级 ----------
    if has_school:
        schools = sorted(df["学校"].dropna().unique())
        selected_school = st.selectbox("选择学校", schools)
        school_df = df[df["学校"] == selected_school]
        classes = sorted(school_df["班级"].dropna().unique())
        if not classes:
            st.error(f"学校「{selected_school}」下未找到班级数据。")
            st.stop()
        selected_class = st.selectbox("选择班级", classes)
    else:
        # 无学校列：直接从所有班级中选择
        selected_school = None
        classes = sorted(df["班级"].dropna().unique())
        if not classes:
            st.error("未找到任何班级数据。")
            st.stop()
        selected_class = st.selectbox("选择班级", classes)
        school_df = df.copy()  # 用于一致性

    # ---------- 选择学科（成绩列） ----------
    exclude_keywords = ["准考证号", "姓名", "学校", "班级", "名次", "校次", "联考"]
    candidate_cols = [col for col in df.columns if not any(k in str(col) for k in exclude_keywords)]
    if not candidate_cols:
        candidate_cols = list(df.columns)

    selected_subjects = st.multiselect(
        "选择需要分析的学科（成绩列）",
        options=candidate_cols,
        default=candidate_cols,
    )
    if not selected_subjects:
        st.warning("请至少选择一列成绩进行分析。")
        st.stop()

    # ---------- 分析范围（仅在有学校时显示选项） ----------
    if has_school:
        scope = st.radio(
            "分析范围",
            ("所有学校", "仅本校"),
            help="「所有学校」将整个数据集分组为“学校+班级”；「仅本校」分组为“班级”",
        )
    else:
        scope = "仅本校"  # 相当于只能按班级

    # 准备分析数据并定义分组
    if scope == "所有学校" and has_school:
        analysis_df = df.copy()
        analysis_df["分组"] = analysis_df["学校"] + " " + analysis_df["班级"].astype(str)
        target_group = f"{selected_school} {selected_class}"
    else:
        analysis_df = school_df.copy() if has_school else df.copy()
        analysis_df["分组"] = analysis_df["班级"].astype(str)
        target_group = selected_class

    # 成绩列转数值
    for col in selected_subjects:
        analysis_df[col] = pd.to_numeric(analysis_df[col], errors="coerce")

    analysis_df = analysis_df.dropna(subset=selected_subjects + ["分组"])
    if analysis_df.empty:
        st.error("处理后无有效数据，请检查成绩列。")
        st.stop()

    # ---------- 统计分析（表格输出） ----------
    st.header("📋 班级对比统计表")

    for subject in selected_subjects:
        st.subheader(f"学科：{subject}")
        stats = (
            analysis_df.groupby("分组")[subject]
            .agg(
                均值="mean",
                中位数="median",
                Q1=lambda x: x.quantile(0.25),
                Q3=lambda x: x.quantile(0.75),
                标准差="std",
            )
            .reset_index()
        )
        stats["均值排名"] = stats["均值"].rank(ascending=False, method="min").astype(int)

        # 目标班级排在最前
        stats["is_target"] = stats["分组"] == target_group
        stats = stats.sort_values(["is_target", "均值排名"], ascending=[False, True]).drop(
            columns="is_target"
        )

        def highlight_target(row):
            if row["分组"] == target_group:
                return ["background: #d4edda; font-weight: bold"] * len(row)
            return [""] * len(row)

        styled_stats = stats.style.format(
            {"均值": "{:.2f}", "中位数": "{:.2f}", "Q1": "{:.2f}", "Q3": "{:.2f}", "标准差": "{:.2f}"}
        ).apply(highlight_target, axis=1)

        st.dataframe(styled_stats, use_container_width=True)

        csv = stats.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            f"下载 {subject} 统计表",
            data=csv,
            file_name=f"{subject}_统计表.csv",
            mime="text/csv",
        )

    # ---------- 可视化 ----------
    st.header("📈 点图与拟合曲线（x = 班级内相对百分位）")

    tabs = st.tabs(selected_subjects)

    all_groups = sorted(analysis_df["分组"].unique())
    default_colors = pcolors.qualitative.Plotly
    color_map = {
        group: default_colors[i % len(default_colors)]
        for i, group in enumerate(all_groups)
    }

    for i, subject in enumerate(selected_subjects):
        with tabs[i]:
            temp_df = analysis_df[["分组", subject]].copy()
            temp_df["百分位"] = temp_df.groupby("分组")[subject].rank(pct=True) * 100
            temp_df = temp_df.dropna()

            fig = px.scatter(
                temp_df,
                x="百分位",
                y=subject,
                color="分组",
                color_discrete_map=color_map,
                opacity=0.7,
                labels={"百分位": "班级内相对百分位 (%)", subject: "成绩"},
                title=f"{subject} - 各班级内部百分位分布",
            )

            # 各分组趋势线
            for group in all_groups:
                group_data = temp_df[temp_df["分组"] == group].sort_values("百分位")
                if len(group_data) >= 3:
                    x = group_data["百分位"].values
                    y = group_data[subject].values
                    deg = min(3, len(x) - 1)
                    coeffs = np.polyfit(x, y, deg)
                    x_line = np.linspace(x.min(), x.max(), 100)
                    y_line = np.polyval(coeffs, x_line)
                    fig.add_trace(go.Scatter(
                        x=x_line, y=y_line, mode="lines",
                        line=dict(color=color_map[group], width=1.5),
                        showlegend=False
                    ))

            # 整体趋势线
            if len(temp_df) >= 4:
                x_vals = temp_df["百分位"].values
                y_vals = temp_df[subject].values
                sort_idx = np.argsort(x_vals)
                x_sorted = x_vals[sort_idx]
                y_sorted = y_vals[sort_idx]
                coeffs = np.polyfit(x_sorted, y_sorted, deg=min(3, len(x_sorted)-1))
                x_line = np.linspace(x_sorted.min(), x_sorted.max(), 200)
                y_line = np.polyval(coeffs, x_line)
                fig.add_trace(go.Scatter(
                    x=x_line, y=y_line, mode="lines",
                    line=dict(color="black", width=2, dash="dash"),
                    name="整体趋势线"
                ))

            fig.update_layout(
                xaxis=dict(range=[0, 100], dtick=20),
                height=800,
                legend_title="分组",
            )
            st.plotly_chart(fig, use_container_width=True)

else:
    st.info("👆 请上传一个 Excel 文件开始分析。")
