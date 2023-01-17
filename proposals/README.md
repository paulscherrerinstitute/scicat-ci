# A microservice for syncing proposals from duo to scicat
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)


## Getting started
The easiest way to set up a dev environment is to use the provided compose file.
```bash
docker-compose -f docker-compose.dev.yml up --build
```


## Docker
Variables to be supplied for docker run:
- SCICAT_ENDPOINT
- SCICAT_USERNAME
- SCICAT_PASSWORD
- DUO_ENDPOINT
- DUO_SECRET
- DUO_FACILITY
- [DUO_YEAR] Year of the proposals to sync

```bash
IMAGE_NAME=<IMAGE_NAME>
docker build -t $IMAGE_NAME .
docker run -e "SCICAT_ENDPOINT=<SCICAT_ENDPOINT>" -e "SCICAT_USERNAME=<SCICAT_USERNAME>" \
-e "SCICAT_PASSWORD=<SCICAT_PASSWORD>" -e "DUO_ENDPOINT=https://duo.psi.ch/duo/api.php/v1" \
-e "DUO_SECRET=<DUO_SECRET>" -e "DUO_FACILITY=<DUO_FACILITY>" \
$IMAGE_NAME python main.py
# see below for more on duo facilities
```

### DUO Facilities
The below endpoint returns the full list of available DUO Facilities. The `name` of the facility should be passed in as `DUO_FACILITY` for `docker run`.

```bash
curl --location --request GET 'https://duo.psi.ch/duo/api.php/v1/CalendarInfos/facilities' \
--header 'Cookie: SECRET=<DUO_SECRET>'
```

Example showing one element of the returned list:
```json
[
    {
        "name": "sls",
        "description": "Swiss Light Source",
        "id": 1,
        "website": "http://www.psi.ch/sls/calls",
        "ical": "https://duo.psi.ch/duo/machine_ical.php/1/SLS-schedule.ics",
        "beamlineword": "Beamline",
        "beamtimeunit": "Shift",
        "isNum": false,
        "isPhoton": true
    }
]
```
### Helm deployment
The way this Helm deployment works is to deploy one cron per facility and each cron will set up a pod. 
**To keep in mind**: passwords are expected to be base64 encoded.

Variables to be supplied for helm deployment:
- scicat_endpoint
- scicat_username
- scicat_password -> base64 encoded
- duo_endpoint
- duo_secret -> base64 encoded
- [facilities_schedule] -> path to yaml file (same content format as value.yaml duo_facilities block)

```bash 
helm install proposals-sync helm/duo_facility_proposals/ \
-n <NAMESPACE> --create-namespace \
--set "scicat_endpoint=https://dacat-development.psi.ch/api/v3" \
--set "scicat_username=proposalIngestor" \
--set "scicat_password=<SCICAT_PASSWORD>" \
--set "duo_endpoint=https://duo.psi.ch/duo/api.php/v1" \
--set "duo_secret=<DUO_SECRET>" \
```
