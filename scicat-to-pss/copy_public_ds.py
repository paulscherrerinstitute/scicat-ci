import logging
from os import environ

from requests import get, post, delete

meaningful_fields = {
    "datasets": {
        "title": "datasetName",
        "keywords": "keywords",
        "metadata": "scientificMetadata",
        "description": "description",
    },
    "documents": {
        "doi": "doi",
        "creator": "creator",
        "title": "title",
        "abstract": "abstract",
        "authors": "authors",
        "datasets": {
            "owner": "owner",
            "principal investigator": "principalInvestigator",
            "keywords": "keywords",
            "description": "description",
            "title": "datasetName",
            "metadata": "scientificMetadata",
        },
    },
}


def prepNestedFields(item, fields_list):
    return {dk: extractFieldValue(dk, sk, item) for dk, sk in fields_list.items()}


def extractFieldValue(dk, sk, item):
    output = ""
    if type(sk) == dict:
        if type(item[dk]) == list:
            output = [prepNestedFields(i, sk) for i in item[dk]]
        else:
            output = prepNestedFields(item[dk], sk)
    elif sk in item.keys():
        output = item[sk]

    return output


def format_documents_for_scoring(raw_datasets):
    return [
        {
            "id": item["doi"],
            "group": "documents",
            "fields": prepNestedFields(item, meaningful_fields["documents"]),
        }
        for item in raw_datasets
    ]


def prepFields(item, group):
    return {k: item.get(v, "") for k, v in meaningful_fields[group].items()}


def format_dataset_for_scoring(raw_datasets):
    return [
        {
            "id": item["pid"],
            "group": "datasets",
            "fields": prepFields(item, "datasets"),
        }
        for item in raw_datasets
    ]


def delete_all_scored(pss_items_url):
    res = get(
        pss_items_url,
    )
    delete_codes = map(
        lambda x: delete(f"{pss_items_url}/{x['id']}").status_code, res.json() or []
    )
    return list(delete_codes)


def post_datasets_to_scoring(scoring_datasets, pss_items_url):
    return post(pss_items_url, json=scoring_datasets)


def compute_weights(pss_compute_url):
    return post(pss_compute_url)


def get_public_datasets(sc_datasets_url):
    res = get(
        sc_datasets_url,
    )
    return res.json()


def main(scicat_base_url, pss_base_url):
    logging.info(scicat_base_url)
    logging.info(pss_base_url)
    pss_items_url = f"{pss_base_url}/items"
    delete_status_codes = delete_all_scored(pss_items_url)
    logging.info(delete_status_codes)
    public_datasets = get_public_datasets(f"{scicat_base_url}/datasets")
    logging.info(len(public_datasets))
    scoring_datasets = format_dataset_for_scoring(public_datasets)
    logging.info(len(scoring_datasets))
    scoring_documents = format_documents_for_scoring(public_datasets)
    logging.info(len(scoring_documents))
    to_scoring_datasets = post_datasets_to_scoring(scoring_datasets, pss_items_url)
    logging.info(to_scoring_datasets.json())
    to_scoring_documents = post_datasets_to_scoring(scoring_documents, pss_items_url)
    logging.info(to_scoring_documents.json())
    scores = compute_weights(f"{pss_base_url}/compute")
    logging.info(scores.json())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main(environ["SCICAT_BASE_URL"], environ["PSS_BASE_URL"])
