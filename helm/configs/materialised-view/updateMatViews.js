function dateLog(message) {
  const timestamp = new Date().toISOString();
  console.log(`${timestamp}: ${message}`);
}

dateLog("Starting materialized view update");

function getLastUpdated(collection) {
  let lastUpdate;
  if (db.getCollectionNames().indexOf(collection) > -1) {
    lastUpdate = db[collection]
      .find({}, { _id: 0, updatedAt: 1 })
      .sort({ updatedAt: -1 })
      .limit(1)
      .next().updatedAt;
    dateLog(`last ${collection} update was at: ${lastUpdate}`);
  } else {
    lastUpdate = new Date("2000-01-01");
    dateLog(`First ${collection} run, using start date: ${lastUpdate}`);
  }
  return lastUpdate;
}

function aggregateWithDefaults(
  collection,
  computationPipe,
  options = { matchDate: true },
) {
  const collectionFiltered =
    options.outputCollection ?? `${collection}Filtered`;
  dateLog(
    `Running aggregation pipeline from ${collection} to ${collectionFiltered}`,
  );
  db[collection].aggregate([
    outputs.matchDate
      ? { $match: { updatedAt: { $gt: getLastUpdated(collectionFiltered) } } }
      : {},
    computationPipe,
    {
      $merge: {
        into: collectionFiltered,
        whenMatched: "replace",
        whenNotMatched: "insert",
      },
    },
  ]);
  dateLog(
    `Completed aggregation pipeline from ${collection} to ${collectionFiltered}`,
  );
  dateLog(`Creating indexes for ${collectionFiltered}`);
  db[collectionFiltered].createIndexes([{ "$**": 1 }]);
  dateLog(`Created indexes for ${collectionFiltered}`);
}

function createDatasetFiltered() {
  aggregateWithDefaults(
    "Dataset",
    {
      $group: {
        _id: { location: "$creationLocation" },
        count: { $sum: 1 },
      },
    },
    {
      matchDate: false,
      outputCollection: "LocationCountsMat",
    },
  );
  aggregateWithDefaults(
    "Dataset",
    {
      $project: {
        scientificMetadata: 0,
        "datasetlifecycle.archiveReturnMessage": 0,
      },
    },
    {
      $lookup: {
        from: "LocationCountsMat",
        localField: "creationLocation",
        foreignField: "_id.location",
        as: "locationcount",
      },
    },
    {
      $lookup: {
        from: "Datablock",
        localField: "_id",
        foreignField: "datasetId",
        as: "datablocks",
      },
    },
    { $match: { "locationcount.0.count": { $gt: 1 } } },
    { $project: { locationcount: 0 } },
  );
}

function createJobFiltered() {
  aggregateWithDefaults(
    "Job",
    {
      $lookup: {
        from: "Dataset",
        localField: "datasetList.pid",
        foreignField: "_id",
        as: "lookupResult",
      },
    },
    {
      $addFields: {
        totalSize: {
          $sum: "$lookupResult.size",
        },
        totalNumber: {
          $size: "$lookupResult",
        },
      },
    },
    {
      $project: {
        lookupResult: 0,
      },
    },
    {
      $addFields: {
        datasetList: "$datasetList.pid",
      },
    },
  );
}

function createDatablockFiltered() {
  aggregateWithDefaults(
    "Datablock",
    { $project: { dataFileList: 0 } },
    {
      $addFields: {
        copies: {
          $substrCP: ["$archiveId", 0, { $indexOfCP: ["$archiveId", "/"] }],
        },
      },
    },
  );
}

createDatasetFiltered();
createJobFiltered();
createDatablockFiltered();

dateLog("Completed materialized view update");
