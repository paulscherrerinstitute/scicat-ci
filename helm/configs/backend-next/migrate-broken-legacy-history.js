/* eslint-disable @typescript-eslint/no-require-imports */
const convertObsoleteHistoryToGenericHistory =
  require("../dist/datasets/utils/history.util").convertObsoleteHistoryToGenericHistory;

/**This script migrates v3 history records that were in invalid format to the generic History collection.
 * Instead of the expected structure {datasetlifecycle: {previousValue: ..., currentValue: ...}}, some history records
 * only contained a {datasetlifecycle: updatedValue}. As a result, these were missed by the original migration script
 * i.e. 20251014092142-legacy-history-to-generic-history.js.
 * This script reconstructs the broken records in expected format, and migrates them to generic history.
 */
module.exports = {
  /**
   * @param db {import('mongodb').Db}
   * @param client {import('mongodb').MongoClient}
   * @returns {Promise<void>}
   */
  async up(db, client) {
    // The query on line 14 should be run against the old DB snapshot
    // One approach would be to copy the old dacat.Dataset collection into the current DB say under oldDataset
    const affectedDatasets = db.collection("oldDataset").find({
      history: {
        $elemMatch: {
          datasetlifecycle: { $exists: true },
          "datasetlifecycle.previousValue": { $exists: false },
        },
      },
    });

    let batch = [];
    const BATCH_SIZE = 1000;
    let successCount = 0;
    let failedCount = 0;
    for await (const ds of affectedDatasets) {
      const pid = ds._id;
      const history = ds.history;
      let prev = {};
      for (const entry of history) {
        if (entry.datasetlifecycle && entry.datasetlifecycle.previousValue) {
          break; // first valid record found, stop for this ds
        }
        if (entry.datasetlifecycle) {
          entry.datasetlifecycle.currentValue = JSON.parse(
            JSON.stringify(entry.datasetlifecycle),
          );
          entry.datasetlifecycle.previousValue = prev;
          prev = entry.datasetlifecycle.currentValue;
          const genericHistory = convertObsoleteHistoryToGenericHistory(
            entry,
            pid,
          );
          batch.push({
            replaceOne: {
              filter: {
                documentId: pid,
                timestamp: genericHistory.timestamp,
                before: {},
                after: {},
              },
              replacement: genericHistory,
            },
          });
          if (batch.length === BATCH_SIZE) {
            const bulkWriteResult = await db
              .collection("History")
              .bulkWrite(batch, { ordered: false });
            successCount += bulkWriteResult.modifiedCount;
            failedCount += BATCH_SIZE - bulkWriteResult.modifiedCount;

            batch = [];
            console.log(
              "migrating, count, failedCount: ",
              successCount,
              failedCount,
            );
          }
        }
      }
    }
    // Flush remaining writes, if any
    if (batch.length > 0) {
      const bulkWriteResult = await db
        .collection("History")
        .bulkWrite(batch, { ordered: false });
      successCount += bulkWriteResult.modifiedCount;
      failedCount += batch.length - bulkWriteResult.modifiedCount;
    }
    console.log("FINISHED: count, failedCount: ", successCount, failedCount);
  },

  async down(db, client) {
    /* The down function of the original script 20251014092142-legacy-history-to-generic-history.js is sufficient for downward migration*/
  },
};
