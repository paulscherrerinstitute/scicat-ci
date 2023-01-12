"use strict";
const config = require("../config.local");

module.exports = (app) => {

    const Job = app.models.Job;
    const jobEventEmitter = Job.eventEmitter;
  
    const notifyUpdates = async (ctx) => {
        if (config.queue && config.queue === "rabbitmq" && ctx.instance.jobStatusMessage.startsWith("finish")) {
            Job.publishJob(ctx.instance, "jobqueue");
        console.log("      Updated Job %s#%s and published to message broker", ctx.Model.modelName, ctx.instance.id);
        }
    };

    jobEventEmitter.addListener("jobUpdated", notifyUpdates);
};
