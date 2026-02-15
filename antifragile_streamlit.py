"""
Antifragile Boardroom - Standalone Streamlit Application

Run with: streamlit run antifragile_streamlit.py

Provides the full Antifragile Board of Advisors as an interactive
web application with Council Protocol deliberation, specialist agent
scans, and analytical tools.
"""

import os
import sys
import json
import streamlit as st
from datetime import datetime

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from antifragile.council import CouncilProtocol, quick_deliberate, ADVISORS
from antifragile.tools import (
    FragilityScorer,
    GeometricSimulator,
    PatternDetector,
    FactorAnalyzer,
    AmbiguityScorer,
)
from antifragile.agents import (
    TalebFragilityAgent,
    SpitznagelSafeHavenAgent,
    SimonsPatternAgent,
    AssnessFactorAgent,
)

# ---------------------------------------------------------------------------
# Page Config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Antifragile Board of Advisors",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session State
# ---------------------------------------------------------------------------

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "scan_results" not in st.session_state:
    st.session_state.scan_results = None
if "last_deliberation" not in st.session_state:
    st.session_state.last_deliberation = None

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🛡️ Antifragile Board")
    st.caption("Multi-Agent Risk Management & Alpha Extraction")

    st.divider()

    st.subheader("Board Advisors")
    st.markdown("""
    - **Nassim Taleb** - Risk Epistemology
    - **Mark Spitznagel** - Safe Haven Practice
    - **Jim Simons** - Quantitative Patterns
    - **Cliff Asness** - Factor Discipline
    """)

    st.divider()

    st.subheader("Council Protocol")
    st.markdown("""
    1. **Divergence** - Parallel independent analysis
    2. **Convergence** - Anonymous peer review
    3. **Synthesis** - Chairman aggregation
    """)

    st.divider()

    selected_advisors = st.multiselect(
        "Select Advisors",
        options=list(ADVISORS.keys()),
        default=list(ADVISORS.keys()),
        format_func=lambda x: ADVISORS[x]["name"],
    )

    peer_review = st.checkbox("Enable Peer Review", value=False,
                              help="Adds adversarial critique phase (slower but more thorough)")

# ---------------------------------------------------------------------------
# Main Content
# ---------------------------------------------------------------------------

st.title("🛡️ The Antifragile Boardroom")

tab_deliberate, tab_scan, tab_tools = st.tabs([
    "📋 Council Deliberation",
    "🔍 Agent Scan",
    "🛠️ Analytical Tools",
])

# ---------------------------------------------------------------------------
# Tab 1: Council Deliberation
# ---------------------------------------------------------------------------

with tab_deliberate:
    st.subheader("Submit a thesis for Board critique")

    # Example buttons
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("Crypto Allocation", use_container_width=True):
            st.session_state.example_query = (
                "We are considering allocating 15% of our endowment portfolio to Bitcoin "
                "and Ethereum. The thesis is that crypto represents a new asset class with "
                "low correlation to traditional markets."
            )
    with col2:
        if st.button("SAP Migration Risk", use_container_width=True):
            st.session_state.example_query = (
                "Our $2B manufacturing company is planning an SAP S/4HANA migration over "
                "24 months with a $150M budget. We plan a 'big bang' go-live rather than phased."
            )
    with col3:
        if st.button("AI Startup Thesis", use_container_width=True):
            st.session_state.example_query = (
                "We are evaluating an AI startup (Series B, $200M valuation) that uses LLMs "
                "to automate legal contract review. $5M ARR growing 300% YoY, 12 months runway."
            )
    with col4:
        if st.button("60/40 Portfolio", use_container_width=True):
            st.session_state.example_query = (
                "Our family office manages $500M in a traditional 60/40 portfolio. Our advisor "
                "says this provides 'adequate diversification'. No alternatives, no tail hedging."
            )

    default_query = st.session_state.get("example_query", "")
    query = st.text_area(
        "Investment thesis, business model, or strategic question:",
        value=default_query,
        height=120,
        placeholder="Enter your thesis here...",
    )

    if st.button("🏛️ Convene the Board", type="primary", use_container_width=True):
        if not query.strip():
            st.error("Please enter a query.")
        elif not selected_advisors:
            st.error("Select at least one advisor.")
        else:
            # Progress indicators
            progress_bar = st.progress(0, text="Phase 1: Divergence - Gathering independent opinions...")

            with st.spinner("Board is deliberating..."):
                progress_bar.progress(20, text="Phase 1: Divergence - Advisors analyzing independently...")

                result = quick_deliberate(
                    query=query,
                    advisors=selected_advisors,
                    peer_review=peer_review,
                )

                progress_bar.progress(100, text="Phase 3: Synthesis - Complete!")
                st.session_state.last_deliberation = result

                # Store in chat history
                st.session_state.chat_history.append({
                    "role": "user",
                    "content": query,
                })
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": result.get("final_recommendation", "No synthesis available."),
                })

    # Display results
    if st.session_state.last_deliberation:
        result = st.session_state.last_deliberation

        st.divider()

        # Synthesis
        st.subheader("📜 Chairman's Synthesis")
        synthesis = result.get("final_recommendation", result.get("phases", {}).get("synthesis", ""))
        st.markdown(synthesis)

        # Individual opinions
        st.divider()
        st.subheader("🗣️ Individual Advisor Opinions")

        opinions = result.get("phases", {}).get("divergence", {})
        for advisor_id, opinion in opinions.items():
            badge_colors = {
                "taleb": "🔴",
                "spitznagel": "🟠",
                "simons": "🔵",
                "asness": "🟢",
            }
            icon = badge_colors.get(advisor_id, "⚪")

            with st.expander(f"{icon} {opinion['advisor']} - {opinion['title']}", expanded=False):
                st.caption(f"Focus: {opinion['focus']}")
                st.markdown(opinion["analysis"])

        # Critiques
        critiques = result.get("phases", {}).get("convergence", {})
        if critiques:
            st.divider()
            st.subheader("⚔️ Peer Review Critiques")
            for reviewer_id, critique in critiques.items():
                with st.expander(f"Critique by {critique['reviewer']}", expanded=False):
                    st.markdown(critique["critique"])

        # Meta
        st.caption(
            f"Elapsed: {result.get('elapsed_seconds', '?')}s | "
            f"Advisors: {', '.join(result.get('advisors_consulted', []))}"
        )

# ---------------------------------------------------------------------------
# Tab 2: Agent Scan
# ---------------------------------------------------------------------------

with tab_scan:
    st.subheader("Run Specialist Agent Scans")
    st.caption("Data-driven market analysis from each advisor's cognitive framework")

    scan_agents = st.multiselect(
        "Select agents to run",
        options=["taleb", "spitznagel", "simons", "asness"],
        default=["taleb", "spitznagel", "simons", "asness"],
        format_func=lambda x: ADVISORS[x]["name"] if x in ADVISORS else x,
    )

    if st.button("🔍 Run Agent Scan", type="primary"):
        agent_map = {
            "taleb": TalebFragilityAgent,
            "spitznagel": SpitznagelSafeHavenAgent,
            "simons": SimonsPatternAgent,
            "asness": AssnessFactorAgent,
        }

        all_findings = {}
        progress = st.progress(0)

        for i, agent_id in enumerate(scan_agents):
            if agent_id not in agent_map:
                continue
            progress.progress(
                (i / len(scan_agents)),
                text=f"Running {ADVISORS.get(agent_id, {}).get('name', agent_id)}..."
            )
            try:
                agent = agent_map[agent_id]()
                findings = agent.analyze()
                all_findings[agent_id] = findings
            except Exception as e:
                all_findings[agent_id] = [{"error": str(e)}]

        progress.progress(1.0, text="Scan complete!")
        st.session_state.scan_results = all_findings

    # Display scan results
    if st.session_state.scan_results:
        results = st.session_state.scan_results
        total = sum(len(f) for f in results.values())
        st.metric("Total Findings", total)

        severity_colors = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢",
        }

        for agent_id, findings in results.items():
            name = ADVISORS.get(agent_id, {}).get("name", agent_id)
            st.subheader(f"{name} ({len(findings)} findings)")

            for f in findings:
                if isinstance(f, dict) and "error" in f:
                    st.error(f["error"])
                    continue

                sev = f.get("severity", "low")
                icon = severity_colors.get(sev, "⚪")
                title = f.get("title", "Finding")
                desc = f.get("description", "")
                symbol = f.get("symbol", "")

                with st.expander(f"{icon} [{sev.upper()}] {title}" + (f" ({symbol})" if symbol else "")):
                    st.markdown(desc)
                    if f.get("metadata"):
                        st.json(f["metadata"])

# ---------------------------------------------------------------------------
# Tab 3: Analytical Tools
# ---------------------------------------------------------------------------

with tab_tools:
    tool_col1, tool_col2 = st.columns(2)

    # Fragility Scorer
    with tool_col1:
        st.subheader("🔴 Fragility Scorer")
        with st.form("fragility_form"):
            fc1, fc2 = st.columns(2)
            with fc1:
                leverage = st.number_input("Leverage Ratio", value=1.0, step=0.1, min_value=0.0)
                concentration = st.slider("Concentration %", 0.0, 1.0, 0.2, 0.05)
                years = st.number_input("Years Operating", value=5, min_value=0)
            with fc2:
                revenue_sources = st.number_input("Revenue Sources", value=3, min_value=1)
                debt_equity = st.number_input("Debt/Equity", value=0.5, step=0.1, min_value=0.0)
                tail = st.selectbox("Tail Exposure", ["neutral", "long_tail", "short_tail"])

            skin = st.checkbox("Has Skin in the Game", value=True)
            forecast = st.checkbox("Relies on Forecasting", value=False)

            if st.form_submit_button("Score Fragility", use_container_width=True):
                result = FragilityScorer.score_fragility(
                    leverage_ratio=leverage,
                    concentration_pct=concentration,
                    years_of_operation=years,
                    has_skin_in_game=skin,
                    relies_on_forecasting=forecast,
                    revenue_sources=revenue_sources,
                    debt_to_equity=debt_equity,
                    tail_exposure=tail,
                )
                score = result["fragility_score"]
                color = "🔴" if score > 50 else "🟡" if score > 30 else "🟢"
                st.metric(f"{color} {result['classification']}", f"{score}/100")
                for rec in result.get("recommendations", []):
                    st.warning(rec)

    # Bernoulli Falls
    with tool_col2:
        st.subheader("🟠 Bernoulli Falls Calculator")
        dd_pct = st.slider("Drawdown %", 1, 99, 50)
        if st.button("Calculate Recovery", use_container_width=True):
            result = GeometricSimulator.bernoulli_falls(dd_pct / 100)
            if "error" not in result:
                c1, c2, c3 = st.columns(3)
                c1.metric("Loss", f"{dd_pct}%")
                c2.metric("Recovery Needed", f"{result['recovery_needed_pct']*100:.1f}%")
                c3.metric("Years @10%", f"{result['years_to_recover_at_10pct']}")

    st.divider()

    tool_col3, tool_col4 = st.columns(2)

    # Safe Haven Simulator
    with tool_col3:
        st.subheader("🟠 Safe Haven Frontier Simulator")
        with st.form("haven_form"):
            hc1, hc2 = st.columns(2)
            with hc1:
                port_return = st.number_input("Portfolio Return %", value=8.0, step=1.0)
                haven_alloc = st.number_input("Haven Allocation %", value=3.0, min_value=1.0, max_value=20.0)
            with hc2:
                port_vol = st.number_input("Portfolio Vol %", value=16.0, step=1.0)
                crash_prob = st.number_input("Crash Probability %", value=5.0, min_value=1.0, max_value=30.0)

            if st.form_submit_button("Run Simulation", use_container_width=True):
                result = GeometricSimulator.safe_haven_frontier(
                    portfolio_return=port_return / 100,
                    portfolio_vol=port_vol / 100,
                    haven_allocation=haven_alloc / 100,
                    crash_probability=crash_prob / 100,
                )
                st.markdown("**10-Year Monte Carlo Results (10,000 paths)**")
                col_p, col_u = st.columns(2)
                with col_p:
                    st.markdown("**Protected Portfolio**")
                    st.metric("CAGR", f"{result['protected']['cagr']*100:.2f}%")
                    st.metric("Median Wealth", f"{result['protected']['median_terminal_wealth']:.2f}x")
                    st.metric("Worst 5%", f"{result['protected']['worst_5pct']:.2f}x")
                with col_u:
                    st.markdown("**Unprotected Portfolio**")
                    st.metric("CAGR", f"{result['unprotected']['cagr']*100:.2f}%")
                    st.metric("Median Wealth", f"{result['unprotected']['median_terminal_wealth']:.2f}x")
                    st.metric("Worst 5%", f"{result['unprotected']['worst_5pct']:.2f}x")

    # Ambiguity Scorer
    with tool_col4:
        st.subheader("🔵 Strategic Ambiguity Scorer")
        amb_text = st.text_area(
            "Paste text to analyze",
            height=150,
            placeholder="Paste an earnings call transcript, strategy doc, or press release...",
        )
        if st.button("Score Ambiguity", use_container_width=True):
            if amb_text.strip():
                result = AmbiguityScorer.score_text(amb_text)
                score = result["ambiguity_score"]
                color = "🔴" if score > 50 else "🟡" if score > 30 else "🟢"
                st.metric(f"{color} Ambiguity Score", f"{score}/100")
                st.caption(result["risk_level"])
                if result.get("flagged_hedges"):
                    st.warning(f"Hedge words: {', '.join(result['flagged_hedges'])}")
                if result.get("flagged_weasels"):
                    st.warning(f"Weasel phrases: {', '.join(result['flagged_weasels'])}")

    st.divider()

    # Lindy Check
    st.subheader("🔴 Lindy Effect Check")
    lc1, lc2, lc3 = st.columns([3, 1, 1])
    with lc1:
        lindy_concept = st.text_input("Concept", placeholder="e.g., Value Investing")
    with lc2:
        lindy_years = st.number_input("Years Existed", value=0, min_value=0)
    with lc3:
        st.write("")
        st.write("")
        if st.button("Check Lindy"):
            if lindy_concept:
                result = FragilityScorer.lindy_check(lindy_concept, lindy_years)
                icon = "✅" if result["lindy_compliant"] else "⚠️"
                st.info(
                    f"{icon} **{result['concept']}**: {result['years_existed']} years old. "
                    f"Expected remaining: {result['expected_remaining_years']} years. "
                    f"Lindy compliant: {'Yes' if result['lindy_compliant'] else 'No'}. "
                    f"Confidence: {result['lindy_confidence']}"
                )
