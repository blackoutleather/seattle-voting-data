import geopandas as gpd
import pandas as pd
import fiona
import streamlit as st
import matplotlib.pyplot as plt
from ingest import DOWNLOAD_PATH
import helper
from inspect import getmembers, isfunction
import inspect
import math
import matplotlib
import altair as alt
from helper import DATA_DIR
import calendar

DROP_COUNTERS = [
    "Times Over Voted",
    "Times Under Voted",
    "Write-In",
    "Times Counted",
    "Times Blank Voted",
]
make_geo_df = st.cache(helper.make_geo_df)
clean_cols = st.cache(helper.clean_cols)
get_seattle_precinct = st.cache(helper.get_seattle_precinct)
join_to_precincts = st.cache(helper.get_all_geos)

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
    "I don't know why there are no voters in these precincts. "
    "\n* Note that in major publication's maps they "
    "join these empty precincts to a neighbor presumably to avoid questions"
    "\n* Don't know your district/voting precinct? Checkout King County for "
    "[maps and other info](https://kingcounty.gov/depts/elections/elections/maps/precinct-and-district-data.aspx)"
)


def decorate(func):
    # See explanation below
    lines = inspect.stack(context=2)[1].code_context
    decorated = any(line.startswith("@") for line in lines)

    print(func.__name__, 'was decorated with "@decorate":', decorated)
    return func


@st.cache
def voter_data():
    path = "/Users/devin.wilkinson/Downloads/BallotStatus King 120219.csv"
    misaligned = pd.read_csv(path, index_col=None).pipe(clean_cols)
    cols = misaligned.columns
    aligned = misaligned.reset_index()
    # drop last col
    aligned = aligned.iloc[:, :-1]

    aligned.columns = cols
    return aligned

@st.cache
def get_year_month():
    df = pd.read_pickle(f"{DATA_DIR}/seattle_data.pickle")
    df = df[df.precinct.str.startswith('SEA ')]
    return {year: months.month.unique() for year, months in df.groupby("year")}


@st.cache
def get_election(year, month):
    df = pd.read_pickle(f"{DATA_DIR}/seattle_data.pickle")
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



def join_vote_data(df, er, agg_geo):
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
        df, agg_vote, left_on="precinct_name", right_on="precinct"
    ).dissolve(by=agg_geo, aggfunc="sum", as_index=False)
    return joined


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
def multi_plot(cntrs, df):
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
                column=cntrs[i], legend=True, ax=i_ax,
                #scheme='quantiles',
                #k=40
                #cmap='OrRd'
            )
            i_ax.axes.xaxis.set_visible(False)
            i_ax.axes.yaxis.set_visible(False)
        except IndexError:
            fig.delaxes(i_ax)
    return fig

@st.cache
def total_row(tdf, label_col):
    total = tdf.sum(numeric_only=True)
    out = tdf.append(total, ignore_index=True)
    out[label_col] = out[label_col].fillna("Total")
    # out["Registered Voters"] = out[counters[:-1]].sum(axis=1) / out["Registered Voters"]
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


if __name__ == "__main__":
    # setup streamlit
    st.set_page_config(layout="wide")
    st.set_option("deprecation.showPyplotGlobalUse", True)

    st.image("./resources/dead_people.jpeg", width=300)
    st.markdown('# "I SEA ELECTION DATA"')
    st.markdown(
        "I can see Seattle election data and now you can too. What patterns are revealed when you can see where "
        "the votes are coming from? The votes are coming from inside the house."
    )

    col1, col2, col3 = st.beta_columns(3)

    # inputs
    year_month_dict = get_year_month()

    geo = join_to_precincts("Council_Districts")

    # widgets
    year = col1.selectbox("Election Year", list(year_month_dict.keys()))
    month = col1.selectbox("Election Month", sorted(year_month_dict[year]), format_func=lambda x: calendar.month_name[x])

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
    erase_trump = st.checkbox("Erase Trump?", value=False)
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
    geo_select = col3.selectbox("Agg Geo", [rename_geos[name] for name in geo_opts])
    agg_geo = inverse_geos[geo_select]

    full_vote = join_vote_data(geo, election_race, agg_geo=agg_geo)

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
    normed_count.loc[:, counters] = normed_count.loc[
        :, counters
    ]  # .applymap(lambda x: "{:.2%}".format(x ))
    raw_count.rename(columns=rename_geos, inplace=True)

    merged = pd.merge(
        normed_count,
        raw_count,
        left_index=True,
        right_index=True,
        suffixes=[" Normed", " Counts"],
    )
    merged = merged[merged["Registered Voters Counts"] > 0]
    summary = merged.sort_values(rename_geos[agg_geo])

    plot_type = col3.selectbox("Plot Type", ["Absolute Counts", "Normed Counts"])

    expander = st.beta_expander("FAQ")
    expander.markdown(NOTES)

    if plot_type == "Normed Counts":
        normed.loc[:,counters]  = normed.loc[:,counters] * 100
        fig = multi_plot(counters, normed)
    else:
        fig = multi_plot(counters, full_vote[full_vote["Registered Voters"] > 0])

    st.write(fig)

    styled = (
        summary.sort_values(summary.columns[-1], ascending=False)
        .set_index(summary.columns[0])
        .style.background_gradient(subset=[summary.columns[1]])
        .background_gradient(subset=[summary.columns[2]])
        .format("{:.2%}", subset=[col for col in summary.columns if "Normed" in col])
        .format("{:,.0f}", subset=[col for col in summary.columns if "Counts" in col])
    )

    st.table(styled)  # ,height=6000)
