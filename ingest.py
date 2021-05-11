from bs4 import BeautifulSoup, NavigableString, Tag
import urllib.request
import pandas as pd
import datetime as dt
import requests
from urllib.error import HTTPError

base_url = "https://kingcounty.gov"

DOWNLOAD_PATH = "/Users/devin.wilkinson/Desktop/vote_data"


def find_final_precinct(url):
    html_page = urllib.request.urlopen(url)
    soup = BeautifulSoup(html_page, "html.parser")
    header_gen = (x for x in soup.find_all("h3") if "Final precinct" in x.text)
    final_precinct_header = next(header_gen, None)

    if final_precinct_header:
        nextNode = final_precinct_header
        while True:
            nextNode = nextNode.next_element
            if nextNode is None:
                break
            if isinstance(nextNode, Tag):
                if nextNode.name == "ul":
                    iterator = (
                        x.get("href")
                        for x in nextNode.select("a")
                        if "comma" in x.text.lower()
                    )  # comma indicates csv
                    link = next(iterator, None)
                    if link.startswith("/~/media") or link.startswith("~/media"):
                        return "https://kingcounty.gov/" + link
                    return link
            if isinstance(nextNode, Tag):
                if nextNode.name == "h3":
                    break
    else:
        return None


def download_csvs(year, month, save_path):
    month_str = str(month).zfill(2)
    results_url = (
        f"https://kingcounty.gov/depts/elections/results/{year}/{year}{month_str}.aspx"
    )

    print(f"Parsing page {results_url}")
    try:
        found_link = find_final_precinct(results_url)
    except HTTPError:
        print("Failed to load ")
        return None

    if found_link:
        try:
            print(f"Downloading {found_link}")
            dl_csv = requests.get(found_link)
            url_content = dl_csv.content
            file_name = f"{year}_{month_str}_final_precinct.csv"
            with open(f"{save_path}/{file_name}", "wb") as f:
                f.write(url_content)
        except HTTPError as e:
            print(e)
            print(f"Bad link: {main_results_link}")


def download_all_csvs(start_year=2021, stop_year=2022, save_path=DOWNLOAD_PATH):
    for year in range(start_year, stop_year):
        for month in range(12):
            download_csvs(year, month, save_path=save_path)


if __name__ == "__main__":
    download_all_csvs(save_path=DOWNLOAD_PATH)
