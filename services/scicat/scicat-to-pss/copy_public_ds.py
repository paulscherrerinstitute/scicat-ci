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
        "description": "dataDescription"
    },
}


def prepFields(item, group):
    return {k: item.get(v, "") for k, v in meaningful_fields[group].items()}


def format_dataset_for_scoring(raw_datasets, group="datasets", pid="pid"):
    return [
        {
            "id": item[pid],
            "group": group,
            "fields": prepFields(item, group),
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
    
    # datasets
    public_datasets = get_public_datasets(f"{scicat_base_url}/datasets")
    logging.info(len(public_datasets))
    scoring_datasets = format_dataset_for_scoring(public_datasets)
    logging.info(len(scoring_datasets))
    to_scoring_datasets = post_datasets_to_scoring(scoring_datasets, pss_items_url)
    logging.info(to_scoring_datasets.json())

    # documents
    public_documents = get_public_datasets(f"{scicat_base_url}/PublishedData")
    logging.info(len(public_documents))
    scoring_documents = format_dataset_for_scoring(public_documents, "documents", "doi")
    logging.info(len(scoring_documents))
    to_scoring_documents = post_datasets_to_scoring(scoring_documents, pss_items_url)
    logging.info(to_scoring_documents.json())
    
    # scores
    scores = compute_weights(f"{pss_base_url}/compute")
    logging.info(scores.json())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main(environ["SCICAT_BASE_URL"], environ["PSS_BASE_URL"])
