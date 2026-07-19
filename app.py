from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="NovaRetail Customer Intelligence",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_FILE = Path(__file__).with_name("NR_dataset.xlsx")
SEGMENT_ORDER = ["Growth", "Promising", "Stable", "Decline"]
SEGMENT_COLORS = {
    "Growth": "#16A34A",
    "Promising": "#2563EB",
    "Stable": "#64748B",
    "Decline": "#DC2626",
}


def product_group(value: object) -> str:
    """Consolidate detailed product labels into decision-friendly groups."""
    text = str(value).strip().lower()
    rules: list[tuple[Iterable[str], str]] = [
        (("electronic", "gaming"), "Electronics & Gaming"),
        (("cloth", "fashion", "apparel", "sportswear"), "Clothing & Fashion"),
        (("grocery", "groceries", "food", "beverage"), "Grocery & Food"),
        (("home", "furniture", "decor", "garden", "improvement"), "Home & Garden"),
        (("book", "magazine", "office"), "Books & Office"),
        (("health", "beauty", "cosmetic", "personal care"), "Health & Beauty"),
        (("sport", "outdoor", "automotive"), "Sports & Outdoors"),
        (("toy", "children"), "Toys & Children"),
    ]
    for keywords, group in rules:
        if any(keyword in text for keyword in keywords):
            return group
    return "Other"


@st.cache_data(show_spinner=False)
def load_data(path: Path) -> tuple[pd.DataFrame, dict[str, int]]:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path.name}")

    df = pd.read_excel(path, engine="openpyxl")
    required = {
        "label", "CustomerID", "TransactionID", "TransactionDate",
        "ProductCategory", "PurchaseAmount", "CustomerAgeGroup",
        "CustomerGender", "CustomerRegion", "CustomerSatisfaction",
        "RetailChannel",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    quality = {
        "source_rows": len(df),
        "missing_segment_rows": int(df["label"].isna().sum()),
        "duplicate_rows": int(df.duplicated().sum()),
    }

    df = df.copy()
    df["TransactionDate"] = pd.to_datetime(df["TransactionDate"], errors="coerce")
    df["PurchaseAmount"] = pd.to_numeric(df["PurchaseAmount"], errors="coerce")
    df["CustomerSatisfaction"] = pd.to_numeric(df["CustomerSatisfaction"], errors="coerce")
    df["label"] = df["label"].astype("string").str.strip()
    df["ProductGroup"] = df["ProductCategory"].map(product_group)
    df["CustomerID"] = df["CustomerID"].astype("Int64").astype("string")

    # Segment-based analysis requires a valid segment and revenue amount.
    df = df[df["label"].isin(SEGMENT_ORDER) & df["PurchaseAmount"].notna()].copy()
    df["Month"] = df["TransactionDate"].dt.to_period("M").astype(str)
    return df, quality


def multiselect_filter(df: pd.DataFrame, column: str, selected: list[str]) -> pd.DataFrame:
    return df[df[column].isin(selected)] if selected else df.iloc[0:0]


def currency(value: float) -> str:
    return f"${value:,.0f}"


st.markdown(
    """
    <style>
      .block-container {padding-top: 1.3rem; padding-bottom: 2rem;}
      [data-testid="stMetric"] {background:#FFFFFF; border:1px solid #E2E8F0;
        border-radius:14px; padding:14px 16px; box-shadow:0 2px 8px rgba(15,23,42,.05);}
      [data-testid="stSidebar"] {background:#F8FAFC;}
      .hero {padding:1.1rem 1.25rem; border-radius:16px;
        background:linear-gradient(120deg,#0F172A,#1D4ED8); color:white; margin-bottom:1rem;}
      .hero h1 {margin:0; font-size:2rem;} .hero p {margin:.35rem 0 0; opacity:.9;}
      .insight {border-left:5px solid #2563EB; background:#EFF6FF; padding:.9rem 1rem;
        border-radius:8px; margin:.45rem 0;}
      .risk {border-left-color:#DC2626; background:#FEF2F2;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """<div class="hero"><h1>NovaRetail Customer Intelligence</h1>
    <p>Interactive revenue, growth, and retention dashboard for customer-level decision making</p></div>""",
    unsafe_allow_html=True,
)

try:
    data, data_quality = load_data(DATA_FILE)
except (FileNotFoundError, ValueError) as exc:
    st.error(str(exc))
    st.stop()
except Exception as exc:  # keep deployment failures understandable
    st.error(f"Unable to load the dataset: {exc}")
    st.stop()

with st.sidebar:
    st.header("Dashboard Filters")
    segments = st.multiselect("Customer segment", SEGMENT_ORDER, default=SEGMENT_ORDER)
    regions_all = sorted(data["CustomerRegion"].dropna().unique().tolist())
    regions = st.multiselect("Region", regions_all, default=regions_all)
    groups_all = sorted(data["ProductGroup"].dropna().unique().tolist())
    groups = st.multiselect("Product group", groups_all, default=groups_all)
    channels_all = sorted(data["RetailChannel"].dropna().unique().tolist())
    channels = st.multiselect("Retail channel", channels_all, default=channels_all)
    ages_all = sorted(data["CustomerAgeGroup"].dropna().unique().tolist())
    ages = st.multiselect("Age group", ages_all, default=ages_all)
    st.divider()
    st.caption("Filters apply to all KPIs, charts, insights, and the customer table.")
    with st.expander("Data quality"):
        st.write(f"Source rows: **{data_quality['source_rows']}**")
        st.write(f"Missing segment rows excluded: **{data_quality['missing_segment_rows']}**")
        st.write(f"Exact duplicate rows: **{data_quality['duplicate_rows']}**")

filtered = data.copy()
for col, selected in [
    ("label", segments), ("CustomerRegion", regions), ("ProductGroup", groups),
    ("RetailChannel", channels), ("CustomerAgeGroup", ages),
]:
    filtered = multiselect_filter(filtered, col, selected)

if filtered.empty:
    st.warning("No records match the selected filters. Expand one or more filter selections.")
    st.stop()

revenue = float(filtered["PurchaseAmount"].sum())
customers = int(filtered["CustomerID"].nunique())
transactions = int(filtered["TransactionID"].nunique())
avg_customer = revenue / customers if customers else 0
avg_satisfaction = float(filtered["CustomerSatisfaction"].mean())
decline_revenue = float(filtered.loc[filtered["label"] == "Decline", "PurchaseAmount"].sum())
decline_share = decline_revenue / revenue if revenue else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Revenue", currency(revenue))
k2.metric("Customers", f"{customers:,}")
k3.metric("Revenue / Customer", currency(avg_customer))
k4.metric("Avg. Satisfaction", f"{avg_satisfaction:.2f} / 5")
k5.metric("Decline Revenue Share", f"{decline_share:.1%}")

overview, risk_tab, customer_tab, insights_tab = st.tabs(
    ["Executive Overview", "Segment & Risk", "Customer Explorer", "Recommended Actions"]
)

with overview:
    c1, c2 = st.columns([1.15, 1])
    segment_summary = (
        filtered.groupby("label", observed=True)
        .agg(Revenue=("PurchaseAmount", "sum"), Customers=("CustomerID", "nunique"),
             Satisfaction=("CustomerSatisfaction", "mean"))
        .reset_index()
    )
    segment_summary["label"] = pd.Categorical(segment_summary["label"], SEGMENT_ORDER, ordered=True)
    segment_summary = segment_summary.sort_values("label")

    fig_segment = px.bar(
        segment_summary, x="label", y="Revenue", color="label",
        color_discrete_map=SEGMENT_COLORS, text_auto="$.3s",
        title="Revenue by Customer Segment",
        labels={"label": "Segment", "Revenue": "Revenue ($)"},
    )
    fig_segment.update_layout(showlegend=False, height=390, margin=dict(t=55, b=25))
    c1.plotly_chart(fig_segment, use_container_width=True)

    product_summary = (
        filtered.groupby("ProductGroup", observed=True)["PurchaseAmount"].sum()
        .sort_values(ascending=True).reset_index()
    )
    fig_product = px.bar(
        product_summary, x="PurchaseAmount", y="ProductGroup", orientation="h",
        title="Revenue by Product Group",
        labels={"PurchaseAmount": "Revenue ($)", "ProductGroup": ""},
        text_auto="$.3s",
    )
    fig_product.update_layout(height=390, margin=dict(t=55, b=25))
    c2.plotly_chart(fig_product, use_container_width=True)

    c3, c4 = st.columns(2)
    region_channel = (
        filtered.groupby(["CustomerRegion", "RetailChannel"], observed=True)["PurchaseAmount"]
        .sum().reset_index()
    )
    fig_region = px.bar(
        region_channel, x="CustomerRegion", y="PurchaseAmount", color="RetailChannel",
        barmode="group", title="Regional Revenue by Sales Channel",
        labels={"PurchaseAmount": "Revenue ($)", "CustomerRegion": "Region"},
    )
    fig_region.update_layout(height=380, margin=dict(t=55, b=25))
    c3.plotly_chart(fig_region, use_container_width=True)

    age_summary = filtered.groupby("CustomerAgeGroup", observed=True).agg(
        Revenue=("PurchaseAmount", "sum"), Satisfaction=("CustomerSatisfaction", "mean")
    ).reset_index()
    fig_age = px.scatter(
        age_summary, x="Revenue", y="Satisfaction", size="Revenue", text="CustomerAgeGroup",
        title="Age Group Opportunity Map", labels={"Revenue": "Revenue ($)", "Satisfaction": "Avg. Satisfaction"},
    )
    fig_age.update_traces(textposition="top center")
    fig_age.update_layout(height=380, margin=dict(t=55, b=25))
    c4.plotly_chart(fig_age, use_container_width=True)

with risk_tab:
    left, right = st.columns([1.05, 1])
    matrix = (
        filtered.groupby("label", observed=True)
        .agg(Revenue=("PurchaseAmount", "sum"), Customers=("CustomerID", "nunique"),
             Satisfaction=("CustomerSatisfaction", "mean"), Transactions=("TransactionID", "nunique"))
        .reset_index()
    )
    matrix["RevenuePerCustomer"] = matrix["Revenue"] / matrix["Customers"].replace(0, pd.NA)
    fig_matrix = px.scatter(
        matrix, x="RevenuePerCustomer", y="Satisfaction", size="Revenue", color="label",
        color_discrete_map=SEGMENT_COLORS, text="label", title="Segment Value vs. Customer Experience",
        labels={"RevenuePerCustomer": "Revenue per Customer ($)", "Satisfaction": "Avg. Satisfaction", "label": "Segment"},
    )
    fig_matrix.add_hline(y=3, line_dash="dash", annotation_text="Satisfaction warning line")
    fig_matrix.update_traces(textposition="top center")
    fig_matrix.update_layout(height=440, margin=dict(t=60, b=25))
    left.plotly_chart(fig_matrix, use_container_width=True)

    risk_breakdown = (
        filtered[filtered["label"] == "Decline"]
        .groupby(["CustomerRegion", "ProductGroup"], observed=True)["PurchaseAmount"]
        .sum().reset_index().sort_values("PurchaseAmount", ascending=False)
    )
    if risk_breakdown.empty:
        right.info("The selected filters contain no Decline-segment records.")
    else:
        fig_risk = px.treemap(
            risk_breakdown, path=["CustomerRegion", "ProductGroup"], values="PurchaseAmount",
            title="Where Decline-Segment Revenue Is Concentrated",
            color="PurchaseAmount", color_continuous_scale="Reds",
        )
        fig_risk.update_layout(height=440, margin=dict(t=60, b=20))
        right.plotly_chart(fig_risk, use_container_width=True)

    st.subheader("Segment Scorecard")
    scorecard = matrix.copy()
    scorecard["Revenue"] = scorecard["Revenue"].map(lambda x: f"${x:,.2f}")
    scorecard["RevenuePerCustomer"] = scorecard["RevenuePerCustomer"].map(lambda x: f"${x:,.2f}")
    scorecard["Satisfaction"] = scorecard["Satisfaction"].map(lambda x: f"{x:.2f}")
    st.dataframe(
        scorecard.rename(columns={"label": "Segment", "RevenuePerCustomer": "Revenue / Customer"}),
        use_container_width=True, hide_index=True,
    )

with customer_tab:
    customer_summary = (
        filtered.groupby("CustomerID", observed=True)
        .agg(
            Segment=("label", lambda x: x.mode().iat[0] if not x.mode().empty else x.iloc[0]),
            Revenue=("PurchaseAmount", "sum"),
            Transactions=("TransactionID", "nunique"),
            AvgSatisfaction=("CustomerSatisfaction", "mean"),
            Region=("CustomerRegion", lambda x: x.mode().iat[0] if not x.mode().empty else x.iloc[0]),
            PreferredChannel=("RetailChannel", lambda x: x.mode().iat[0] if not x.mode().empty else x.iloc[0]),
            TopProductGroup=("ProductGroup", lambda x: x.mode().iat[0] if not x.mode().empty else x.iloc[0]),
        ).reset_index()
    )
    customer_summary["Priority"] = customer_summary.apply(
        lambda r: "Retention" if r["Segment"] == "Decline" else
                  "Accelerate" if r["Segment"] in ["Growth", "Promising"] and r["Revenue"] >= customer_summary["Revenue"].median()
                  else "Maintain", axis=1,
    )
    customer_summary = customer_summary.sort_values("Revenue", ascending=False)

    top_n = st.slider("Number of customers to display", 5, min(30, len(customer_summary)), min(15, len(customer_summary)))
    display = customer_summary.head(top_n).copy()
    display["Revenue"] = display["Revenue"].map(lambda x: f"${x:,.2f}")
    display["AvgSatisfaction"] = display["AvgSatisfaction"].map(lambda x: f"{x:.2f}")
    st.dataframe(display, use_container_width=True, hide_index=True)

    csv = customer_summary.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download filtered customer summary",
        data=csv,
        file_name="novaretail_customer_summary.csv",
        mime="text/csv",
    )

with insights_tab:
    seg_rev = filtered.groupby("label", observed=True)["PurchaseAmount"].sum().sort_values(ascending=False)
    top_segment = seg_rev.index[0]
    top_segment_revenue = float(seg_rev.iloc[0])
    top_product = filtered.groupby("ProductGroup", observed=True)["PurchaseAmount"].sum().idxmax()
    top_region = filtered.groupby("CustomerRegion", observed=True)["PurchaseAmount"].sum().idxmax()
    top_channel = filtered.groupby("RetailChannel", observed=True)["PurchaseAmount"].sum().idxmax()

    st.markdown(
        f"<div class='insight'><b>Growth focus:</b> {top_segment} is the largest selected segment at "
        f"<b>{currency(top_segment_revenue)}</b>. Prioritize cross-sell and loyalty offers for high-value "
        f"Growth and Promising customers, especially in <b>{top_product}</b>.</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div class='insight'><b>Investment focus:</b> <b>{top_region}</b> and the <b>{top_channel}</b> channel "
        f"currently generate the strongest revenue under the selected filters. Test targeted campaigns there first, "
        f"then compare lift with a holdout region or channel.</div>",
        unsafe_allow_html=True,
    )
    if decline_revenue > 0:
        decline_sat = filtered.loc[filtered["label"] == "Decline", "CustomerSatisfaction"].mean()
        st.markdown(
            f"<div class='insight risk'><b>Early warning:</b> Decline customers represent "
            f"<b>{currency(decline_revenue)}</b> ({decline_share:.1%} of selected revenue) with average satisfaction "
            f"of <b>{decline_sat:.2f}/5</b>. Launch service-recovery outreach and examine the region-product "
            f"concentrations shown in the risk tab.</div>",
            unsafe_allow_html=True,
        )
    else:
        st.success("No Decline-segment revenue is present under the current filters.")

    st.subheader("Suggested Commercial Actions")
    st.markdown(
        """
        1. **Accelerate Growth and Promising customers:** personalize bundles, loyalty rewards, and next-best-product offers.
        2. **Protect Decline customers:** trigger outreach for low satisfaction, offer service recovery, and monitor repeat purchases.
        3. **Develop Stable customers:** use low-cost replenishment reminders and category-adjacent recommendations.
        4. **Measure results:** track campaign conversion, repeat-purchase rate, revenue per customer, and movement between segments.
        """
    )

st.caption(
    f"Filtered view: {len(filtered):,} records | {transactions:,} unique transaction IDs | "
    f"Data source: {DATA_FILE.name}"
)
