#!/bin/bash

# This requires preliminary setting status: "public" in scicat in mongo directly for the desired publishedData to be updated in datacite
# It might also require some data curation in scicat to ensure that the metadata is complete and valid for datacite, for examaple, for the sync of old data these steps were necessary:
# 1. Split names of creators with multiple names into separate creators in the metadata of the publishedData (either comma or semicolon separated names)
# 2. Add affiliation.name: Not Available to all creators in the metadata of the publishedData

ENVIRONMENT=$1

SCICAT_TOKEN=$2
DATACITE_USERNAME=$3
DATACITE_TOKEN=$4
INPUT_DOI=$5

if [ "$ENVIRONMENT" == "dev" ]; then
    SCICAT_URL="https://scicat.development.psi.ch"
    DATACITE_URL="https://api.test.datacite.org"
    LANDING_PAGE_URL="https://oaipmh.development.psi.ch/detail/"
elif [ "$ENVIRONMENT" == "prod" ]; then
    SCICAT_URL="https://dacat.psi.ch"
    DATACITE_URL="https://api.datacite.org"
    LANDING_PAGE_URL="https://doi.psi.ch/detail/"
else
    echo "Unknown environment: $ENVIRONMENT"
    exit 1
fi

# if input DOI is provided, process only that DOI by making manually a doi list
if [ -n "$INPUT_DOI" ]; then
    DOIS=$(echo "[{\"doi\": \"$INPUT_DOI\"}]")
else
    DOIS=$(curl -X 'GET' \
    "$SCICAT_URL/api/v4/publisheddata?filter=%7B%22where%22%3A%7B%22metadata.creators.affiliation.name%22%3A%22Not%20Available%22%2C%20%22status%22%3A%22public%22%7D%7D" \
    -H 'accept: application/json' \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $SCICAT_TOKEN")
fi

DOIS_ID=$(echo "$DOIS" | jq -r '.[].doi')

echo "Retrieved DOIs: $DOIS_ID"

for DOI in $(echo "$DOIS" | jq -r '.[].doi | @uri'); do
    echo "Processing DOI: $DOI"

    RAW_CONTENT=$(curl -X GET -H "Authorization: Bearer $SCICAT_TOKEN" \
        -H "Content-Type: application/json" \
        "$SCICAT_URL/api/v4/publisheddata/${DOI}" \
        | jq 'del(.doi, .id, .createdAt, .updatedAt, .__v, .status, .updatedBy, .createdBy, ._id, .pid, .numberOfFiles, .sizeOfArchive) | .status = "registered" | .metadata.publisher.name = "PSI Open Data Provider"')

    if [ $? -ne 0 ]; then
        echo "Error getting DOI $DOI in SciCat"
        continue
    fi

    THUMBNAIL=$(echo "$RAW_CONTENT" | jq -r '.metadata.thumbnail // empty')

    if [ ! -z "$THUMBNAIL" ]; then
        PREFIX="data:image/jpeg;base64"
        RESIZED_THUMBNAIL=$(echo "$THUMBNAIL" | tr -d '"' | awk -F, '{print $2}' | base64 -d | magick - -resize 400x400 -strip -quality 90 jpeg:- | base64 | awk -v pre="$PREFIX" '{print pre "," $0}')
        # for gif thumbnails, use the following command instead of the above
        # PREFIX="data:image/gif;base64"
        # RESIZED_THUMBNAIL=$(echo "$THUMBNAIL" | tr -d '"' | awk -F, '{print $2}' | base64 -d | magick - -coalesce -thumbnail 300x300 -fuzz 10% -colorspace Gray -depth 4 -layers Optimize gif:- | base64 | awk -v pre="$PREFIX" '{print pre "," $0}')
    else
        RESIZED_THUMBNAIL=""
    fi
    echo "$RESIZED_THUMBNAIL" > "thumbnail_$DOI.txt"

    DOI_CONTENT=$(echo "$RAW_CONTENT" | jq \
        --arg new_thumb "$RESIZED_THUMBNAIL" \
        'del(.doi, .id, .createdAt, .updatedAt, .__v, .status, .updatedBy, .createdBy, ._id, .pid, .numberOfFiles, .sizeOfArchive, .DownloadLink) 
        | .status = "registered" 
        | .metadata.publisher.name = "PSI Open Data Provider"
        | if $new_thumb != "" then .metadata.thumbnail = $new_thumb else . end')
    echo "DOI content for DOI $DOI: $DOI_CONTENT"

    PATCH_RETURN=$(curl -X PATCH -H "Authorization: Bearer $SCICAT_TOKEN" \
        -H "Content-Type: application/json" -d \
        "$DOI_CONTENT" \
        "$SCICAT_URL/api/v4/publisheddata/${DOI}")

    if [ $? -ne 0 ]; then
        echo "Error updating DOI $DOI in SciCat"
        continue
    fi

    if echo "$PATCH_RETURN" | jq -e '.statusCode == 400 or .error == "Bad Request"' > /dev/null; then
        echo "Exiting script. Updated content is: $PATCH_RETURN"
        continue
    fi
    
    FORMATTED_PAYLOAD=$(echo "$PATCH_RETURN" | jq \
        --arg landingPage "$LANDING_PAGE_URL" '{
        data: {
            type: "dois",
            attributes: {
            event: "publish",
            doi: .doi,
            titles: [{ lang: "en", title: .title }],
            descriptions: ([{ description: .abstract, descriptionType: "Abstract", lang: "en" }] + (.metadata.descriptions // [])),
            publicationYear: .metadata.publicationYear,
            subjects: .metadata.subjects,
            creators: .metadata.creators,
            publisher: .metadata.publisher,
            contributors: .metadata.contributors,
            types: { resourceTypeGeneral: "Dataset", resourceType: .metadata.resourceType },
            relatedItems: .metadata.relatedItems,
            relatedIdentifiers: .metadata.relatedIdentifiers,
            language: .metadata.language,
            dates: .metadata.dates,
            sizes: .metadata.sizes,
            formats: .metadata.formats,
            rightsList: .metadata.rightsList,
            geoLocations: .metadata.geoLocations,
            fundingReferences: .metadata.fundingReferences,
            url: "\($landingPage)\(.doi | @uri)"
            }
        }
    }')

    if [ $? -ne 0 ]; then
        echo "Error formatting DOI $DOI from SciCat"
        continue
    fi

    DATACITE_RETURN=$(curl -X PUT \
        -H "Content-Type: application/json" \
        -H "Accept: application/vnd.api+json" \
        -H "Authorization: Basic $(echo -n "$DATACITE_USERNAME:$DATACITE_TOKEN" | base64)" \
        -d "$FORMATTED_PAYLOAD" \
        "$DATACITE_URL/dois/${DOI}")

    if [ $? -ne 0 ]; then
        echo "Error updating DOI $DOI in DataCite"
        continue
    fi
    
    if echo "$DATACITE_RETURN" | jq -e '.errors and (.errors | length > 0)' > /dev/null; then
        echo "Error updating DOI $DOI in DataCite"
        echo "Exiting script. DataCite returned errors: $DATACITE_RETURN"
        continue
    fi

    DATACITE_ID=$(echo "$DATACITE_RETURN" | jq -r '.data.id')
    echo "Updated DATACITE_ID: $DATACITE_ID"

    echo "DOI $DOI has been published to DataCite: $DATACITE_URL/application/vnd.datacite.datacite+json/$DOI"
done
