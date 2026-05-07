keywords = [
  {
    keyword: "setFullName",
    schema: false,
    modifying: true,
    validate: function (data, dataCxt) {
      data.name =
        data.givenName && data.familyName
          ? `${data.familyName}, ${data.givenName}`
          : data.givenName || data.familyName || undefined;
      return true;
    },
  },
];

async function mergeKeywords(ctx) {
  const datasets = await ctx.datasetsService.findAll({
    where: {
      $or: ctx.publishedData.datasetPids.map((p) => ({
        pid: p,
      })),
    },
  });

  return () => {
    if (!datasets) return;

    return Array.from(new Set(datasets.flatMap((ds) => ds.keywords))).map(
      (k) => ({
        subject: k,
        lang: "en",
      }),
    );
  };
}

async function mergeCreators(ctx) {
  const datasets = await ctx.datasetsService.findAll({
    where: {
      $or: ctx.publishedData.datasetPids.map((p) => ({
        pid: p,
      })),
    },
  });

  return () => {
    if (!datasets) return;

    return Array.from(
      new Set(datasets.flatMap((ds) => ds.owner.split(","))),
    ).flatMap((creator) => {
      const split = creator.split(" ");
      if (split.length !== 2) {
        return [];
      }

      return {
        name: `${split[1]}, ${split[0]}`,
        givenName: split[0],
        familyName: split[1],
        affiliation: [
          {
            name: "Paul Scherrer Institute",
            schemeUri: "https://ror.org",
            affiliationIdentifier: "https://ror.org/03eh3y714",
            affiliationIdentifierScheme: "ROR",
          },
        ],
      };
    });
  };
}

async function computeTotalSize(ctx) {
  const datasets = await ctx.datasetsService.findAll({
    where: {
      $or: ctx.publishedData.datasetPids.map((p) => ({
        pid: p,
      })),
    },
  });

  return () => {
    if (!datasets) return;

    return [datasets.reduce((acc, ds) => acc + (ds.size ?? 0), 0).toString()];
  };
}

async function datasetLinks(ctx) {
  const relatedIdentifiers = ctx.publishedData.datasetPids.map((pid) => {
    return {
      relatedItemType: "Other",
      relationType: "References",
      relatedItemIdentifier: {
        relatedItemIdentifierType: "URL",
        relatedItemIdentifier: `${process.env["SCICAT_FRONTEND_URL"]}/datasets/${encodeURIComponent(pid)}`,
      },
    };
  });

  return () => {
    return relatedIdentifiers;
  };
}

const dynamicDefaults = new Map([
  ["mergeKeywords", mergeKeywords],
  ["mergeCreators", mergeCreators],
  ["computeTotalSize", computeTotalSize],
  ["datasetLinks", datasetLinks],
]);

module.exports = {
  keywords,
  dynamicDefaults,
};
