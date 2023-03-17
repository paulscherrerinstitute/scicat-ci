"use strict";

const checkEmailJobInitiator = (data, currentUser) => {
  const condition = data && data.emailJobInitiator && data.emailJobInitiator === currentUser;
  if (!condition && data.type) {
    const error = new Error();
    error.statusCode = 401,
    error.name = "Error",
    error.message = "Authorization Required",
    error.code = "AUTHORIZATION_REQUIRED";
    throw error;
  }
};

const addEmailJobInitiatorFilter = (filter, currentUser) => {
  const additionalFilter = { emailJobInitiator: currentUser };
  if (!filter)
    filter = { where: additionalFilter };
  else if (!filter.where)
    filter.where = additionalFilter;
  else
    filter.where = { and: [filter.where, additionalFilter] };
  return filter;
};

const isGlobalAccess = (currentGroups) => (
  currentGroups && currentGroups.includes("globalaccess")
)

const removeNonAuthorized = (resultList, currentUser) => (
  resultList.filter(item => item.emailJobInitiator === currentUser)
)

const getCurrentUserEmail = async (userId) => {
  const userIdentityModel = app.models.UserIdentity;
  const userIdentity = await userIdentityModel.find({userId: userId});
  if (userIdentity.length === 1 && userIdentity.profile && userIdentity.profile.email)
    return userIdentity.profile.email
  const userModel = app.models.User;
  const user = await userModel.findById(userId);
  return user.email
}

module.exports = function (app) {
  app.models.Job.beforeRemote("**", async (ctx, unused, next) => {
    if (isGlobalAccess(ctx.args.options.currentGroups)) {
      next();
      return;
    }
    if (ctx.args.data && ctx.methodString !== "Job.create") {
      const email = await getCurrentUserEmail(ctx.options.accessToken.userId);
      checkEmailJobInitiator(ctx.args.data, email);
    } else if ("filter" in ctx.args) {
      const email = await getCurrentUserEmail(ctx.options.accessToken.userId);
      ctx.args.filter = addEmailJobInitiatorFilter(
        ctx.filter, 
        email
      );
    }
  });

  app.models.Job.afterRemote("**", async (ctx, unused, next) => {
    if (isGlobalAccess(ctx.args.options.currentGroups)) {
      next();
      return;
    }
    if(ctx.result && ctx.methodString !== "Job.create") {
      const email = await getCurrentUserEmail(ctx.args.options.accessToken.userId);
      if (ctx.args.id)
        checkEmailJobInitiator(ctx.result, email);
      else if (Array.isArray(ctx.result)) 
        ctx.result = removeNonAuthorized(ctx.result, email)
    }
  });
}
