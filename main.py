import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import helper
import math
import matplotlib
from helper import DATA_DIR, S3_OBJ
import calendar
from data import get_age_data

DROP_COUNTERS = [
    "Times Over Voted",
    "Times Under Voted",
    "Write-In",
    "Times Counted",
    "Times Blank Voted",
]

make_geo_df = st.cache(helper.make_geo_df, allow_output_mutation=True)
clean_cols = st.cache(helper.clean_cols)
get_seattle_precinct = st.cache(helper.get_seattle_precinct)
get_all_geos = st.cache(helper.get_all_geos)
get_year_month = st.cache(helper.get_year_month)
get_seattle_precinct = st.cache(get_seattle_precinct)
get_age_data = st.cache(get_age_data)

rename_geos = {
    "precinct_name": "Voter Precinct",
    "zipcode": "Zipcode",
    "c_district": "Council District",
    "gen_alias": "Neighborhood",
}
inverse_geos = {value: key for key, value in rename_geos.items()}

NOTES = (
    "* Vote Data is tabulated at the voting precinct level. "
    "However, I provide the option to aggregate the votes at a number of geographic boundaries. "
    "In the case where a precinct intersects with multiple larger geographic boundaries I have assigned that precinct "
    "to the geography that has the greatest intersection."
    "\n* Voter precincts with zero registered voters show up as blank in the map. "
    "I don't know why there are no voters in these precincts. Note that these blank precincts are more numerous "
    "in 2016 elections and slowly disappear as we get to 2020. Its wild to think that there were so many non-voting "
    "parts of the city just 4 years ago."
    "\n* Note that in major publication's maps they "
    "join these empty precincts to a neighbor presumably to avoid questions"
    "\n* Don't know your district/voting precinct? Checkout King County for "
    "[maps and other info](https://kingcounty.gov/depts/elections/elections/maps/precinct-and-district-data.aspx)"
    '\n* *"What up with "Erase Trump?*": Notice that about 8% of Seattle voted for Trump. But the Trump vote rate is not uniform. '
    "For example 30% of Broadmoor voted for Trump in both elections. Now notice that the precincts "
    "with high Trump vote counts also vote at high rates for other unpopular candidates i.e. Loren Culp, Egan Orion etc. "
    'Turns out we have our own analog of "Red States". \nUse the "Erase Trump" checkbox  '
    "to play a game where you imagine that Trump losers didn't vote for the loser in a given race in a given precinct. "
    "How does that change things? (This button subtracts the 2020 Trump vote count in each precinct from the vote count "
    "of the 2nd place candidate in a given election race. You havin' fun yet or are You mad, bro?"
    "\n* *Why do the Geographic Labels look like crap?*: Heya, lay off! It ain't exactly easy to cram all that sweet sweet "
    "info in one map. I'm workin' on it, mmk?"
)


DEMO_NOTES = (
    "* Why do the zipcode geos look different? The voter age data I'm working with is much larger than the vote count data "
    " in the election data view. To make it run faster, I am not doing any fancy geography maniplulation and just drawing "
    "the zipcodes as they are. In the election view I am drawing only the portions of the zipcodes that have Seattle voter precincts."
    " However, I am not including non-Seattle voters in the age statistics below. It's all Seattle and only Seattle, baby! "
    "\n Jet City FOHEVAH!!"
)


@st.cache
def get_election(year, month):
    df = pd.read_pickle(S3_OBJ.get_s3_file_bytes(f"{DATA_DIR}/seattle_data.pickle"))
    # filter out non-seattle races
    seattle = df.precinct.str.startswith("SEA ")
    non_seattle_races = (
        pd.DataFrame(df[seattle].groupby("race").sumofcount.sum())
        .query("sumofcount == 0")
        .index
    )
    return df.query(
        "year == @year and month == @month and countertype not in @DROP_COUNTERS and race not in @non_seattle_races"
    )


@st.cache
def agg_votes(er):
    return er.groupby(["precinct", "binned_counter"]).sumofcount.sum().unstack()


@st.cache
def join_vote_to_geo(geo_df, er, agg_geo, counters):
    """['precinct',
    'race',
    'leg',
    'cc',
    'cg',
    'countergoup',
    'party',
    'countertype',
    'sumofcount']"""

    agg_vote = agg_votes(er)
    joined = pd.merge(
        geo_df, agg_vote, left_on="precinct_name", right_on="precinct", how="left"
    )
    joined.loc[:, counters] = joined.loc[:, counters].fillna(0)
    age_data = get_age_data()
    joined = pd.merge(
        joined,
        age_data[["mean", "25%", "50%", "75%"]],
        left_on="precinct_name",
        right_index=True,
    )
    joined = joined.dissolve(by=agg_geo, aggfunc="sum", as_index=False, dropna=False)
    return joined


@st.cache
def join_demo_to_geo(agg_geo, geo_df, metrics, council_districts=None):
    cols = ["precinct_name", "c_district", "gen_alias", "zipcode", "age_years"]
    voter_age_df = pd.read_pickle(
        S3_OBJ.get_s3_file_bytes(f"{DATA_DIR}/voter_age_geos.pickle")
    )[cols]

    if council_districts:
        voter_age_df = voter_age_df.query("c_district in @council_districts")

    agg_df = voter_age_df.groupby(agg_geo)["age_years"].describe().reset_index()
    agg_df = agg_df.rename(
        columns={"count": "Voter Count", "mean": "Average", "50%": "Median"}
    )

    return pd.merge(geo_df, agg_df, on=agg_geo)


@st.cache
def bin_race(er, other_pct):
    counts = er.groupby("countertype").sumofcount.sum().sort_values()
    votes = counts[counts.index != "Registered Voters"]
    normed_votes = votes.div(votes.sum()).reset_index()
    reg_voters = counts[counts.index == "Registered Voters"]
    reg_voters = reg_voters.div(reg_voters.sum()).reset_index()
    non_others = pd.concat([reg_voters, normed_votes]).query("sumofcount > @other_pct")
    er["binned_counter"] = er.countertype.map(
        lambda x: x if x in non_others.countertype.tolist() else "Other"
    )
    return er


@st.cache
def get_trump_votes():
    election = get_election(2020, 11)
    trump2020 = election.race.str.contains(
        "President"
    ) & election.countertype.str.contains("Trump")
    trump_votes = election[trump2020].groupby("precinct").sumofcount.sum()
    return pd.DataFrame(trump_votes).rename(columns={"sumofcount": "trump_votes"})


@st.cache
def erase_trump_from_loser(er):
    counts = er.groupby("binned_counter").sumofcount.sum()
    votes = counts[counts.index != "Registered Voters"].sort_values()
    second_place = votes.index[-2]
    er = pd.merge(
        er, get_trump_votes(), left_on="precinct", right_index=True, how="left"
    )
    # erase trump
    er.loc[er.binned_counter == second_place, "sumofcount"] = (
        er.loc[er.binned_counter == second_place, "sumofcount"] - er.trump_votes
    )
    return er.drop("trump_votes", axis=1)


@st.cache
def get_election_race(election, race, erase_trump=False, other_pct=0.1):
    er = election[election["race"] == race]
    er = bin_race(er, other_pct=other_pct)
    if erase_trump:
        er = er.pipe(erase_trump_from_loser)
    return er.query("sumofcount > 0")


@st.cache(hash_funcs={matplotlib.figure.Figure: lambda _: None})
def multi_plot(cntrs, df, legend_label, agg_geo=None, plot_geo_labels=False):
    df = df.dropna(subset=["geometry"])
    n_plots = len(cntrs)
    ncols = 2
    nrows = math.ceil(n_plots / 2)
    figsize = (15, 10 * nrows)
    fig, ax = plt.subplots(nrows=nrows, ncols=ncols, figsize=figsize)
    fig.tight_layout()
    # plt.subplots_adjust(
    #     left=None, bottom=None, right=None, top=None, wspace=0, hspace=0.2
    # )
    for i, i_ax in enumerate(ax.flat):
        try:
            i_ax.title.set_text(cntrs[i])
            df.plot(
                column=cntrs[i],
                legend=True,
                ax=i_ax,
                legend_kwds={
                    "label": legend_label,
                    #'orientation': "horizontal"
                }
                # scheme='quantiles',
                # k=40
                # cmap='OrRd'
            )
            i_ax.axes.xaxis.set_visible(False)
            i_ax.axes.yaxis.set_visible(False)

            if plot_geo_labels:
                df.apply(
                    lambda x: i_ax.annotate(
                        s=x[agg_geo],
                        xy=x.geometry.centroid.coords[0],
                        fontsize="xx-small",
                        ha="center",
                    ),
                    axis=1,
                )
        except IndexError:
            fig.delaxes(i_ax)
    return fig


@st.cache
def total_row(tdf, label_col):
    total = tdf.sum(numeric_only=True)
    out = tdf.append(total, ignore_index=True)
    if pd.api.types.is_numeric_dtype(out[label_col]):
        idx = out[label_col].idxmax()
        out[label_col] = out[label_col].astype(int).astype(str)
        out.loc[idx, label_col] = "Total"

    else:
        out[label_col] = out[label_col].fillna("Total")
    return out


@st.cache
def norm_vote_counts(df, counters):
    df["Registered Voters"] = (
        df.loc[:, counters[:-1]].sum(axis=1) / df["Registered Voters"]
    )
    df.loc[:, counters[:-1]] = df.loc[:, counters[:-1]].div(
        df[counters[:-1]].sum(axis=1), axis=0
    )
    return df


def demographics():
    col1, col2 = st.beta_columns(2)

    geo = helper.get_all_geos()

    # agg geo
    geo_opts = ["precinct_name", "zipcode", "c_district", "gen_alias"]
    geo_select = col1.selectbox(
        "Geographical Aggregation", [rename_geos[name] for name in geo_opts]
    )
    agg_geo = inverse_geos[geo_select]

    control = {
        "precinct_name": "Precincts",
        "zipcode": ["Zip_Codes"],
        "c_district": ["Council_Districts"],
        "gen_alias": ["Community_Reporting_Areas"],
    }

    if agg_geo == "precinct_name":
        geo_df = get_seattle_precinct()
    else:
        geo_df = make_geo_df(control[agg_geo][0])[["geometry", agg_geo]]

    cd = col2.multiselect("Council District", list(range(1, 10)))
    plot_geo_labels = col1.checkbox("Plot Geographic Labels", value=False)

    expander = st.beta_expander("FAQ")
    expander.markdown(DEMO_NOTES)

    metrics = ["Average", "Median", "Voter Count"]
    geo_demo = join_demo_to_geo(agg_geo, geo_df, metrics, council_districts=cd)

    fig = multi_plot(
        metrics,
        geo_demo,
        legend_label="Voter Age in Years",
        agg_geo=agg_geo,
        plot_geo_labels=plot_geo_labels,
    )

    st.markdown(f"## Registered Voter Age Metrics by {rename_geos[agg_geo]}")

    st.pyplot(fig)

    table = geo_demo[[agg_geo] + metrics].filter("c_district in @cd").set_index(agg_geo)

    styled_table = (
        table.sort_values(table.columns[-1], ascending=False)
        .style.background_gradient(subset=[table.columns[0]])
        .background_gradient(subset=[table.columns[1]])
        .format("{:.1f}", subset=table.columns[0:2])
        .format("{:,.0f}", subset=table.columns[-1])
    )

    st.table(styled_table)


def voter():
    col1, col2, col3 = st.beta_columns(3)

    # inputs
    year_month_dict = get_year_month()

    geo = helper.get_all_geos()

    # widgets
    year = col1.selectbox("Election Year", list(year_month_dict.keys()))
    month = col1.selectbox(
        "Election Month",
        sorted(year_month_dict[year]),
        format_func=lambda x: calendar.month_name[x],
    )

    other_pct = col2.slider(
        'Bin Candidates receiving less than X% of vote into "Other"',
        value=10,
        min_value=0,
        max_value=40,
        step=1,
    )
    other_pct = other_pct / 100

    # election race
    election = get_election(year, month)
    races = election.race.unique()
    race = col2.selectbox("Race", races)
    plot_geo_labels = st.checkbox("Plot Geographic Labels", value=False)
    erase_trump = st.checkbox("Erase Trump", value=False)
    election_race = get_election_race(
        election, race, erase_trump=erase_trump, other_pct=other_pct
    )
    ranked_counters = (
        election_race.groupby("binned_counter")
        .sumofcount.sum()
        .sort_values()
        .index.tolist()
    )
    counters = ranked_counters[:-1][::-1] + [ranked_counters.pop()]

    # agg geo
    geo_opts = ["precinct_name", "zipcode", "c_district", "gen_alias"]
    geo_select = col3.selectbox(
        "Geographical Aggregation", [rename_geos[name] for name in geo_opts]
    )
    agg_geo = inverse_geos[geo_select]

    full_vote = join_vote_to_geo(geo, election_race, agg_geo=agg_geo, counters=counters)

    # turnout
    raw_count = full_vote.copy()
    raw_count = raw_count.pipe(lambda x: total_row(x, agg_geo))
    normed = raw_count.copy()

    # normalize actual votes
    normed = norm_vote_counts(normed, counters)

    normed_count = normed.loc[:, [agg_geo] + counters].sort_values(
        counters[0], ascending=False
    )
    raw_count = raw_count.loc[:, [agg_geo] + counters].sort_values(
        counters[0], ascending=False
    )
    normed_count.loc[:, counters] = normed_count.loc[:, counters]
    raw_count.rename(columns=rename_geos, inplace=True)

    merged = pd.merge(
        normed_count,
        raw_count,
        left_index=True,
        right_index=True,
        suffixes=[" Normed", " Counts"],
    )
    merged = merged[merged["Registered Voters Counts"] > 0]

    total_row_idx = merged[rename_geos[agg_geo]] == "Total"
    total_row_df = merged[total_row_idx]
    merged = merged[~total_row_idx]
    summary = merged.sort_values(rename_geos[agg_geo])
    summary = pd.concat([total_row_df, summary])

    plot_type = col3.selectbox("Plot Type", ["Normed Counts", "Absolute Counts"])

    expander = st.beta_expander("FAQ")
    expander.markdown(NOTES)

    if plot_type == "Normed Counts":
        normed.loc[:, counters] = normed.loc[:, counters] * 100
        fig = multi_plot(
            counters,
            normed,
            legend_label="% of Total Votes Cast",
            agg_geo=agg_geo,
            plot_geo_labels=plot_geo_labels,
        )
    elif plot_type == "Absolute Counts":
        fig = multi_plot(
            counters,
            full_vote[full_vote["Registered Voters"] > 0],
            legend_label="Votes",
            agg_geo=agg_geo,
            plot_geo_labels=plot_geo_labels,
        )

    st.markdown(
        f"## {plot_type} of Votes for {race} in {calendar.month_name[month]}, {year} aggregated by {rename_geos[agg_geo]}"
    )
    st.pyplot(fig)

    styled = (
        summary.sort_values(summary.columns[-1], ascending=False)
        .set_index(summary.columns[0])
        .style.background_gradient(subset=[summary.columns[1]])
        .background_gradient(subset=[summary.columns[2]])
        .format("{:.2%}", subset=[col for col in summary.columns if "Normed" in col])
        .format("{:,.0f}", subset=[col for col in summary.columns if "Counts" in col])
    )

    st.table(styled)


@st.cache
def put_centers_on_polys(geo_df):
    geo_df["coords"] = geo_df["geometry"].apply(
        lambda x: x.representative_point().coords[:][0] if x else None
    )
    # geo_df["coords"] = [coords[0] for coords in geo_df["coords"]]
    return geo_df


if __name__ == "__main__":
    # setup streamlit
    st.set_page_config(layout="wide")
    st.set_option("deprecation.showPyplotGlobalUse", True)

    st.image("./resources/dead_people.jpeg", width=300)
    st.markdown('# "I SEA ELECTION DATA"')
    st.markdown(
        "I can see Seattle election data and now you can too. What patterns are revealed when you can see where "
        "the votes are coming from? It appears that many of these votes are coming from inside the house."
    )

    tab = st.sidebar.radio("", ["Elections Data", "Voter Demographics Data"])

    if tab == "Elections Data":
        with st.spinner("Loadin' votes..."):
            voter()
    else:
        with st.spinner("Gettin' Voters...."):
            demographics()
