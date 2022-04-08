import { TableColumn } from "state-management/models";

// The file contents for the current environment will overwrite these during build.
// The build system defaults to the dev environment which uses `environment.ts`, but if you do
// `ng build --env=development` then `environment.development.ts` will be used instead.
// The list of which env maps to which file can be found in `angular-cli.json`.

export const environment = {
  production: true,
  lbBaseURL: "https://scicat.development.psi.ch",
  archiveWorkflowEnabled: true,
  retrieveDestinations: [{option: "PSI", location: "/home/out"}, {option:"CSCS (Testphase)"}],
  externalAuthEndpoint: "/auth/msad",
  editMetadataEnabled: true,
  editSampleEnabled: true,
  editPublishedData: true,
  scienceSearchEnabled: true,
  disabledDatasetColumns: [],
  facility: "PSI",
  multipleDownloadEnabled: false,
  shoppingCartEnabled: true,
  shoppingCartOnHeader: true,
  columnSelectEnabled: true,
  ingestManual: "http://melanie.gitpages.psi.ch/SciCatPages/",
  gettingStarted: "http://melanie.gitpages.psi.ch/SciCatPages/SciCatGettingStartedSLSSummary.pdf",
  jupyterHubUrl: "",
  fileserverBaseURL: null,
  synapseBaseUrl: null,
  riotBaseUrl: null,
  datasetReduceEnabled: false,
  fileColorEnabled: false,
  jsonMetadataEnabled: true,
  localColumns: [
    { name: "select", order: 0, type: "standard", enabled: true },
    { name: "datasetName", order: 1, type: "standard", enabled: true },
    { name: "runNumber", order: 2, type: "standard", enabled: false },
    { name: "sourceFolder", order: 3, type: "standard", enabled: true },
    { name: "size", order: 4, type: "standard", enabled: true },
    { name: "creationTime", order: 5, type: "standard", enabled: true },
    { name: "type", order: 6, type: "standard", enabled: true },
    { name: "image", order: 7, type: "standard", enabled: false },
    { name: "metadata", order: 8, type: "standard", enabled: false },
    { name: "proposalId", order: 9, type: "standard", enabled: true },
    { name: "ownerGroup", order: 10, type: "standard", enabled: true },
    { name: "dataStatus", order: 11, type: "standard", enabled: true },
    // { name: "derivedDatasetsNum", order: 12, type: "standard", enabled: false }
  ] as TableColumn[],
  logbookEnabled: false,
  metadataPreviewEnabled: true,
  maxDirectDownloadSize: 5000000000,
  multipleDownloadAction: null,
  searchProposals: true,
  searchSamples: true,
  sftpHost: null,
  tableSciDataEnabled: true,
  shareEnabled: true,
  userProfileImageEnabled: true,
  searchPublicDataEnabled: true,
  landingPage: "doi2.psi.ch/detail/", 
  fileDownloadEnabled: false,
  jobsEnabled: true,
  policiesEnabled: true,
  addDatasetEnabled: true,
  editDatasetSampleEnabled: true,
  scienceSearchUnitsEnabled: true,
  metadataStructure: "tree",
  loginFormEnabled: true,
  oAuth2Endpoints: [{
    displayText: "Login with PSI user account", displayImage:
      "../../../assets/images/keycloak_icon_256px.svg", authURL:
      "auth/keycloak"
  }]
};
