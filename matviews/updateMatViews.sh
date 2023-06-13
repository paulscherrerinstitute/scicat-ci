mongosh 'mongodb://$(USER):$(PASSWORD)@my-cluster-name-rs0.mongo.svc.cluster.local/$(DB)?replicaSet=rs0&directConnection=true&readPreference=secondaryPreferred' --file updateMatViews.js  

