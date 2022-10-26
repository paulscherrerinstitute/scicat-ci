from asyncio import constants
import logging
from os import environ

from requests import get, post

meaningful_fields = {
    'datasets': {
        'title': 'datasetName',
        'keywords': 'keywords',
        'metadata': 'scientificMetadata'
    },
}


def prepFields(item, group):
    return {
        k: item.get(v, '')
        for k, v
        in meaningful_fields[group].items()
    }


def format_dataset_for_scoring(raw_datasets):
    return [
        {
            'id': item['pid'],
            'group': 'datasets',
            'fields': prepFields(item, 'datasets')
        }
        for item
        in raw_datasets
    ]


def post_datasets_to_scoring(scoring_datasets, pss_items_url):
    return post(
        pss_items_url,
        json=scoring_datasets
    )


def compute_weights(pss_compute_url):
    return get(pss_compute_url)


def get_public_datasets(sc_datasets_url):
    res = get(
        sc_datasets_url,
    )
    return res.json()


def main(scicat_base_url, pss_base_url):
    logging.info(scicat_base_url)
    logging.info(pss_base_url)
    public_datasets = get_public_datasets(f"{scicat_base_url}/datasets")
    logging.info(len(public_datasets))
    scoring_datasets = format_dataset_for_scoring(public_datasets)
    logging.info(len(scoring_datasets))
    to_scoring = post_datasets_to_scoring(scoring_datasets, f"{pss_base_url}/items")
    logging.info(to_scoring)
    scores = compute_weights(f"{pss_base_url}/compute")
    logging.info(scores)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main(environ['SCICAT_BASE_URL'], environ['PSS_BASE_URL'])