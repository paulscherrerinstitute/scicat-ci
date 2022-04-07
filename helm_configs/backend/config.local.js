// catamel-psiconfig
"use strict";
var doiServer = process.env.ENV !== "production" ? "2" : "";
var envOAIProvider = "https://doi" + (doiServer) + ".psi.ch/oaipmh/oai/Publication";
var p = require("../package.json");
var version = p.version.split(".").shift();
module.exports = {
  restApiRoot: "/api" + (version > 0 ? "/v" + version : ""),
  host: process.env.HOST || "0.0.0.0",
  port: process.env.PORT || 3000,
  pidPrefix: "20.500.11935",
  doiPrefix: "10.16907",
  oaiProviderRoute: envOAIProvider,
  policyPublicationShiftInYears: 3,
  policyRetentionShiftInYears: 10,
  metadataKeysReturnLimit: 100,
  metadataParentInstancesReturnLimit: 10,
  site: "PSI",
  defaultManager: "scicatingestor@psi.ch",
  facilities: ["SLS", "SINQ", "SWISSFEL", "SmuS"],
  jobMessages: {
    jobSubmitted: "Submitted for immediate execution",
    jobSubmittedDelayed: "Submitted for delayed execution",
    jobForwarded: "Forwarded to archive system",
    jobStarted: "Execution started",
    jobInProgress: "Finished by %i percent",
    jobSuccess: "Successfully finished",
    jobError: "Finished with errors",
    jobCancel: "Cancelled"
  },
  smtpSettings: {
    host: "mail.ethz.ch",
    port: 587,
    secure: false,
    auth: JSON.parse(process.env.MAIL_AUTH)
  },
  expressSessionSecret: "asecret",
  smtpMessage: {
    from: "scicatarchivemanager@psi.ch",
    to: undefined,
    subject: "[SciCat " + process.env.ENV + "]",
    text: undefined // can also set html key and this will override this
  },
  queue: "rabbitmq"
};
