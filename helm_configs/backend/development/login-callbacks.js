const logger = require("../../common/logger");

module.exports = function (app) {
  app.models.UserIdentity.observe("before save", function(ctx, next) {
    if (ctx.instance){
      ctx.instance.profile.accessGroups = ctx.instance.profile._json.pgroups
      next()
    }
    if (ctx.data){
      ctx.data.profile.accessGroups = ctx.data.profile._json.pgroups
      next()
    }
    if (!ctx.data && !ctx.instance){
      logger.logInfo("No context data or instance from UserIdentity");
      next()
      return
    }
  })
};
