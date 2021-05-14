from ingest import DOWNLOAD_PATH
import glob
import pandas as pd
from helper import get_all_geos
from s3 import S3_Bucket

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
S3_BUCKET_NAME = 'voter-data'
S3_OBJ = S3_Bucket(S3_BUCKET_NAME)

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
    return df[df.precinct.isinls(cd_precincts.name_left.unique())].to_pickle(save_path)


def get_voter_reg():
    zipfile = '1702125604/202105_VRDB_Extract.txt'
    obj = S3_OBJ.get_object(Bucket=self.bucket_name, Key=f"data/{zipfile}")
    df = pd.read_csv(obj)
    return df

def get_age_data():
    """just a groupby agg to describe of agg by precinct"""
    return pd.read_pickle(S3_OBJ.get_s3_file_bytes("data/precinct_age.pickle"))

def get_long_age_data():
    """ all voter ages joined to precincts"""
    return pd.read_pickle(S3_OBJ.get_s3_file_bytes("data/precinct_age_long.pickle"))

def join_geos_to_voter_age(geo_df):
    #geo_df = get_all_geos()
    geo_df = geo[['precinct_name', 'geometry', 'c_district', 'gen_alias', 'zipcode']]
    age_data = get_long_age_data()
    joined = pd.merge(
        geo_df, age_data, left_on="precinct_name", right_on="PrecinctName", how="left"
    )
    S3_OBJ.write_pickle(joined, 'data/voter_age_geos.pickle')



if __name__ == "__main__":
    # df = get_all_the_data()
    make_seattle_data(DOWNLOAD_PATH + "/seattle_data.pickle")
