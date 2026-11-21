// Adds jobResultObject.datasetTotals to each job: numberOfDatasets and the sums
// of size, numberOfFiles, packedSize and numberOfFilesArchived of the datasets
// in jobParams.datasetList. Runs server-side ($lookup + $merge, MongoDB >= 5).
const TOTALS_KEY = "datasetTotals";
const TOTAL_FIELDS = [
  "size",
  "numberOfFiles",
  "packedSize",
  "numberOfFilesArchived",
];
const JOBS_WITH_DATASETS = {
  "jobParams.datasetList": { $type: "array" },
  "jobParams.datasetList.0": { $exists: true },
};

module.exports = {
  async up(db) {
    const start = Date.now();
    await db
      .collection("Job")
      .aggregate(
        [
          // skips legacy jobs with a non-array datasetList
          { $match: JOBS_WITH_DATASETS },
          {
            $project: {
              pids: {
                $setUnion: [{ $ifNull: ["$jobParams.datasetList.pid", []] }],
              },
            },
          },
          {
            $lookup: {
              from: "Dataset",
              localField: "pids",
              foreignField: "_id",
              pipeline: [
                {
                  $group: {
                    _id: null,
                    ...Object.fromEntries(
                      TOTAL_FIELDS.map((f) => [f, { $sum: `$${f}` }]),
                    ),
                  },
                },
                { $project: { _id: 0 } },
              ],
              as: "totals",
            },
          },
          {
            $project: {
              stats: {
                $mergeObjects: [
                  Object.fromEntries(TOTAL_FIELDS.map((f) => [f, 0])),
                  { $first: "$totals" },
                  { numberOfDatasets: { $size: "$pids" } },
                ],
              },
            },
          },
          {
            $merge: {
              into: "Job",
              on: "_id",
              whenMatched: [
                {
                  $set: {
                    jobResultObject: {
                      $mergeObjects: [
                        { $ifNull: ["$jobResultObject", {}] },
                        { [TOTALS_KEY]: "$$new.stats" },
                      ],
                    },
                  },
                },
              ],
              whenNotMatched: "discard",
            },
          },
        ],
        { allowDiskUse: true },
      )
      .toArray(); // runs the pipeline
    console.log(
      `✅ Job totals added in ${((Date.now() - start) / 1000).toFixed(1)}s`,
    );
  },

  async down(db) {
    await db
      .collection("Job")
      .updateMany(
        { [`jobResultObject.${TOTALS_KEY}`]: { $exists: true } },
        { $unset: { [`jobResultObject.${TOTALS_KEY}`]: "" } },
      );
  },
};
