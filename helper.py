import geopandas as gpd
import pandas as pd
import shapely
import pathlib
from s3 import S3_Bucket

# use aws role in production
try:
    import aws_creds
except:
    #production
    pass


gpd.io.file.fiona.drvsupport.supported_drivers["KML"] = "rw"


HERE = pathlib.Path(__file__).parent
DATA_DIR = "data"
S3_BUCKET_NAME = "voter-data"

# check that install produces valid polygons
assert shapely.geometry.Polygon([[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]).is_valid


GLOBAL_CRS = "EPSG:4326"

S3_OBJ = S3_Bucket(S3_BUCKET_NAME)


def make_geo_df(name):
    path = f"{DATA_DIR}/{name}.kml"
    info_path = f"{DATA_DIR}/{name}.csv"
    geo_df = gpd.read_file(S3_OBJ.get_s3_file_bytes(path), driver="KML").pipe(
        clean_cols
    )
    info_df = pd.read_csv(S3_OBJ.get_s3_file_bytes(info_path)).pipe(clean_cols)
    return pd.merge(geo_df, info_df, left_index=True, right_index=True).to_crs(
        GLOBAL_CRS
    )


def clean_cols(df):
    new_cols = [col.lower().replace(" ", "_") for col in df.columns]
    df.columns = new_cols
    return df


def get_year_month():
    df = pd.read_pickle(S3_OBJ.get_s3_file_bytes(f"{DATA_DIR}/seattle_data.pickle"))
    df = df[df.precinct.str.startswith("SEA ")]
    return {year: months.month.unique() for year, months in df.groupby("year")}


def get_kc_precinct_gdf():
    path = f"{DATA_DIR}/Voting_Districts_of_King_County___votdst_area.kml"
    path2 = f"{DATA_DIR}/Voting_Districts_of_King_County___votdst_area.csv"

    df = gpd.read_file(S3_OBJ.get_s3_file_bytes(path), driver="KML").pipe(clean_cols)
    info_df = pd.read_csv(S3_OBJ.get_s3_file_bytes(path2)).pipe(clean_cols)
    out = pd.merge(df, info_df).to_crs(GLOBAL_CRS)
    return out.rename(columns={"name": "precinct_name"})


def get_seattle_precinct():
    kc = get_kc_precinct_gdf()
    return kc[kc.precinct_name.str.startswith("SEA ")]


def get_seattle_community_reporting_area():
    path = f"{DATA_DIR}/Community_Reporting_Areas.kml"
    info_path = f"{DATA_DIR}/Community_Reporting_Areas.csv"
    info_df = pd.read_csv(S3_OBJ.get_s3_file_bytes(info_path)).pipe(clean_cols)
    geo_df = gpd.read_file(S3_OBJ.get_s3_file_bytes(path), driver="KML").pipe(
        clean_cols
    )
    return pd.merge(geo_df, info_df, left_index=True, right_index=True).to_crs(
        GLOBAL_CRS
    )


def join_seattle(df):
    seattle = get_seattle_community_reporting_area()
    return gpd.sjoin(df, seattle, how="inner", op="intersects")


def close_polygon(shapely_polygon):
    coords = shapely_polygon.exterior.coords[:]
    if coords[0] != coords[-1]:
        return shapely.geometry.Polygon(coords + coords[0])
    return shapely_polygon


def join_by_max_intersect(small_geo_df, big_geo_df, left_on=None, right_on=None):
    """ return a joined df where poly1 is joined to poly2 if it has max intersection"""
    if not any([left_on, right_on]):
        print("Must specify join keys")
        return None

    # drop common join cols
    if left_on != right_on:
        small_geo_df.drop(columns=[right_on], inplace=True, errors="ignore")
        big_geo_df.drop(columns=[left_on], inplace=True, errors="ignore")

    overlay = gpd.overlay(small_geo_df, big_geo_df, how="intersection")

    # calculate overlay intersection area
    overlay["intersect_area"] = overlay.geometry.area
    overlay = overlay[[left_on, right_on, "intersect_area"]]

    # spatial join leads to small polygons being members for multiple large polygons at borders
    for df in [small_geo_df, big_geo_df]:
        df.drop(columns=["index_left", "index_right"], inplace=True, errors="ignore")
    s_joined = gpd.sjoin(small_geo_df, big_geo_df, how="left", op="intersects")

    # select the largest intersection
    merged = pd.merge(s_joined, overlay, on=[left_on, right_on])
    idx_max = (
        merged.groupby([left_on])["intersect_area"].transform(max)
        == merged["intersect_area"]
    )
    merged.drop(columns=["intersect_area"], inplace=True)
    return merged[idx_max]


def get_all_geos(join_type="inner"):
    drop_cols = [
        "description_left",
        "objectid_left",
        "votdst",
        "sum_voters",
        "shape_length_left",
        "index_right",
        "name_right",
        "description_right",
        "objectid_right",
        "display_name",
        "shape_length_right",
    ]
    rename_dict = {
        "shape_area_left": "shape_area_precinct",
        "area_acres": "area_acres_cd",
        "area_sqmi": "area_sqmi_cd",
        "shape_area_right": "shape_area_cd",
    }
    precinct_df = get_seattle_precinct()
    cd = make_geo_df("Council_Districts")
    cd_precincts = (
        join_by_max_intersect(
            precinct_df, cd, left_on="precinct_name", right_on="c_district"
        )
        .drop(columns=drop_cols, errors="ignore")
        .rename(columns=rename_dict)
    )

    scr = get_seattle_community_reporting_area()
    scr = scr.drop(
        columns=["name", "description", "objectid", "cra_grp", "shape_length"]
    )
    cd_precincts_cras = join_by_max_intersect(
        cd_precincts, scr, left_on="precinct_name", right_on="cra_no"
    )

    zips = make_geo_df("Zip_Codes")
    zips = zips.drop(
        columns=["name", "description", "objectid", "shape_length", "county"]
    )

    cd_precincts_cras_zips = join_by_max_intersect(
        cd_precincts_cras, zips, left_on="precinct_name", right_on="zipcode"
    )
    return cd_precincts_cras_zips
