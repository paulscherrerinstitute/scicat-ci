/* eslint-disable @typescript-eslint/no-require-imports */
// Fixes datasetlifecycle.archiveRetentionTime and dateOfPublishing set by the
// buggy defaults fixed in https://github.com/SciCatProject/backend/pull/3050
// (weekday used as day of month), and fills
// missing ones. A value is wrong if it equals the buggy default at createdAt or
// updatedAt, with shift 0 or the configured one. Wrong and missing values
// become creation day (UTC) + POLICY_RETENTION_SHIFT / POLICY_PUBLICATION_SHIFT
// years; a negative retention shift means no retention date.
const {
  getPolicyPublicationShiftInYears,
  getPolicyRetentionShiftInYears,
} = require("../dist/config/policy-times");

const BATCH_SIZE = 5000;

const LC = "datasetlifecycle";
const RETENTION = "archiveRetentionTime";
const PUBLISHING = "dateOfPublishing";

const isValidDate = (d) => d instanceof Date && !isNaN(d);
const isMissing = (v) => v === undefined || v === null;

// The buggy default at time t: year + shift, month, weekday
const weekdayDefault = (t, shift) =>
  new Date(
    Date.UTC(t.getUTCFullYear() + shift, t.getUTCMonth(), t.getUTCDay()),
  );

// Start of the day (UTC) + years, like todayShiftedByYears; Feb 29 -> Feb 28
const dateShiftedByYears = (date, years) => {
  const year = date.getUTCFullYear() + years;
  const month = date.getUTCMonth();
  const lastDayOfMonth = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
  return new Date(
    Date.UTC(year, month, Math.min(date.getUTCDate(), lastDayOfMonth)),
  );
};

// Valid values that can coincide with the buggy default
const isCreationDayPlusYears = (value, createdAt) => {
  const years = value.getUTCFullYear() - createdAt.getUTCFullYear();
  return (
    years >= 1 &&
    value.getTime() === dateShiftedByYears(createdAt, years).getTime()
  );
};

const hasWeekdayBug = (value, { createdAt, updatedAt }, shifts) =>
  isValidDate(value) &&
  !isCreationDayPlusYears(value, createdAt) &&
  [createdAt, updatedAt].some(
    (t) =>
      isValidDate(t) &&
      shifts.some((s) => weekdayDefault(t, s).getTime() === value.getTime()),
  );

// The getters fall back to defaults when unset, so require explicit values
const requireYearsFromEnv = (name, getter) => {
  const raw = process.env[name];
  if (Number.isNaN(Number.parseInt(raw ?? "", 10))) {
    throw new Error(
      `${name} must be set to a number of years (in .env or the environment), got "${raw ?? ""}"`,
    );
  }
  return getter();
};

module.exports = {
  async up(db) {
    const retentionYears = requireYearsFromEnv(
      "POLICY_RETENTION_SHIFT",
      getPolicyRetentionShiftInYears,
    );
    const publicationYears = requireYearsFromEnv(
      "POLICY_PUBLICATION_SHIFT",
      getPolicyPublicationShiftInYears,
    );
    // shifts the buggy code ran with
    const retentionShifts = [...new Set([0, retentionYears])];
    const publicationShifts = [...new Set([0, publicationYears])];

    const start = Date.now();
    const elapsed = () => `${((Date.now() - start) / 1000).toFixed(1)}s`;
    const datasets = db.collection("Dataset");

    const match = { createdAt: { $type: "date" } };
    const total = await datasets.countDocuments(match);
    console.log(
      `[${elapsed()}] Checking ${total.toLocaleString()} datasets, ` +
        `POLICY_RETENTION_SHIFT=${retentionYears}` +
        (retentionYears < 0 ? " (retained indefinitely)" : "") +
        `, POLICY_PUBLICATION_SHIFT=${publicationYears}`,
    );

    let operations = [];
    let processed = 0;
    const fixed = {
      [RETENTION]: 0,
      [PUBLISHING]: 0,
      [`${RETENTION} filled`]: 0,
      [`${PUBLISHING} filled`]: 0,
    };
    const flush = async () => {
      if (operations.length === 0) return;
      await datasets.bulkWrite(operations, { ordered: false });
      operations = [];
      console.log(
        `[${elapsed()}] ${processed.toLocaleString()}/${total.toLocaleString()} checked, fixed: ${JSON.stringify(fixed)}`,
      );
    };

    const cursor = datasets
      .find(match)
      .project({
        createdAt: 1,
        updatedAt: 1,
        [`${LC}.${RETENTION}`]: 1,
        [`${LC}.${PUBLISHING}`]: 1,
      })
      .batchSize(BATCH_SIZE);

    for await (const dataset of cursor) {
      processed += 1;
      if (!isValidDate(dataset.createdAt)) continue;
      const lifecycle = dataset[LC] ?? {};
      const { createdAt } = dataset;

      // filter on the old values (null = missing), so reruns are no-ops
      const filter = { _id: dataset._id };
      const $set = {};
      const $unset = {};

      if (isMissing(lifecycle[RETENTION])) {
        if (retentionYears >= 0) {
          filter[`${LC}.${RETENTION}`] = null;
          $set[`${LC}.${RETENTION}`] = dateShiftedByYears(
            createdAt,
            retentionYears,
          );
          fixed[`${RETENTION} filled`] += 1;
        }
      } else if (
        hasWeekdayBug(lifecycle[RETENTION], dataset, retentionShifts)
      ) {
        filter[`${LC}.${RETENTION}`] = lifecycle[RETENTION];
        if (retentionYears < 0) $unset[`${LC}.${RETENTION}`] = "";
        else
          $set[`${LC}.${RETENTION}`] = dateShiftedByYears(
            createdAt,
            retentionYears,
          );
        fixed[RETENTION] += 1;
      }
      if (isMissing(lifecycle[PUBLISHING])) {
        filter[`${LC}.${PUBLISHING}`] = null;
        $set[`${LC}.${PUBLISHING}`] = dateShiftedByYears(
          createdAt,
          publicationYears,
        );
        fixed[`${PUBLISHING} filled`] += 1;
      } else if (
        hasWeekdayBug(lifecycle[PUBLISHING], dataset, publicationShifts)
      ) {
        filter[`${LC}.${PUBLISHING}`] = lifecycle[PUBLISHING];
        $set[`${LC}.${PUBLISHING}`] = dateShiftedByYears(
          createdAt,
          publicationYears,
        );
        fixed[PUBLISHING] += 1;
      }

      if (Object.keys(filter).length === 1) continue;
      const update = {};
      if (Object.keys($set).length) update.$set = $set;
      if (Object.keys($unset).length) update.$unset = $unset;
      operations.push({ updateOne: { filter, update } });
      if (operations.length >= BATCH_SIZE) await flush();
    }
    await flush();

    console.log(
      `[${elapsed()}] ✅ Migration completed, fixed: ${JSON.stringify(fixed)}`,
    );
  },

  async down() {
    // No path backward: the replaced values were wrong
  },
};
