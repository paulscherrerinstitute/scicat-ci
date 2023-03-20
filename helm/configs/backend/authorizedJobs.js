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

const addEmailJobInitiatorField = (fields, currentUser) => {
  if (!fields)
    fields = { emailJobInitiator: currentUser };
  else
    fields.emailJobInitiator = currentUser;
  return fields
}

module.exports = function (app) {
  app.models.Job.beforeRemote("**",function(ctx, unused, next){
    if (isGlobalAccess(ctx.args.options.currentGroups)) {
      next();
      return;
    }
    if (ctx.args.data && ctx.methodString !== "Job.create")
      checkEmailJobInitiator(ctx.args.data, ctx.args.options.currentUserEmail);
    else if ("filter" in ctx.args) {
      ctx.args.filter = addEmailJobInitiatorFilter(
        ctx.filter, 
        ctx.args.options.currentUserEmail
      );
    }
    else if (ctx.methodString === "Job.fullquery")
      addEmailJobInitiatorField(ctx.args.fields, ctx.args.options.currentUserEmail);
    next();
  });

  app.models.Job.afterRemote("**",function(ctx, unused, next){
    if (isGlobalAccess(ctx.args.options.currentGroups)) {
      next();
      return;
    }
    if(ctx.result && ctx.methodString !== "Job.create") {
      if (ctx.args.id)
        checkEmailJobInitiator(ctx.result, ctx.args.options.currentUserEmail);
    }
    next();
  });
}
