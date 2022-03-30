exports.accessGroupsToProfile =
function (req, done) {
  return function (err, user, identity, token) {
      identity.updateAttribute('profile', {
        accessGroups: identity.profile._json.pgroups,
        ...identity.profile,
      })
      var authInfo = {
        identity: identity,
      };
      if (token) {
        authInfo.accessToken = token;
      }  
      done(err, user, authInfo)  
    }
};
