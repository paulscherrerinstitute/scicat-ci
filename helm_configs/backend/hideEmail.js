"use strict";

function hideEmails(result){
    if(result.ownerEmail) result.ownerEmail="";
    if(result.contactEmail) result.contactEmail="";
    if(result.principalInvestigator) result.principalInvestigator="";
    if(result.investigator) result.investigator="";
    if(result.orcidOfOwner) result.orcidOfOwner="";
}

module.exports = function (app) {
  app.models.Dataset.afterRemote("**",function(ctx, unused, next){
    if(ctx.result) {
      if(Array.isArray(ctx.result)) {
        ctx.result.forEach(function (result) {
          hideEmails(result);
        });
      } else {
        hideEmails(ctx.result);
      }
    }
    next();
  });
}