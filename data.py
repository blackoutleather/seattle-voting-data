from ingest import DOWNLOAD_PATH
import glob
import pandas as pd
from helper import get_all_geos

DTYPES = {
    "precinct": "category",
    "race": "category",
    "leg": "category",
    "cc": "category",
    "cg": "category",
    "countergroup": "category",
    "party": "category",
    "countertype": "category",
    "sumofcount": "int32",
    "year": "int32",
    "month": "int32",
}


def make_df(file_path):
    print(f"loading {file_path}")
    encoding = None
    if file_path in [
        "/Users/devin.wilkinson/Desktop/vote_data/2019_11_final_precinct.csv",
        "/Users/devin.wilkinson/Desktop/vote_data/2020_08_final_precinct.csv",
        "/Users/devin.wilkinson/Desktop/vote_data/2019_08_final_precinct.csv",
    ]:
        encoding = "cp1252"
    file_name = file_path.replace(DOWNLOAD_PATH + "/", "")
    year, month = file_name.split("_")[0], file_name.split("_")[1]
    df = pd.read_csv(file_path, encoding=encoding)
    return df.assign(year=year, month=month)


def make_big_df(data_path):
    return pd.concat(make_df(file) for file in glob.iglob(data_path + "/*.csv"))


def clean_cols(df):
    new_cols = [col.lower().replace(" ", "_") for col in df.columns]
    df.columns = new_cols
    return df


def get_all_the_data():
    df = make_big_df(DOWNLOAD_PATH).pipe(clean_cols)
    df["sumofcount"] = df.sumofcount.map(
        lambda x: x.replace(",", "") if type(x) == str else x
    )
    df = df.astype(dtype=DTYPES)
    return df


def make_seattle_data(save_path):
    # council districts and precincts
    cd_precincts = get_all_geos("Council_Districts")
    df = get_all_the_data()
    return df[df.precinct.isin(cd_precincts.name_left.unique())].to_pickle(save_path)


if __name__ == "__main__":
    # df = get_all_the_data()
    make_seattle_data(DOWNLOAD_PATH + "/seattle_data.pickle")
