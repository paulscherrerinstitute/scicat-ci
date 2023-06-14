
//
// mongosh based script to create/update materialized views DatasetFiltered and JobFiltered
// 
console.log(new Date(),": starting materialized view creation", )
// get date of last update
// ( since we have repl server: we could try to use oplog as an alternative approach )

if (db.getCollectionNames().indexOf('DatasetFiltered') > -1){
  lastDatasetUpdate=db.DatasetFiltered.find({},{_id:0,updatedAt:1}).sort({'updatedAt': -1}).limit(1).next().updatedAt
  console.log(new Date(), ": last dataset update was at:",lastDatasetUpdate)
} else {
  lastDatasetUpdate=new Date("2000-01-01")
  console.log(new Date(), ": First dataset run, using start date:",lastDatasetUpdate)
}

if (db.getCollectionNames().indexOf('JobFiltered') > -1){
  lastJobUpdate=db.JobFiltered.find({},{_id:0,updatedAt:1}).sort({'updatedAt': -1}).limit(1).next().updatedAt
  console.log(new Date(), ": last job update was at:",lastJobUpdate)
} else {
  lastJobUpdate=new Date("2000-01-01")
  console.log(new Date(), ": First job run, using start date:",lastJobUpdate)
}

// first create the table counting the number of Datasets per location

console.log(new Date(), ": Create Location counter table")

db.Dataset.aggregate(
  [{
      "$group": {
          "_id": { "location": "$creationLocation" },
          "count": { "$sum": 1 }
      }
  },
  { $merge: { into: "LocationCountsMat", whenMatched: "replace" , whenNotMatched: "insert"} }
  ]
)

console.log(new Date(), ": Create DatasetFiltered table")

// now update materialized views of dataset table, ignoring "single-location" datasets  
db.Dataset.aggregate(
  [
      { "$match": {"updatedAt" : {$gt: lastDatasetUpdate}}},
      { "$project": { "scientificMetadata": 0, "datasetlifecycle.archiveReturnMessage": 0 } },
      {
          "$lookup": {
              "from": "LocationCountsMat",
              "localField": "creationLocation",
              "foreignField": "_id.location",
              "as": "locationcount"
          }
      },
      { "$match": { "locationcount.0.count": { "$gt": 1 } } },
      { "$project": { "locationcount": 0} },
      { "$merge": { into: "DatasetFiltered", whenMatched: "replace" , whenNotMatched: "insert"} }
  ]
)


// update materialized view JobFiltered
console.log(new Date(), ": Create JobFiltered table")

db.Job.aggregate(
    [
        { $match: {updatedAt : {$gt: lastJobUpdate}}},
        {
          $lookup: {
            from: "Dataset",
            localField: "datasetList.pid",
            foreignField: "_id",
            as: "lookupResult",
          },
        },
        {
          $addFields:
            /**
             * newField: The new field name.
             * expression: The new field expression.
             */
      
            {
              totalSize: {
                $sum: "$lookupResult.size",
              },
              totalNumber: {
                $size: "$lookupResult",
              },
            },
        },
        {
          $project:
            /**
             * specifications: The fields to
             *   include or exclude.
             */
            {
              lookupResult: 0,
            },
        },
        {
          $addFields:
            /**
             * specifications: The fields to
             *   include or exclude.
             */
            {
              datasetList: "$datasetList.pid",
            },
        },
        { "$merge": { into: "JobFiltered", whenMatched: "replace", whenNotMatched: "insert"} }
      ]
    )

console.log(new Date(), ": Creating indices on materialized views")
    // create index if not yet there
db.DatasetFiltered.createIndexes( [{ "$**" : 1 }])
db.JobFiltered.createIndexes( [{ "$**" : 1 }])
//db.JobFiltered.createIndexes( [{ updatedAt: 1}, 
//    {emailJobInitiator: 1}, {type: 1}, {creationTime:1}, {createdAt:1} , {jobStatusMessage:1}, {totalSize:1 }])

console.log(new Date(), ": Tasks finished")
