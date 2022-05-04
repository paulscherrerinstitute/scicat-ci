"use strict";

const HttpErrors = require('http-errors');
let functionalAccounts;
try {
  functionalAccounts = require('../functionalAccounts.json');
} catch {
  functionalAccounts = {};
};

module.exports = function (app) {
  const allowed_ips = JSON.parse(process.env.ALLOWED_IPS || '["*.*.*.*"]');
  app.models.User.beforeRemote("login", function (ctx, unused, next) {
    if (ctx.args && ctx.args.credentials) {
      if (
        functionalAccounts.some(account => account.account === ctx.args.credentials.username)
        && !allowed_ips.some(ip => ctx.req.headers['x-forwarded-for'].startsWith(ip.split('*')[0]))
      )
        return next(new HttpErrors.BadRequest('Authentication Error'));
    }
    next();
  });
};
