'use strict';
const mongoose = require('mongoose');
const { MONGO_URI } = require('./config');

async function connect() {
  await mongoose.connect(MONGO_URI);
  console.log(`[db] connected → ${MONGO_URI}`);
}

module.exports = { connect };
