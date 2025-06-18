export const environment = {
    accessDataHref:
      "https://www.psi.ch/en/photon-science-data-services/slsswissfel-data-transfer",
    accessInstructions:
      "To access the data associated with this DOI click below and follow the instructions",
    directMongoAccess: true,
    doiBaseUrl: "https://doi.org/",
    facility: "psi",
    lbBaseURL: "https://dacat-development.psi.ch",
    oaiProviderRoute: null,
    production: true,
    scicatBaseUrl: "https://discovery-development.psi.ch",
    showLogoBanner: false,
    retrieveToEmail: {
      option: "URLs", 
      username: "lp_service", 
      title: "Please enter your email address where you will receive the download procedure",
      confirmMessage: "Are you sure you want to continue?"
  },
  statusMessage: "URL retrieve is currently down. Please check <a href='https://scistatus.psi.ch/' target=_blank>https://scistatus.psi.ch/</a> for latest updates.",
  statusCode: "WARN",
};
