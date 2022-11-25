import os
from urllib import parse
from json import dumps

from dotenv import load_dotenv
import requests


load_dotenv("/.env")


def get_token():
    response = requests.post(
        f"{os.environ['LB_BASE_URL']}/Users/login",
        data={"username": os.environ["USERNAME"], "password": os.environ["PASSWORD"]},
    )
    return response.json()["id"]


def get_ds_creation_location(locations_dict):
    fields = {
        "creationLocation": {"inq": list(locations_dict.keys())},
        "fields": ["pid", "creationLocation", "techniques"],
    }
    response = requests.get(
        f"{os.environ['LB_BASE_URL']}/Datasets?filter={parse.quote(dumps(fields))}"
    )
    return list(
        filter(
            lambda x: locations_dict.get(x.get("creationLocation"))
            if x.get("creationLocation")
            else False,
            response.json(),
        )
    )


def get_pid_given_location(access_token, _id):
    response = requests.get(
        f"{os.environ['LB_BASE_URL']}/Datasets/{parse.quote(_id, safe='')}?access_token={access_token}"
    )
    return response.json()


def update_pids_given_location(access_token, _id, technique):
    response = requests.post(
        f"{os.environ['LB_BASE_URL']}/Datasets/{parse.quote(_id, safe='')}/techniquesList?access_token={access_token}",
        technique,
    )
    print(response.json())


def update_all_techniques(access_token, dataset_pids, locations_dict):
    for ds in dataset_pids:
        update_pids_given_location(
            access_token, ds["pid"], locations_dict[ds["creationLocation"]][0]
        )


def main():
    token = get_token()
    ds_pids = get_published_data_ds_pids(token)
    update_all_techniques(token, ds_pids)


if __name__ == "__main__":
    main()
