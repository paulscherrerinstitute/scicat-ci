module.exports = {
  async up(db, client) {
    // in mongo < 5 there's no trivial way to unset the field. Live with duplication
    db.collection("Proposal").updateMany(
      { "MeasurementPeriodList.id": { $exists: true } },
      [
        {
          $set: {
            MeasurementPeriodList: {
              $map: {
                input: "$MeasurementPeriodList",
                as: "mp",
                in: {
                  $mergeObjects: [
                    "$$mp",
                    { _id: "$$mp.id" },
                  ]
                }
              }
            }
          }
        }
      ]
    )
  },

  async down(db, client) {
    // No path backward since in mongo < 5 there's no easy way to unset 
  },
};
